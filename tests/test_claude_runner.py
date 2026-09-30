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
