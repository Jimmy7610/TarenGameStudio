from __future__ import annotations

import json
import subprocess

from runners import AgentRunRequest, CodexRunner


def _jsonl_message(text: str) -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "test-thread"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}}),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def test_codex_runner_invokes_noninteractive_read_only_json_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.codex.shutil.which", lambda _: "/usr/bin/codex")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=_jsonl_message(
                'No blocking defects.\nTGS_REVIEW: {"status":"approved","findings":[],"needs_meeting":false}'
            ),
            stderr="",
        )

    monkeypatch.setattr("runners.codex.subprocess.run", fake_run)
    runner = CodexRunner(executable="codex", workspace_root=tmp_path)
    result = runner.run(
        AgentRunRequest(
            run_id="review-1",
            agent="codex",
            role="engineering_review",
            objective="Review the first playable",
            context_package={"project_id": "project-1", "task_id": "task-1"},
            allowed_actions=("read", "glob", "grep"),
        )
    )

    assert result.status == "completed"
    assert result.summary.startswith("No blocking defects")
    assert result.findings == ()
    assert seen["cwd"] == tmp_path / "project-1"
    cmd = seen["cmd"]
    assert cmd[:4] == ["codex", "--ask-for-approval", "never", "exec"]
    assert "--json" in cmd
    assert "--skip-git-repo-check" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"


def test_codex_runner_parses_structured_findings(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.codex.shutil.which", lambda _: "/usr/bin/codex")

    def fake_run(cmd, **kwargs):
        marker = {
            "status": "changes_requested",
            "findings": [
                {
                    "severity": "high",
                    "title": "Ball can escape playfield",
                    "detail": "Clamp the reset position before accepting the build.",
                }
            ],
            "needs_meeting": True,
        }
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=_jsonl_message("Review complete.\nTGS_REVIEW: " + json.dumps(marker)),
            stderr="",
        )

    monkeypatch.setattr("runners.codex.subprocess.run", fake_run)
    runner = CodexRunner(executable="codex", workspace_root=tmp_path)
    result = runner.run(
        AgentRunRequest(
            run_id="review-2",
            agent="codex",
            role="engineering_review",
            objective="Review",
            context_package={"project_id": "project-2"},
            allowed_actions=("read",),
        )
    )

    assert len(result.findings) == 1
    assert result.findings[0]["severity"] == "high"
    assert result.needs_meeting is True


def test_codex_runner_uses_workspace_write_only_when_requested(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.codex.shutil.which", lambda _: "/usr/bin/codex")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=_jsonl_message(
                'Done.\nTGS_REVIEW: {"status":"approved","findings":[],"needs_meeting":false}'
            ),
            stderr="",
        )

    monkeypatch.setattr("runners.codex.subprocess.run", fake_run)
    runner = CodexRunner(executable="codex", workspace_root=tmp_path)
    runner.run(
        AgentRunRequest(
            run_id="review-write",
            agent="codex",
            role="engineering_review",
            objective="Apply a review fix",
            context_package={"project_id": "project-write"},
            allowed_actions=("read", "write", "edit"),
        )
    )

    cmd = seen["cmd"]
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"


def test_codex_runner_fails_cleanly_when_cli_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("runners.codex.shutil.which", lambda _: None)
    runner = CodexRunner(executable="codex", workspace_root=tmp_path)

    try:
        runner.run(
            AgentRunRequest(
                run_id="review-missing",
                agent="codex",
                role="engineering_review",
                objective="Review",
                context_package={"project_id": "project-missing"},
            )
        )
    except RuntimeError as exc:
        assert "executable not found" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
