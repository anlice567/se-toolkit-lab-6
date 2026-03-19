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
    ]


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return its result."""
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
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
    system_prompt = """You are a documentation assistant with access to two tools:
- list_files: List files in a directory
- read_file: Read contents of a file

To answer questions:
1. Use list_files to explore the wiki/ directory structure
2. Use read_file to read relevant files and find the answer
3. Include the source reference (file path + section anchor like #heading) in your final answer
4. Maximum 10 tool calls per question

Always provide a source reference in your final answer.
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
