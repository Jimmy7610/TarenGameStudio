from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import AgentRunRequest, AgentRunResult


class ClaudeCodeRunner:
    agent_id = "claude"
    role = "lead_engineer"

    def __init__(
        self,
        *,
        executable: str | None = None,
        workspace_root: str | Path | None = None,
        max_turns: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.executable = executable or os.getenv("TGS_CLAUDE_BIN", "claude")
        self.workspace_root = Path(
            workspace_root or os.getenv("TGS_WORKSPACE_ROOT", "/srv/taren/game-studio/workspaces")
        )
        self.max_turns = max_turns or int(os.getenv("TGS_CLAUDE_MAX_TURNS", "8"))
        self.timeout_seconds = timeout_seconds or int(os.getenv("TGS_CLAUDE_TIMEOUT_SECONDS", "900"))

    def _workspace(self, request: AgentRunRequest) -> Path:
        project_id = str(request.context_package.get("project_id") or "unscoped")
        path = self.workspace_root / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _prompt(request: AgentRunRequest) -> str:
        context = json.dumps(request.context_package, ensure_ascii=False, indent=2, default=str)
        writable = any(action in request.allowed_actions for action in ("write", "edit"))
        bash_allowed = "bash" in request.allowed_actions
        mutation_rule = (
            "- You may create and edit source files required to satisfy the objective."
            if writable
            else "- This is an analysis/review phase. Do not create, edit, rename, or delete any files."
        )
        bash_rule = (
            "- Bash is allowed only for commands needed to build/test files in this workspace. Do not install packages, use sudo, access the network, or touch paths outside the workspace."
            if bash_allowed
            else "- Bash is not allowed in this phase."
        )
        return f"""You are Claude Code acting as Lead Engineer inside Taren Game Studio.

OBJECTIVE
{request.objective}

RUN ID
{request.run_id}

CONTEXT
{context}

WORKSPACE RULES
- Work only inside the current working directory.
- Do not access, modify, or inspect files outside the current working directory.
- Do not use network access.
- Do not publish, deploy, spend money, create accounts, or perform external actions.
{mutation_rule}
{bash_rule}
- Keep the implementation deliberately small, reviewable, and reproducible.
- Follow the owner instruction and supplied design/dependency context exactly. Do not substitute a different game or platform unless the context explicitly approves it.
- Do not claim that a build, test, or playable check passed unless you actually performed it.
- Finish with a concise summary of exactly what you changed and any remaining risks.
- On the final line, output exactly one machine-readable marker:
  TGS_VERIFICATION: {{"build_ran": true|false, "build_passed": true|false, "tests_ran": true|false, "tests_passed": true|false, "playable_verified": true|false}}

"""

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        if shutil.which(self.executable) is None:
            raise RuntimeError(f"Claude Code executable not found: {self.executable}")

        workspace = self._workspace(request)
        tool_map = {
            "read": "Read",
            "write": "Write",
            "edit": "Edit",
            "glob": "Glob",
            "grep": "Grep",
            "bash": "Bash",
        }
        allowed_tools = [tool_map[action] for action in request.allowed_actions if action in tool_map]
        if not allowed_tools:
            allowed_tools = ["Read", "Glob", "Grep"]

        cmd = [
            self.executable,
            "-p",
            self._prompt(request),
            "--output-format",
            "json",
            "--max-turns",
            str(self.max_turns),
            "--allowedTools",
            *allowed_tools,
        ]
        if "bash" not in request.allowed_actions:
            cmd.extend(["--disallowedTools", "Bash"])

        completed = subprocess.run(
            cmd,
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
            env=os.environ.copy(),
        )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                f"Claude Code failed with exit code {completed.returncode}: {detail[-2000:]}"
            )

        try:
            payload: dict[str, Any] = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Claude Code returned invalid JSON") from exc

        if payload.get("is_error") or payload.get("subtype") not in (None, "success"):
            raise RuntimeError(f"Claude Code reported an error: {payload}")

        summary = str(payload.get("result") or "").strip()
        if not summary:
            raise RuntimeError("Claude Code returned no result text")

        verification: dict[str, Any] = {}
        match = re.search(r"TGS_VERIFICATION:\s*(\{.*\})\s*$", summary, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    verification = parsed
            except json.JSONDecodeError:
                verification = {}

        artifacts = tuple(
            {
                "type": "workspace",
                "ref": str(path.relative_to(workspace)),
            }
            for path in sorted(workspace.rglob("*"))
            if path.is_file()
        )

        return AgentRunResult(
            status="completed",
            summary=summary,
            artifacts=artifacts,
            verification=verification,
        )
