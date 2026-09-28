from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.enums import AgentState
from database.models import Agent, Event
from orchestrator.transitions import ensure_agent_transition


class AgentReducer:
    def apply(self, session: Session, event: Event) -> Agent | None:
        p = event.payload_json
        et = event.event_type

        if et == "agent.registered":
            agent = Agent(
                id=p["agent_id"],
                role=p["role"],
                state=AgentState(p.get("state", AgentState.OFFLINE.value)),
            )
            session.add(agent)
            session.flush()
            return agent

        if et != "agent.state_changed":
            return None

        agent = session.get(Agent, p["agent_id"])
        if agent is None:
            raise KeyError(f"unknown agent: {p['agent_id']}")
        target = AgentState(p["state"])
        ensure_agent_transition(agent.state, target)
        agent.state = target
        raw_task_id = p.get("current_task_id")
        agent.current_task_id = uuid.UUID(raw_task_id) if raw_task_id else None
        agent.version += 1
        session.flush()
        return agent
