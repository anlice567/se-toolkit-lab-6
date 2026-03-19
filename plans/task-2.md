# Task 2: The Documentation Agent

## Overview

Build an agentic loop that allows the LLM to call tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with source references.

## Tool Schemas

### read_file

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required) — relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message if file doesn't exist.

**Schema for LLM:**
```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file at the specified path",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

### list_files

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required) — relative directory path from project root

**Returns:** Newline-separated listing of entries.

**Schema for LLM:**
```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List files and directories at the specified path",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative directory path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

## Agentic Loop

```
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

## Path Security

**Goal:** Prevent access to files outside project directory.

**Implementation:**
- Resolve the full path using `Path.resolve()`
- Check that resolved path starts with project root
- Reject paths containing `..` or absolute paths
- Return error message for invalid paths

**Example:**
```python
def validate_path(path: str) -> bool:
    full_path = (project_root / path).resolve()
    return str(full_path).startswith(str(project_root))
```

## System Prompt Strategy

The system prompt should instruct the LLM to:

1. Use `list_files` to discover files in the `wiki/` directory
2. Use `read_file` to read relevant files and find the answer
3. Include the source reference (file path + section anchor) in the final answer
4. Stop after finding the answer (max 10 tool calls)

**Example system prompt:**
```
You are a documentation assistant. You have access to two tools:
- list_files: List files in a directory
- read_file: Read contents of a file

To answer questions:
1. First use list_files to explore the wiki/ directory
2. Use read_file to read relevant files
3. Find the answer and cite the source (file path + section anchor)
4. Respond with the answer and source

Always include the source field in your final answer.
Maximum 10 tool calls per question.
```

## Output Format

```json
{
  "answer": "...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Testing

Two regression tests:

1. **"How do you resolve a merge conflict?"**
   - Expected: `read_file` in tool_calls
   - Expected: `wiki/git-workflow.md` in source

2. **"What files are in the wiki?"**
   - Expected: `list_files` in tool_calls
