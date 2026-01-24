import express from 'express';
import axios from 'axios';

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL;
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN;

if (!BACKEND_BASE_URL) {
  console.error('ERROR: BACKEND_BASE_URL environment variable is required');
  process.exit(1);
}

// Middleware
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'yumyummy-mcp-server' });
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

// MCP handler function
async function handleMCPRequest(req, res) {
  try {
    const { method, params } = req.body;

    if (!method) {
      return res.status(400).json({ 
        error: 'Missing "method" field in request body' 
      });
    }

    // Handle listTools
    if (method === 'listTools') {
      return res.json({
        tools: [getDayContextTool]
      });
    }

    // Handle callTool
    if (method === 'callTool') {
      if (!params || !params.name) {
        return res.status(400).json({ 
          error: 'Missing "params.name" field. Expected: { name: string, arguments: object }' 
        });
      }

      const toolName = params.name;
      const toolArgs = params.arguments || {};

      if (toolName === 'get_day_context') {
        // Validate input
        if (typeof toolArgs.user_id !== 'number' || typeof toolArgs.day !== 'string') {
          return res.status(400).json({ 
            error: 'Invalid arguments. Expected: { user_id: number, day: string (YYYY-MM-DD) }' 
          });
        }

        // Validate date format
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(toolArgs.day)) {
          return res.status(400).json({ 
            error: 'Invalid date format. Expected YYYY-MM-DD' 
          });
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
          return res.json({
            content: [
              {
                type: 'text',
                text: JSON.stringify(response.data, null, 2)
              }
            ]
          });
        } catch (error) {
          if (error.response) {
            // Backend returned an error status
            return res.status(500).json({
              error: `Backend error: ${error.response.status}`,
              message: error.response.data?.detail || error.response.data?.message || 'Unknown error'
            });
          } else if (error.request) {
            // Request was made but no response received
            return res.status(500).json({
              error: 'Backend unreachable',
              message: 'Could not connect to backend server'
            });
          } else {
            // Error setting up request
            return res.status(500).json({
              error: 'Request setup error',
              message: error.message
            });
          }
        }
      } else {
        return res.status(400).json({ 
          error: `Unknown tool: ${toolName}. Supported tools: get_day_context` 
        });
      }
    }

    // Unknown method
    return res.status(400).json({ 
      error: `Unknown method: ${method}. Supported methods: listTools, callTool` 
    });

  } catch (error) {
    console.error('Error processing MCP request:', error);
    return res.status(500).json({ 
      error: 'Internal server error',
      message: error.message 
    });
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
