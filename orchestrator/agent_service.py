from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.enums import AgentState
from database.models import Agent, Project
from orchestrator.command_bus import CommandBus


class AgentService:
    def __init__(self, session: Session):
        self.session = session
        self.bus = CommandBus(session)

    def register(self, *, project_id: uuid.UUID, agent_id: str, role: str, initial_state: AgentState = AgentState.OFFLINE, correlation_id: uuid.UUID | None = None) -> Agent:
        self.bus.emit(
            project_id=project_id,
            event_type="agent.registered",
            actor="orchestrator",
            correlation_id=correlation_id,
            payload={"agent_id": agent_id, "role": role, "state": initial_state.value},
        )
        return self.session.get(Agent, agent_id)

    def set_state(self, *, project_id: uuid.UUID, agent: Agent, state: AgentState, current_task_id: uuid.UUID | None = None, correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None) -> None:
        self.bus.emit(
            project_id=project_id,
            event_type="agent.state_changed",
            actor="orchestrator",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "agent_id": agent.id,
                "state": state.value,
                "current_task_id": str(current_task_id) if current_task_id else None,
            },
        )
