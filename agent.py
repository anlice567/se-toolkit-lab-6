#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns structured JSON response.

Usage:
    uv run agent.py "Your question here"

Output:
    {"answer": "...", "source": "...", "tool_calls": [...]}
"""

import json
import os
import sys
from pathlib import Path

import httpx


# Project root for security checks
PROJECT_ROOT = Path(__file__).parent.resolve()


def validate_path(path: str) -> tuple[bool, str]:
    """
    Validate that path doesn't escape project directory.

    Returns (is_valid, error_message).
    """
    # Reject absolute paths
    if Path(path).is_absolute():
        return False, "Absolute paths are not allowed"

    # Reject paths with ..
    if ".." in path:
        return False, "Path traversal is not allowed"

    # Resolve and check
    try:
        full_path = (PROJECT_ROOT / path).resolve()
        if not str(full_path).startswith(str(PROJECT_ROOT)):
            return False, "Path escapes project directory"
    except Exception as e:
        return False, f"Invalid path: {e}"

    return True, ""


def read_file(path: str) -> str:
    """Read contents of a file at the specified path."""
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    try:
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        with open(full_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at the specified path."""
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    try:
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            return f"Error: Path not found: {path}"
        if not full_path.is_dir():
            return f"Error: Not a directory: {path}"

        entries = []
        for entry in sorted(full_path.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


def get_tool_schemas() -> list[dict]:
    """Return tool schemas for OpenRouter function calling."""
    return [
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
                            "description": "Relative path from project root (e.g., wiki/git-workflow.md)",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
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
                            "description": "Relative directory path from project root (e.g., wiki/)",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
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
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                        },
                        "path": {
                            "type": "string",
                            "description": "API path (e.g., /items/, /analytics/completion-rate)",
                        },
                        "body": {
                            "type": "string",
                            "description": "JSON request body for POST/PUT requests (optional)",
                        },
                    },
                    "required": ["method", "path"],
                },
            },
        },
    ]


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return its result."""
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    elif tool_name == "query_api":
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
        )
    else:
        return f"Error: Unknown tool: {tool_name}"


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        sys.exit(1)

    env = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def load_docker_env() -> dict[str, str]:
    """Load LMS_API_KEY from .env.docker.secret."""
    env_file = Path(__file__).parent / ".env.docker.secret"
    if not env_file.exists():
        return {}

    env = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the backend API with authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., /items/)
        body: Optional JSON request body

    Returns:
        JSON string with status_code and body, or error message
    """
    # Load configuration
    docker_env = load_docker_env()
    agent_env = load_env()

    lms_api_key = docker_env.get("LMS_API_KEY", "")
    api_base = agent_env.get("AGENT_API_BASE_URL", "http://localhost:42002")

    # Build URL
    url = f"{api_base}{path}"

    # Build headers
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": lms_api_key,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            if method == "GET":
                response = client.get(url, headers=headers)
            elif method == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return f"Error: Unknown method: {method}"

            # Return response as JSON string
            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            return json.dumps(result)
    except httpx.HTTPError as e:
        return f"Error: API request failed: {e}"
    except Exception as e:
        return f"Error: {e}"


def call_llm(
    messages: list[dict],
    api_key: str,
    api_base: str,
    model: str,
    tools: list[dict] | None = None,
) -> dict:
    """Call the LLM API and return the full response."""
    url = f"{api_base}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # OpenRouter headers
        "HTTP-Referer": "https://github.com/anlice567/se-toolkit-lab-6",
        "X-Title": "Documentation Agent",
    }

    payload: dict = {
        "model": model,
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]


def extract_source_from_content(content: str) -> str:
    """Extract source reference from LLM response."""
    # Try to find file references in the content
    import re

    # Look for patterns like wiki/something.md or wiki/something.md#section
    pattern = r"(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)"
    match = re.search(pattern, content)
    if match:
        return match.group(1)

    return "unknown"


def run_agentic_loop(
    question: str,
    api_key: str,
    api_base: str,
    model: str,
) -> tuple[str, str, list[dict]]:
    """
    Run the agentic loop with tool calling.

    Returns (answer, source, tool_calls).
    """
    # System prompt
    system_prompt = """You are a documentation and system assistant with access to three tools:
- list_files: List files in a directory
- read_file: Read contents of a file
- query_api: Call the backend API (for system facts and data queries)

Tool selection guide:
- Use list_files/read_file for:
  - Wiki documentation questions
  - Source code questions
  - Configuration file questions
- Use query_api for:
  - Checking HTTP status codes
  - Querying database counts (e.g., number of items)
  - Testing API endpoints
  - Diagnosing API errors
  - System facts (framework, ports, etc.)

Always cite sources:
- For wiki: wiki/filename.md#section
- For source code: path/to/file.py
- For API: the endpoint path (e.g., GET /items/)
- For system facts: indicate it's from the running system

Maximum 10 tool calls per question.
"""

    # Initialize messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    # Get tool schemas
    tools = get_tool_schemas()

    # Track all tool calls
    all_tool_calls: list[dict] = []
    max_iterations = 10

    for iteration in range(max_iterations):
        # Call LLM
        response = call_llm(messages, api_key, api_base, model, tools)

        # Check for tool calls
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - we have the final answer
            answer = response.get("content", "")
            source = extract_source_from_content(answer)
            return answer, source, all_tool_calls

        # Execute each tool call
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            tool_name = func.get("name", "unknown")

            # Parse arguments
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            # Execute tool
            result = execute_tool(tool_name, args)

            # Record the tool call
            tool_record = {
                "tool": tool_name,
                "args": args,
                "result": result,
            }
            all_tool_calls.append(tool_record)

            # Add tool response to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": result,
                }
            )

    # Max iterations reached
    answer = "Maximum tool calls reached. Partial answer may be incomplete."
    source = "unknown"
    return answer, source, all_tool_calls


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    env = load_env()
    api_key = env.get("LLM_API_KEY")
    api_base = env.get("LLM_API_BASE")
    model = env.get("LLM_MODEL")

    if not api_key:
        print("Error: LLM_API_KEY not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    if not api_base:
        print("Error: LLM_API_BASE not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    # Run agentic loop
    try:
        answer, source, tool_calls = run_agentic_loop(
            question, api_key, api_base, model
        )
    except httpx.HTTPError as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Output structured JSON
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
