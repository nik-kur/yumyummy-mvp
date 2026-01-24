# YumYummy MCP Server

MCP (Model Context Protocol) server for OpenAI Agent Builder. Provides DB tools for accessing YumYummy meal data.

## Features

- **get_day_context** tool: Get meal entries and totals for a specific day
  - Input: `{ user_id: number, day: string (YYYY-MM-DD) }`
  - Output: JSON response from backend `/day/{user_id}/{day}` endpoint

## Environment Variables

Required:
- `BACKEND_BASE_URL` - Base URL of the YumYummy backend API (e.g., `https://your-backend.onrender.com`)

Optional:
- `INTERNAL_API_TOKEN` - Token for X-Internal-Token header (if backend requires authentication)
- `PORT` - Server port (defaults to 3000)

## Deployment on Render

### 1. Create a new Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select the repository and branch

### 2. Configure Build Settings

- **Name**: `yumyummy-mcp-server` (or your preferred name)
- **Environment**: `Node`
- **Root Directory**: `mcp-server`
- **Build Command**: `npm install`
- **Start Command**: `npm start`

### 3. Set Environment Variables

In the Render dashboard, go to "Environment" tab and add:

```
BACKEND_BASE_URL=https://your-backend.onrender.com
INTERNAL_API_TOKEN=your-secret-token-here
PORT=10000
```

**Note**: Render automatically sets `PORT` environment variable, but you can override it if needed.

### 4. Deploy

Click "Create Web Service" and wait for deployment to complete.

### 5. Get MCP Server URL

After deployment, Render will provide a URL like:
```
https://yumyummy-mcp-server.onrender.com
```

Use this URL in OpenAI Agent Builder as your MCP server endpoint:
```
https://yumyummy-mcp-server.onrender.com/mcp
```

## Local Development

1. Install dependencies:
```bash
cd mcp-server
npm install
```

2. Set environment variables:
```bash
export BACKEND_BASE_URL=http://localhost:8000
export INTERNAL_API_TOKEN=your-token-here  # optional
export PORT=3000  # optional
```

3. Start server:
```bash
npm start
```

4. Test health endpoint:
```bash
curl http://localhost:3000/health
```

5. Test MCP endpoint:
```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "get_day_context",
    "input": {
      "user_id": 1,
      "day": "2024-01-15"
    }
  }'
```

## MCP Protocol

The server implements a simplified MCP protocol:

**Request:**
```json
{
  "tool": "get_day_context",
  "input": {
    "user_id": 1,
    "day": "2024-01-15"
  }
}
```

**Response:**
```json
{
  "tool": "get_day_context",
  "output": {
    "user_id": 1,
    "date": "2024-01-15",
    "total_calories": 1850.0,
    "total_protein_g": 120.5,
    "total_fat_g": 65.0,
    "total_carbs_g": 210.0,
    "meals": [...]
  }
}
```

## Error Handling

The server returns appropriate HTTP status codes:
- `200` - Success
- `400` - Bad request (invalid input)
- `502` - Backend unreachable
- `500` - Internal server error

## Health Check

The server exposes a `/health` endpoint for monitoring:
```bash
curl https://your-mcp-server.onrender.com/health
```

Response:
```json
{
  "status": "ok",
  "service": "yumyummy-mcp-server"
}
```
