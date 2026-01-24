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

// MCP endpoint
app.post('/mcp', async (req, res) => {
  try {
    const { tool, input } = req.body;

    if (!tool) {
      return res.status(400).json({ error: 'Missing "tool" field in request body' });
    }

    if (tool === 'get_day_context') {
      // Validate input
      if (!input || typeof input.user_id !== 'number' || typeof input.day !== 'string') {
        return res.status(400).json({ 
          error: 'Invalid input. Expected: { user_id: number, day: string (YYYY-MM-DD) }' 
        });
      }

      // Validate date format
      const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
      if (!dateRegex.test(input.day)) {
        return res.status(400).json({ 
          error: 'Invalid date format. Expected YYYY-MM-DD' 
        });
      }

      // Build request URL
      const url = `${BACKEND_BASE_URL}/day/${input.user_id}/${input.day}`;

      // Prepare headers
      const headers = {};
      if (INTERNAL_API_TOKEN) {
        headers['X-Internal-Token'] = INTERNAL_API_TOKEN;
      }

      // Make request to backend
      try {
        const response = await axios.get(url, { headers });
        return res.json({
          tool: 'get_day_context',
          output: response.data
        });
      } catch (error) {
        if (error.response) {
          // Backend returned an error status
          return res.status(error.response.status).json({
            error: `Backend error: ${error.response.status}`,
            message: error.response.data?.detail || error.response.data?.message || 'Unknown error'
          });
        } else if (error.request) {
          // Request was made but no response received
          return res.status(502).json({
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
        error: `Unknown tool: ${tool}. Supported tools: get_day_context` 
      });
    }
  } catch (error) {
    console.error('Error processing MCP request:', error);
    return res.status(500).json({ 
      error: 'Internal server error',
      message: error.message 
    });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`MCP server listening on port ${PORT}`);
  console.log(`Backend URL: ${BACKEND_BASE_URL}`);
  console.log(`Internal token: ${INTERNAL_API_TOKEN ? 'configured' : 'not set'}`);
});
