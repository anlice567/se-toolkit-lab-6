"""Regression tests for agent.py CLI."""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json() -> None:
    """Test that agent.py outputs valid JSON with required fields."""
    project_root = Path(__file__).parent.parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields
    assert "answer" in output, "Missing 'answer' field"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"


def test_documentation_agent_uses_read_file() -> None:
    """Test that agent uses read_file tool for documentation questions."""
    project_root = Path(__file__).parent.parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "How do you resolve a merge conflict?",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Verify read_file was used
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Verify source contains wiki path
    assert "wiki/" in output["source"] or "git" in output["source"].lower(), (
        f"Expected wiki path in source, got: {output['source']}"
    )


def test_documentation_agent_uses_list_files() -> None:
    """Test that agent uses list_files tool for directory questions."""
    project_root = Path(__file__).parent.parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "What files are in the wiki directory?",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Verify list_files was used
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"
