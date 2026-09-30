from __future__ import annotations

import json
import subprocess

from runners import AgentRunRequest, ClaudeCodeRunner


def test_claude_code_runner_invokes_noninteractive_json_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.claude_code.shutil.which", lambda _: "/usr/bin/claude")

    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs["cwd"]
        (kwargs["cwd"] / "pong.txt").write_text("real runner artifact", encoding="utf-8")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "Implemented the requested first playable files.",
                    "session_id": "test-session",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("runners.claude_code.subprocess.run", fake_run)

    runner = ClaudeCodeRunner(executable="claude", workspace_root=tmp_path, max_turns=3)
    result = runner.run(
        AgentRunRequest(
            run_id="run-1",
            agent="claude",
            role="lead_engineer",
            objective="Implement first playable",
            context_package={"project_id": "project-123", "task_id": "task-1"},
            allowed_actions=("read", "write", "edit", "glob", "grep"),
        )
    )

    assert result.status == "completed"
    assert result.summary.startswith("Implemented")
    assert {"type": "workspace", "ref": "pong.txt"} in result.artifacts
    assert seen["cwd"] == tmp_path / "project-123"
    assert "-p" in seen["cmd"]
    assert "--output-format" in seen["cmd"]
    assert "json" in seen["cmd"]
    assert "--max-turns" in seen["cmd"]
    assert "--allowedTools" in seen["cmd"]
    assert "--disallowedTools" in seen["cmd"]
    assert "Bash" in seen["cmd"]


def test_claude_code_runner_fails_cleanly_when_cli_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.claude_code.shutil.which", lambda _: None)
    runner = ClaudeCodeRunner(executable="claude", workspace_root=tmp_path)

    try:
        runner.run(
            AgentRunRequest(
                run_id="run-2",
                agent="claude",
                role="lead_engineer",
                objective="Test",
                context_package={"project_id": "project-123"},
            )
        )
    except RuntimeError as exc:
        assert "executable not found" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_claude_code_runner_read_only_phase_excludes_write_tools(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.claude_code.shutil.which", lambda _: "/usr/bin/claude")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "Analysis only.",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("runners.claude_code.subprocess.run", fake_run)

    runner = ClaudeCodeRunner(executable="claude", workspace_root=tmp_path)
    result = runner.run(
        AgentRunRequest(
            run_id="run-ro",
            agent="claude",
            role="lead_engineer",
            objective="Analyze only",
            context_package={"project_id": "project-ro"},
            allowed_actions=("read", "glob", "grep"),
        )
    )

    assert result.summary == "Analysis only."
    cmd = seen["cmd"]
    allowed_index = cmd.index("--allowedTools")
    disallowed_index = cmd.index("--disallowedTools")
    tools = cmd[allowed_index + 1:disallowed_index]
    assert "Read" in tools
    assert "Glob" in tools
    assert "Grep" in tools
    assert "Write" not in tools
    assert "Edit" not in tools


def test_claude_code_runner_parses_verification_marker(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.claude_code.shutil.which", lambda _: "/usr/bin/claude")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": (
                        "Built and tested.\n"
                        'TGS_VERIFICATION: {"build_ran": true, "build_passed": true, '
                        '"tests_ran": true, "tests_passed": true, "playable_verified": true}'
                    ),
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("runners.claude_code.subprocess.run", fake_run)
    runner = ClaudeCodeRunner(executable="claude", workspace_root=tmp_path)

    result = runner.run(
        AgentRunRequest(
            run_id="run-v",
            agent="claude",
            role="lead_engineer",
            objective="Implement",
            context_package={"project_id": "project-v"},
            allowed_actions=("read", "write", "edit", "glob", "grep", "bash"),
        )
    )

    assert result.verification["build_ran"] is True
    assert result.verification["build_passed"] is True
    assert result.verification["playable_verified"] is True


def test_claude_code_runner_allows_bash_only_when_requested(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.claude_code.shutil.which", lambda _: "/usr/bin/claude")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": 'Done.\nTGS_VERIFICATION: {"build_ran": false, "build_passed": false, "tests_ran": false, "tests_passed": false, "playable_verified": false}',
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("runners.claude_code.subprocess.run", fake_run)
    runner = ClaudeCodeRunner(executable="claude", workspace_root=tmp_path)
    runner.run(
        AgentRunRequest(
            run_id="run-bash",
            agent="claude",
            role="lead_engineer",
            objective="Implement",
            context_package={"project_id": "project-bash"},
            allowed_actions=("read", "write", "edit", "glob", "grep", "bash"),
        )
    )

    cmd = seen["cmd"]
    allowed_index = cmd.index("--allowedTools")
    disallowed_index = cmd.index("--disallowedTools")
    tools = cmd[allowed_index + 1:disallowed_index]
    assert "Bash" in tools
