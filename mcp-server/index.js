import express from 'express';
import axios from 'axios';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL;
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN;

if (!BACKEND_BASE_URL) {
  console.error('ERROR: BACKEND_BASE_URL environment variable is required');
  process.exit(1);
}

// Middleware
app.use(cors({ origin: '*' }));
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'yumyummy-mcp-server' });
});

// MCP tools (GET fallback for platforms that probe via GET)
function getToolsResponse() {
  return {
    tools: [getDayContextTool]
  };
}

app.get('/', (req, res) => {
  res.json(getToolsResponse());
});

app.get('/mcp', (req, res) => {
  res.json(getToolsResponse());
});

// Tool definition
const getDayContextTool = {
  name: 'get_day_context',
  description: 'Get day nutrition summary from YumYummy backend',
  inputSchema: {
    type: 'object',
    properties: {
      user_id: {
        type: 'integer',
        description: 'User ID'
      },
      day: {
        type: 'string',
        description: 'Date in YYYY-MM-DD format'
      }
    },
    required: ['user_id', 'day']
  }
};

// JSON-RPC helpers
function jsonRpcResult(id, result) {
  return {
    jsonrpc: '2.0',
    id,
    result
  };
}

function jsonRpcError(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) {
    error.data = data;
  }
  return {
    jsonrpc: '2.0',
    id: id ?? null,
    error
  };
}

// MCP handler function (JSON-RPC 2.0)
async function handleMCPRequest(req, res) {
  try {
    const { jsonrpc, id, method, params } = req.body || {};

    if (!method) {
      return res.status(400).json(jsonRpcError(id, -32600, 'Invalid Request: missing method'));
    }

    // Accept both MCP and legacy method names for compatibility
    const normalizedMethod = method === 'listTools' ? 'tools/list'
      : method === 'callTool' ? 'tools/call'
      : method;

    // Handle tools/list
    if (normalizedMethod === 'tools/list') {
      return res.json(jsonRpcResult(id ?? 1, { tools: [getDayContextTool] }));
    }

    // Handle tools/call
    if (normalizedMethod === 'tools/call') {
      if (!params || !params.name) {
        return res.status(400).json(
          jsonRpcError(id, -32602, 'Invalid params: missing params.name')
        );
      }

      const toolName = params.name;
      const toolArgs = params.arguments || params.input || {};

      if (toolName === 'get_day_context') {
        // Validate input
        if (typeof toolArgs.user_id !== 'number' || typeof toolArgs.day !== 'string') {
          return res.status(400).json(
            jsonRpcError(
              id,
              -32602,
              'Invalid arguments. Expected: { user_id: number, day: string (YYYY-MM-DD) }'
            )
          );
        }

        // Validate date format
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(toolArgs.day)) {
          return res.status(400).json(
            jsonRpcError(id, -32602, 'Invalid date format. Expected YYYY-MM-DD')
          );
        }

        // Build request URL
        const url = `${BACKEND_BASE_URL}/day/${toolArgs.user_id}/${toolArgs.day}`;

        // Prepare headers
        const headers = {};
        if (INTERNAL_API_TOKEN) {
          headers['X-Internal-Token'] = INTERNAL_API_TOKEN;
        }

        // Make request to backend
        try {
          const response = await axios.get(url, { headers });
          return res.json(
            jsonRpcResult(id ?? 1, {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(response.data)
                }
              ]
            })
          );
        } catch (error) {
          if (error.response) {
            return res.status(500).json(
              jsonRpcError(
                id,
                -32000,
                `Backend error: ${error.response.status}`,
                error.response.data
              )
            );
          }
          if (error.request) {
            return res.status(500).json(
              jsonRpcError(id, -32001, 'Backend unreachable')
            );
          }
          return res.status(500).json(
            jsonRpcError(id, -32002, 'Request setup error', error.message)
          );
        }
      }

      return res.status(400).json(
        jsonRpcError(id, -32601, `Unknown tool: ${toolName}`)
      );
    }

    // Unknown method
    return res.status(400).json(
      jsonRpcError(id, -32601, `Unknown method: ${method}`)
    );
  } catch (error) {
    console.error('Error processing MCP request:', error);
    return res.status(500).json(
      jsonRpcError(null, -32603, 'Internal error', error.message)
    );
  }
}

// MCP endpoints - both root and /mcp
app.post('/', handleMCPRequest);
app.post('/mcp', handleMCPRequest);

// Start server
app.listen(PORT, () => {
  console.log(`MCP server listening on port ${PORT}`);
  console.log(`Backend URL: ${BACKEND_BASE_URL}`);
  console.log(`Internal token: ${INTERNAL_API_TOKEN ? 'configured' : 'not set'}`);
});
