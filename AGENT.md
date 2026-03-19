# Agent Architecture

## Overview

This agent is a CLI tool that calls an LLM to answer questions. In Task 2, the agent gained tool-calling capabilities (`read_file`, `list_files`) and an agentic loop to navigate the project wiki.

## LLM Provider

**Provider:** OpenRouter  
**Model:** `meta-llama/llama-3.3-70b-instruct:free`  
**API:** OpenAI-compatible chat completions API with function calling

### Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | OpenRouter API key |
| `LLM_API_BASE` | API base URL (`https://openrouter.ai/api/v1`) |
| `LLM_MODEL` | Model name (`meta-llama/llama-3.3-70b-instruct:free`) |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Arg   │ ──→ │  Env Loader  │ ──→ │ Agentic     │ ──→ │   LLM API   │
│  (question) │     │ (.env file)  │     │ Loop        │     │  (OpenRouter)│
└─────────────┘     └──────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ↓
                    ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
                    │ JSON Output  │ ←── │   Parser    │ ←── │  Response   │
                    │  (stdout)    │     │             │     │  + Tools    │
                    └──────────────┘     └─────────────┘     └─────────────┘
```

## Tools

The agent has two tools registered as function-calling schemas:

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
- Only lists directories, not files

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

1. Use `list_files` to discover files in the `wiki/` directory
2. Use `read_file` to read relevant files
3. Find the answer and cite the source (file path + section anchor)
4. Stop after finding the answer (max 10 tool calls)

## Output Format

```json
{
  "answer": "Representational State Transfer.",
  "source": "wiki/rest-api.md#what-is-rest",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\nrest-api.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/rest-api.md"},
      "result": "# REST API\n\nREST stands for..."
    }
  ]
}
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error to stderr |
| Missing API key | Exit with error to stderr |
| Network error | Exit with error to stderr |
| Invalid response | Exit with error to stderr |
| Path traversal attempt | Return error message in tool result |
| Max iterations reached | Return partial answer |

## Dependencies

- `httpx` — HTTP client for API requests
- Standard library: `json`, `os`, `sys`, `pathlib`, `re`

## Testing

Run the regression tests:

```bash
pytest backend/tests/unit/test_agent.py
```

Tests verify:

- Agent outputs valid JSON with `answer`, `source`, `tool_calls`
- `read_file` is called for documentation questions
- `list_files` is called for directory listing questions
- Source references are extracted correctly

## Security

Path validation prevents access to files outside the project directory:

1. Reject absolute paths
2. Reject paths containing `..`
3. Resolve path and verify it starts with project root

## Limitations

- Free tier OpenRouter has 50 requests/day limit
- Maximum 10 tool calls per question
- Only accesses files in project directory
- No web search or external knowledge
