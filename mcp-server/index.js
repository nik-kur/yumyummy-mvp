import express from "express";
import cors from "cors";
import axios from "axios";
import { randomUUID } from "crypto";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

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

// Store for transports (stateful mode for session management)
const transports = new Map();

// Create MCP server
function createMcpServer() {
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

  return mcp;
}

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "yumyummy-mcp-server" });
});

// MCP endpoint - handles both initialization and ongoing communication
app.post("/mcp", async (req, res) => {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_entry',message:'POST /mcp entry',data:{method:req.body?.method,hasParams:!!req.body?.params,accept:req.headers?.accept,contentType:req.headers?.['content-type'],sessionId:req.headers?.['mcp-session-id']},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'A'})}).catch(()=>{});
  // #endregion agent log
  console.log("MCP POST request:", JSON.stringify(req.body));
  console.log("Headers:", JSON.stringify(req.headers));

  try {
    // Check for existing session
    const sessionId = req.headers["mcp-session-id"];
    
    let transport;
    
    if (sessionId && transports.has(sessionId)) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_session_reuse',message:'Reusing existing MCP session',data:{sessionId,known:true},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})}).catch(()=>{});
      // #endregion agent log
      // Reuse existing transport
      transport = transports.get(sessionId);
    } else if (!sessionId && req.body?.method === "initialize") {
      // New session - create new transport and server
      const newSessionId = randomUUID();
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_session_create',message:'Creating new MCP session',data:{newSessionId,method:req.body?.method},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'C'})}).catch(()=>{});
      // #endregion agent log
      
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => newSessionId,
      });
      
      const mcp = createMcpServer();
      await mcp.connect(transport);
      
      transports.set(newSessionId, transport);
      
      console.log(`New MCP session created: ${newSessionId}`);
    } else if (!sessionId) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_no_session',message:'No session and not initialize',data:{method:req.body?.method},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})}).catch(()=>{});
      // #endregion agent log
      // No session and not initialize - error
      return res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "No session. Send initialize first." },
        id: null,
      });
    } else {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:post_session_missing',message:'Session id provided but not found',data:{sessionId},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})}).catch(()=>{});
      // #endregion agent log
      // Session ID provided but not found
      return res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Session not found" },
        id: null,
      });
    }

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
  fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:get_entry',message:'GET /mcp entry',data:{accept:req.headers?.accept,sessionId:req.headers?.['mcp-session-id']},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'A'})}).catch(()=>{});
  // #endregion agent log
  const sessionId = req.headers["mcp-session-id"];
  
  if (!sessionId || !transports.has(sessionId)) {
    return res.status(400).json({
      jsonrpc: "2.0",
      error: { code: -32000, message: "Invalid or missing session" },
      id: null,
    });
  }
  
  const transport = transports.get(sessionId);
  await transport.handleRequest(req, res);
});

// Handle DELETE for session cleanup
app.delete("/mcp", async (req, res) => {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4fe014b3-6723-4d28-a73e-d62e1df8347b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'mcp-server/index.js:delete_entry',message:'DELETE /mcp entry',data:{sessionId:req.headers?.['mcp-session-id']},timestamp:Date.now(),sessionId:'debug-session',runId:'pre-fix',hypothesisId:'B'})}).catch(()=>{});
  // #endregion agent log
  const sessionId = req.headers["mcp-session-id"];
  
  if (sessionId && transports.has(sessionId)) {
    const transport = transports.get(sessionId);
    await transport.close();
    transports.delete(sessionId);
    console.log(`Session ${sessionId} closed`);
  }
  
  res.status(204).send();
});

// Start server
app.listen(PORT, () => {
  console.log(`MCP server listening on port ${PORT}`);
  console.log(`Backend URL: ${BACKEND_BASE_URL}`);
  console.log(`Internal token: ${INTERNAL_API_TOKEN ? "configured" : "not set"}`);
});
