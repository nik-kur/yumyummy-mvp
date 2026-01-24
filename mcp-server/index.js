import express from "express";
import cors from "cors";
import axios from "axios";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const app = express();
app.use(cors({ origin: "*", exposedHeaders: ["mcp-session-id"] }));
app.use(express.json());

const PORT = process.env.PORT || 3000;
const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL;
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN;

if (!BACKEND_BASE_URL) {
  console.error("ERROR: BACKEND_BASE_URL environment variable is required");
  process.exit(1);
}

// Create MCP server
const mcp = new McpServer({
  name: "yumyummy-mcp-server",
  version: "1.0.0",
});

// Register tool
mcp.tool(
  "get_day_context",
  "Get day nutrition summary from YumYummy backend",
  {
    user_id: z.number().int().describe("Telegram user id"),
    day: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).describe("Date in YYYY-MM-DD format"),
  },
  async ({ user_id, day }) => {
    console.log(`Tool call: get_day_context(user_id=${user_id}, day=${day})`);
    
    const url = `${BACKEND_BASE_URL}/day/${user_id}/${day}`;
    const headers = {};
    if (INTERNAL_API_TOKEN) headers["X-Internal-Token"] = INTERNAL_API_TOKEN;

    try {
      const response = await axios.get(url, { headers });
      return {
        content: [{ type: "text", text: JSON.stringify(response.data) }],
      };
    } catch (e) {
      const status = e?.response?.status;
      const data = e?.response?.data;
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            error: "backend_request_failed",
            status: status ?? null,
            details: data ?? e?.message ?? "unknown",
          }),
        }],
      };
    }
  }
);

// Streamable HTTP transport (stateless)
const transport = new StreamableHTTPServerTransport({
  sessionIdGenerator: undefined,
});

async function start() {
  await mcp.connect(transport);

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "yumyummy-mcp-server" });
});

// MCP endpoint - handles both initialization and ongoing communication
app.post("/mcp", async (req, res) => {
  // #region agent log
  res.on("finish", () => {
    fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_finish',message:'POST /mcp finished',data:{status:res.statusCode,mcpSessionId:res.getHeader('mcp-session-id') ?? null},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})}).catch(()=>{});
  });
  // #endregion agent log
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_entry',message:'POST /mcp entry',data:{method:req.body?.method,hasParams:!!req.body?.params,accept:req.headers?.accept,contentType:req.headers?.['content-type'],sessionId:req.headers?.['mcp-session-id']},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'A'})}).catch(()=>{});
  // #endregion agent log
  console.log("MCP POST request:", JSON.stringify(req.body));
  console.log("Headers:", JSON.stringify(req.headers));

  try {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_stateless',message:'Using stateless transport',data:{method:req.body?.method,sessionId:req.headers?.['mcp-session-id'] ?? null},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})}).catch(()=>{});
    // #endregion agent log
    // Handle the request
    await transport.handleRequest(req, res, req.body);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_handle_success',message:'transport.handleRequest success',data:{method:req.body?.method},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'D'})}).catch(()=>{});
    // #endregion agent log
    
  } catch (error) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_error',message:'Error handling MCP request',data:{errorMessage:error?.message},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'E'})}).catch(()=>{});
    // #endregion agent log
    console.error("Error handling MCP request:", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null,
      });
    }
  }
});

// Handle GET for SSE streams (if client reconnects)
app.get("/mcp", async (req, res) => {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:get_entry',message:'GET /mcp entry',data:{accept:req.headers?.accept,sessionId:req.headers?.['mcp-session-id'] ?? null},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'A'})}).catch(()=>{});
  // #endregion agent log
  try {
    await transport.handleRequest(req, res);
  } catch (error) {
    console.error("Error handling MCP GET request:", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null,
      });
    }
  }
});

// Start server
  app.listen(PORT, () => {
    console.log(`MCP server listening on port ${PORT}`);
    console.log(`Backend URL: ${BACKEND_BASE_URL}`);
    console.log(`Internal token: ${INTERNAL_API_TOKEN ? "configured" : "not set"}`);
  });
}

start().catch((e) => {
  console.error("Failed to start MCP server:", e);
  process.exit(1);
});
