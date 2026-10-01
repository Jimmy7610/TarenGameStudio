from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import AgentRunRequest, AgentRunResult


class CodexRunner:
    agent_id = "codex"
    role = "engineering_review"

    def __init__(
        self,
        *,
        executable: str | None = None,
        workspace_root: str | Path | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.executable = executable or os.getenv("TGS_CODEX_BIN", "codex")
        self.workspace_root = Path(
            workspace_root or os.getenv("TGS_WORKSPACE_ROOT", "/srv/taren/game-studio/workspaces")
        )
        self.timeout_seconds = timeout_seconds or int(os.getenv("TGS_CODEX_TIMEOUT_SECONDS", "900"))

    def _workspace(self, request: AgentRunRequest) -> Path:
        project_id = str(request.context_package.get("project_id") or "unscoped")
        path = self.workspace_root / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _prompt(request: AgentRunRequest) -> str:
        context = json.dumps(request.context_package, ensure_ascii=False, indent=2, default=str)
        writable = any(action in request.allowed_actions for action in ("write", "edit"))
        mutation_rule = (
            "- You may modify files only when the objective explicitly requires implementation work."
            if writable
            else "- This is a review/analysis phase. Do not create, edit, rename, or delete files."
        )
        return f"""You are Codex acting as Engineering Review / QA inside Taren Game Studio.

OBJECTIVE
{request.objective}

RUN ID
{request.run_id}

CONTEXT
{context}

REVIEW RULES
- Work only from the supplied project workspace and context.
- Inspect the implementation critically and independently.
- Do not use network access.
{mutation_rule}
- Do not approve merely because another agent says the work is correct.
- Separate verified facts from assumptions.
- Findings must be concrete and actionable.
- Severity must be one of: critical, high, medium, low.
- Use critical/high only for defects that should block progression.
- Finish with a concise review summary.
- On the final line output exactly one machine-readable marker:
  TGS_REVIEW: {{"status":"approved|changes_requested","findings":[{{"severity":"critical|high|medium|low","title":"...","detail":"..."}}],"needs_meeting":false}}
"""

    @staticmethod
    def _extract_message(stdout: str) -> str:
        messages: list[str] = []
        for raw in stdout.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                event: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue
            item = event.get("item")
            if isinstance(item, dict):
                if item.get("type") in ("agent_message", "message"):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        messages.append(text.strip())
                    content = item.get("content")
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                messages.append(part["text"].strip())
            for key in ("message", "text", "output_text"):
                value = event.get(key)
                if isinstance(value, str) and value.strip():
                    messages.append(value.strip())
        if messages:
            return messages[-1]
        return stdout.strip()

    @staticmethod
    def _parse_review(summary: str) -> tuple[tuple[dict[str, Any], ...], bool]:
        match = re.search(r"TGS_REVIEW:\s*(\{.*\})\s*$", summary, re.DOTALL)
        if not match:
            return (), False
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            return (), False
        raw_findings = parsed.get("findings", [])
        findings = tuple(item for item in raw_findings if isinstance(item, dict))
        needs_meeting = parsed.get("needs_meeting") is True
        return findings, needs_meeting

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        if shutil.which(self.executable) is None:
            raise RuntimeError(f"Codex executable not found: {self.executable}")

        workspace = self._workspace(request)
        writable = any(action in request.allowed_actions for action in ("write", "edit"))
        sandbox = "workspace-write" if writable else "read-only"

        cmd = [
            self.executable,
            "--ask-for-approval",
            "never",
            "exec",
            "--sandbox",
            sandbox,
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            self._prompt(request),
        ]

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
            raise RuntimeError(f"Codex failed with exit code {completed.returncode}: {detail[-3000:]}")

        summary = self._extract_message(completed.stdout)
        if not summary:
            raise RuntimeError("Codex returned no review text")

        findings, needs_meeting = self._parse_review(summary)
        artifacts = tuple(
            {"type": "workspace", "ref": str(path.relative_to(workspace))}
            for path in sorted(workspace.rglob("*"))
            if path.is_file()
        )

        return AgentRunResult(
            status="completed",
            summary=summary,
            findings=findings,
            artifacts=artifacts,
            needs_meeting=needs_meeting,
        )
