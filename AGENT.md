# Agent Architecture

## Overview

This agent is a CLI tool that calls an LLM to answer questions. In Task 3, the agent gained a `query_api` tool to query the deployed backend API, enabling it to answer questions about system facts and live data.

## LLM Provider

**Provider:** OpenRouter  
**Model:** `meta-llama/llama-3.3-70b-instruct:free`  
**API:** OpenAI-compatible chat completions API with function calling

### Configuration

The agent reads configuration from two environment files:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api | `.env.agent.secret`, defaults to `http://localhost:42002` |

**Important:** Never hardcode these values. The autochecker injects its own credentials.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Arg   │ ──→ │  Env Loader  │ ──→ │ Agentic     │ ──→ │   LLM API   │
│  (question) │     │ (.env files) │     │ Loop        │     │  (OpenRouter)│
└─────────────┘     └──────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ↓
                    ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
                    │ JSON Output  │ ←── │   Parser    │ ←── │  Response   │
                    │  (stdout)    │     │             │     │  + Tools    │
                    └──────────────┘     └─────────────┘     └─────────────┘
                                                  │
                                                  ↓
                                       ┌─────────────────────┐
                                       │  Backend API        │
                                       │  (query_api tool)   │
                                       └─────────────────────┘
```

## Tools

The agent has three tools registered as function-calling schemas:

### read_file

**Purpose:** Read contents of a file from the project repository.

**Parameters:**

- `path` (string) — relative path from project root

**Security:**

- Rejects absolute paths
- Rejects paths containing `..`
- Validates resolved path stays within project directory

### list_files

**Purpose:** List files and directories at a given path.

**Parameters:**

- `path` (string) — relative directory path from project root

**Security:**

- Same path validation as `read_file`

### query_api

**Purpose:** Call the deployed backend API with authentication.

**Parameters:**

- `method` (string) — HTTP method (GET, POST, PUT, DELETE)
- `path` (string) — API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT

**Authentication:**

- Uses `LMS_API_KEY` from `.env.docker.secret`
- Sends `X-API-Key` header with each request

**Returns:**

- JSON string with `status_code` and `body`

**Error handling:**

- Returns error message for network failures
- Returns error message for non-200 status codes

## Agentic Loop

```python
1. Send user question + tool schemas to LLM
2. Parse response:
   - If tool_calls present:
     a. Execute each tool call
     b. Append results as tool role messages
     c. Go to step 1 (max 10 iterations)
   - If text message (no tool calls):
     a. Extract answer and source
     b. Output JSON and exit
```

**Maximum iterations:** 10 tool calls per question.

## System Prompt Strategy

The system prompt instructs the LLM to:

1. **Use list_files/read_file for:**
   - Wiki documentation questions
   - Source code questions
   - Configuration file questions

2. **Use query_api for:**
   - Checking HTTP status codes
   - Querying database counts (e.g., number of items)
   - Testing API endpoints
   - Diagnosing API errors
   - System facts (framework, ports, etc.)

3. **Always cite sources:**
   - For wiki: `wiki/filename.md#section`
   - For source code: `path/to/file.py`
   - For API: the endpoint path (e.g., `GET /items/`)
   - For system facts: indicate it's from the running system

## Output Format

```json
{
  "answer": "There are 42 items in the database.",
  "source": "GET /items/",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

**Note:** `source` field is now optional for system questions that don't have a wiki source.

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error to stderr |
| Missing `LLM_API_KEY` | Exit with error to stderr |
| Network error (LLM) | Exit with error to stderr |
| Network error (API) | Return error in tool result |
| Path traversal attempt | Return error message in tool result |
| Max iterations reached | Return partial answer |
| Missing `LMS_API_KEY` | query_api returns unauthenticated error |

## Dependencies

- `httpx` — HTTP client for API requests
- Standard library: `json`, `os`, `sys`, `pathlib`, `re`

## Testing

Run the regression tests:

```bash
pytest tests/test_agent.py
```

Tests verify:

- Agent outputs valid JSON with `answer`, `source`, `tool_calls`
- `read_file` is called for documentation questions
- `list_files` is called for directory listing questions
- `query_api` is called for data queries
- `read_file` is called for source code questions (e.g., framework detection)

## Security

### Path Validation (read_file, list_files)

1. Reject absolute paths
2. Reject paths containing `..`
3. Resolve path and verify it starts with project root

### API Authentication (query_api)

1. Load `LMS_API_KEY` from `.env.docker.secret`
2. Send `X-API-Key` header with each request
3. Never expose key in logs or error messages

### Environment Variables

- Two distinct keys: `LLM_API_KEY` (LLM provider) vs `LMS_API_KEY` (backend API)
- Never commit `.env.*.secret` files to git
- Autochecker injects its own credentials at evaluation time

## Lessons Learned

### Challenge 1: Tool Selection

Initially, the LLM would call `read_file` for questions that required `query_api`.

**Fix:** Improved the system prompt with explicit tool selection guide, listing specific use cases for each tool.

### Challenge 2: API Authentication

The `query_api` tool initially returned 401 errors.

**Fix:** Ensured `LMS_API_KEY` is loaded from `.env.docker.secret` and sent as `X-API-Key` header.

### Challenge 3: Source Field

The `source` field was required even for system questions without a wiki source.

**Fix:** Made `source` optional and allow API endpoints as source values (e.g., `GET /items/`).

### Challenge 4: Environment Variables

Confusion between `LLM_API_KEY` and `LMS_API_KEY`.

**Fix:** Clear documentation and separate loading functions (`load_env` vs `load_docker_env`).

## Final Benchmark Score

*(To be filled after running run_eval.py)*

- Score: _/10
- Passed: [list questions]
- Failed: [list questions with fixes]

## Limitations

- Free tier OpenRouter has 50 requests/day limit
- Maximum 10 tool calls per question
- Only accesses files in project directory
- `query_api` only works when backend is running
- No web search or external knowledge
