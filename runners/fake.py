from __future__ import annotations

from runners.base import AgentRunRequest, AgentRunResult


_ROLE_SUMMARIES = {
    "chatgpt": "Game Director: constrain the first playable to one clear core loop, document the player goal, and reject scope that does not prove the game concept. Risk: broad ideas can hide an untestable core.",
    "claude": "Lead Engineer: prefer the smallest technically complete implementation with clear module boundaries and a reproducible build. Risk: premature architecture can create unnecessary complexity.",
    "codex": "Engineering Review: define objective acceptance checks before implementation and challenge hidden assumptions. Risk: code can pass happy-path tests while violating the intended workflow.",
    "antigravity": "Experience/Visual: make the first playable immediately readable, with clear feedback and minimal UI. Risk: a technically correct prototype can still feel confusing or flat.",
}


class FakeAgentRunner:
    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        if request.agent != self.agent_id:
            raise ValueError(f"runner {self.agent_id} cannot execute request for {request.agent}")
        kickoff = request.context_package.get("meeting_type") == "kickoff"
        summary = _ROLE_SUMMARIES.get(
            self.agent_id, f"{self.agent_id} completed: {request.objective}"
        ) if kickoff else f"{self.agent_id} completed: {request.objective}"
        if request.context_package.get("devil_advocate"):
            summary += " Devil's Advocate: explicitly challenge the leading proposal before accepting it."
        return AgentRunResult(
            status="completed",
            summary=summary,
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
