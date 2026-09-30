from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentRunRequest:
    run_id: str
    agent: str
    role: str
    objective: str
    context_package: dict[str, Any] = field(default_factory=dict)
    allowed_actions: tuple[str, ...] = ()
    expected_output: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRunResult:
    status: str
    summary: str
    findings: tuple[dict[str, Any], ...] = ()
    proposals: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    requested_actions: tuple[dict[str, Any], ...] = ()
    needs_meeting: bool = False
    verification: dict[str, Any] = field(default_factory=dict)


class AgentRunner(Protocol):
    agent_id: str
    role: str

    def run(self, request: AgentRunRequest) -> AgentRunResult: ...
