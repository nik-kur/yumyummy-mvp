import express from "express";
import cors from "cors";
import axios from "axios";

const app = express();
app.use(cors({ origin: "*" }));
app.use(express.json());

const PORT = process.env.PORT || 3000;
const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL;
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN;

if (!BACKEND_BASE_URL) {
  console.error("ERROR: BACKEND_BASE_URL environment variable is required");
  process.exit(1);
}

// Tool definition
const getDayContextTool = {
  name: "get_day_context",
  description: "Get day nutrition summary from YumYummy backend",
  inputSchema: {
    type: "object",
    properties: {
      user_id: {
        type: "integer",
        description: "Telegram user id"
      },
      day: {
        type: "string",
        description: "Date in YYYY-MM-DD format"
      }
    },
    required: ["user_id", "day"]
  }
};

// JSON-RPC helpers
function jsonRpcResult(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function jsonRpcError(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  return { jsonrpc: "2.0", id: id ?? null, error };
}

// Execute tool
async function executeGetDayContext(user_id, day) {
  const url = `${BACKEND_BASE_URL}/day/${user_id}/${day}`;
  const headers = {};
  if (INTERNAL_API_TOKEN) headers["X-Internal-Token"] = INTERNAL_API_TOKEN;

  try {
    const response = await axios.get(url, { headers });
    return {
      content: [{ type: "text", text: JSON.stringify(response.data) }]
    };
  } catch (e) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          error: "backend_request_failed",
          status: e?.response?.status ?? null,
          details: e?.response?.data ?? e?.message ?? "unknown"
        })
      }]
    };
  }
}

// MCP JSON-RPC handler
async function handleMCPRequest(req, res) {
  // Log incoming request for debugging
  console.log("MCP Request:", JSON.stringify(req.body));

  try {
    const { jsonrpc, id, method, params } = req.body || {};

    if (!method) {
      return res.json(jsonRpcError(id, -32600, "Invalid Request: missing method"));
    }

    // 1) initialize - MCP handshake
    if (method === "initialize") {
      const protocolVersion = params?.protocolVersion || "2024-11-05";
      return res.json(jsonRpcResult(id, {
        protocolVersion,
        serverInfo: {
          name: "yumyummy-mcp-server",
          version: "1.0.0"
        },
        capabilities: {
          tools: { listChanged: false }
        }
      }));
    }

    // 2) notifications/initialized - client confirmation (no response needed, but send empty result)
    if (method === "notifications/initialized") {
      return res.status(204).send();
    }

    // 3) ping
    if (method === "ping") {
      return res.json(jsonRpcResult(id, {}));
    }

    // 4) tools/list
    if (method === "tools/list" || method === "listTools") {
      return res.json(jsonRpcResult(id, {
        tools: [getDayContextTool]
      }));
    }

    // 5) tools/call
    if (method === "tools/call" || method === "callTool") {
      const toolName = params?.name;
      const toolArgs = params?.arguments || params?.input || {};

      if (!toolName) {
        return res.json(jsonRpcError(id, -32602, "Invalid params: missing tool name"));
      }

      if (toolName === "get_day_context") {
        const userId = typeof toolArgs.user_id === "string" 
          ? parseInt(toolArgs.user_id, 10) 
          : toolArgs.user_id;
        const day = toolArgs.day;

        if (!Number.isFinite(userId) || typeof day !== "string") {
          return res.json(jsonRpcError(id, -32602, 
            "Invalid arguments. Expected: { user_id: number, day: string (YYYY-MM-DD) }"));
        }

        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(day)) {
          return res.json(jsonRpcError(id, -32602, "Invalid date format. Expected YYYY-MM-DD"));
        }

        const result = await executeGetDayContext(userId, day);
        return res.json(jsonRpcResult(id, result));
      }

      return res.json(jsonRpcError(id, -32601, `Unknown tool: ${toolName}`));
    }

    // Unknown method
    return res.json(jsonRpcError(id, -32601, `Method not found: ${method}`));

  } catch (error) {
    console.error("Error processing MCP request:", error);
    return res.json(jsonRpcError(null, -32603, "Internal error", error.message));
  }
}

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "yumyummy-mcp-server" });
});

// MCP endpoints - POST for JSON-RPC
app.post("/", handleMCPRequest);
app.post("/mcp", handleMCPRequest);

// GET endpoints - return server info for discovery
app.get("/", (req, res) => {
  res.json({
    name: "yumyummy-mcp-server",
    version: "1.0.0",
    protocol: "MCP",
    endpoints: {
      mcp: "/mcp"
    }
  });
});

app.get("/mcp", (req, res) => {
  res.json({
    name: "yumyummy-mcp-server", 
    version: "1.0.0",
    protocol: "MCP"
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`MCP server listening on port ${PORT}`);
  console.log(`Backend URL: ${BACKEND_BASE_URL}`);
  console.log(`Internal token: ${INTERNAL_API_TOKEN ? "configured" : "not set"}`);
});
