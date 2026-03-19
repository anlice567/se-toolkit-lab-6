# Task 3: The System Agent

## Overview

Add a `query_api` tool to the agent so it can query the deployed backend API and answer questions about system facts and data.

## Tool Schema: query_api

**Purpose:** Call the deployed backend API with authentication.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (string, required) — API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`.

**Authentication:** Use `LMS_API_KEY` from `.env.docker.secret` in the `X-API-Key` header.

**Schema for LLM:**
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the backend API with authentication. Use for querying system data, checking status codes, and diagnosing API errors.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, PUT, DELETE)",
          "enum": ["GET", "POST", "PUT", "DELETE"]
        },
        "path": {
          "type": "string",
          "description": "API path (e.g., /items/, /analytics/completion-rate)"
        },
        "body": {
          "type": "string",
          "description": "JSON request body for POST/PUT requests (optional)"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

## Environment Variables

The agent reads configuration from two files:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (optional) | `.env.agent.secret`, defaults to `http://localhost:42002` |

**Important:** Never hardcode these values. The autochecker injects its own credentials.

## Implementation Plan

### 1. Add query_api tool function

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the backend API with authentication."""
    # Load LMS_API_KEY from .env.docker.secret
    # Build URL from AGENT_API_BASE_URL
    # Send request with X-API-Key header
    # Return JSON response with status_code and body
```

### 2. Add tool to schemas

Update `get_tool_schemas()` to include `query_api`.

### 3. Update execute_tool()

Add handler for `query_api` tool.

### 4. Update system prompt

Instruct LLM when to use each tool:
- **wiki questions** → `list_files`, `read_file`
- **system facts** → `query_api` (e.g., status codes, endpoints)
- **data queries** → `query_api` (e.g., item count)
- **source code questions** → `read_file`

### 5. Update output format

Make `source` field optional (system questions may not have wiki source).

## Security Considerations

- `query_api` should only call the configured `AGENT_API_BASE_URL`
- Authentication via `X-API-Key` header (not query params)
- No path traversal issues (API paths are validated by backend)

## System Prompt Strategy

```
You are a documentation and system assistant with access to three tools:
- list_files: List files in a directory
- read_file: Read contents of a file
- query_api: Call the backend API (for system facts and data queries)

Tool selection guide:
- Use list_files/read_file for wiki documentation and source code questions
- Use query_api for:
  - Checking HTTP status codes
  - Querying database counts
  - Testing API endpoints
  - Diagnosing API errors

Always cite sources:
- For wiki: wiki/filename.md#section
- For source code: path/to/file.py:line
- For API: the endpoint path (e.g., GET /items/)

Maximum 10 tool calls per question.
```

## Testing

Two new regression tests:

1. **"What framework does the backend use?"**
   - Expected: `read_file` in tool_calls
   - Expected: answer contains "FastAPI"

2. **"How many items are in the database?"**
   - Expected: `query_api` in tool_calls
   - Expected: answer contains a number > 0

## Benchmark Iteration Strategy

1. Run `uv run run_eval.py`
2. For each failing question:
   - Check which tool was called (if any)
   - Check if tool arguments were correct
   - Check if tool result was parsed correctly
   - Fix system prompt or tool implementation
3. Re-run until all 10 questions pass

## Known Challenges

| Challenge | Potential Fix |
|-----------|---------------|
| LLM doesn't call query_api | Improve tool description, add examples to system prompt |
| query_api returns 401/403 | Check LMS_API_KEY loading, verify header name |
| API base URL wrong | Ensure AGENT_API_BASE_URL defaults to localhost:42002 |
| LLM times out | Reduce max iterations, use faster model |
| Answer close but wrong keywords | Adjust system prompt phrasing |

## Initial Benchmark Score

*(To be filled after first run)*

- Score: _/10
- First failures: [list questions]
- Iteration plan: [describe fixes]
