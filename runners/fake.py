from __future__ import annotations

from runners.base import AgentRunRequest, AgentRunResult


class FakeAgentRunner:
    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        if request.agent != self.agent_id:
            raise ValueError(f"runner {self.agent_id} cannot execute request for {request.agent}")
        return AgentRunResult(
            status="completed",
            summary=f"{self.agent_id} completed: {request.objective}",
            findings=(),
            proposals=(),
            artifacts=(),
            requested_actions=(),
            needs_meeting=False,
        )


class FakeChatGPT(FakeAgentRunner):
    def __init__(self):
        super().__init__("chatgpt", "game_director")


class FakeClaude(FakeAgentRunner):
    def __init__(self):
        super().__init__("claude", "lead_engineer")


class FakeCodex(FakeAgentRunner):
    def __init__(self):
        super().__init__("codex", "engineering_review")


class FakeAntigravity(FakeAgentRunner):
    def __init__(self):
        super().__init__("antigravity", "experience_visual")
