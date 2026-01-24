import express from "express";
import cors from "cors";
import axios from "axios";
import { z } from "zod";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

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

// 1) Create MCP server
const mcp = new McpServer({
  name: "yumyummy-mcp-server",
  version: "1.0.0",
});

// 2) Register tool
mcp.tool(
  "get_day_context",
  "Get day nutrition summary from YumYummy backend",
  {
    user_id: z.number().int().describe("Telegram user id"),
    day: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).describe("YYYY-MM-DD"),
  },
  async ({ user_id, day }) => {
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
        content: [
          {
            type: "text",
            text: JSON.stringify({
              error: "backend_request_failed",
              status: status ?? null,
              details: data ?? e?.message ?? "unknown",
            }),
          },
        ],
      };
    }
  }
);

// 3) Streamable HTTP transport (stateless)
const transport = new StreamableHTTPServerTransport({
  sessionIdGenerator: undefined,
});

async function start() {
  await mcp.connect(transport);

  app.get("/health", (req, res) => {
    res.json({ status: "ok", service: "yumyummy-mcp-server" });
  });

  // MCP endpoint
  app.post("/mcp", async (req, res) => {
    try {
      // Ensure Accept header includes both required types for MCP streamable transport
      const acceptHeader = req.headers.accept || "";
      if (!acceptHeader.includes("application/json") || !acceptHeader.includes("text/event-stream")) {
        req.headers.accept = "application/json, text/event-stream";
      }
      await transport.handleRequest(req, res, req.body);
    } catch (error) {
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

  // GET should not return tools
  app.get("/mcp", (req, res) => {
    res.status(405).json({
      jsonrpc: "2.0",
      error: { code: -32000, message: "Method not allowed." },
      id: null,
    });
  });

  app.listen(PORT, () => {
    console.log(`MCP server listening on port ${PORT}`);
  });
}

start().catch((e) => {
  console.error("Failed to start MCP server:", e);
  process.exit(1);
});
