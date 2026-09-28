from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.enums import Priority
from database.models import Event, Task
from orchestrator.command_bus import CommandBus


class TaskService:
    def __init__(self, session: Session):
        self.session = session
        self.bus = CommandBus(session)

    def create(
        self,
        *,
        project_id: uuid.UUID,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        owner_agent_id: str | None = None,
        acceptance_criteria: list | None = None,
        depends_on: list[uuid.UUID] | None = None,
        max_rework_cycles: int = 3,
        actor: str = "orchestrator",
        correlation_id: uuid.UUID | None = None,
        causation_id: uuid.UUID | None = None,
    ) -> tuple[Task, Event]:
        task_id = uuid.uuid4()
        event = self.bus.emit(
            project_id=project_id,
            event_type="task.created",
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "task_id": str(task_id),
                "title": title,
                "description": description,
                "priority": priority.value,
                "owner_agent_id": owner_agent_id,
                "acceptance_criteria": acceptance_criteria or [],
                "depends_on": [str(x) for x in (depends_on or [])],
                "max_rework_cycles": max_rework_cycles,
            },
        )
        return self.session.get(Task, task_id), event

    def transition(self, task: Task, event_type: str, *, actor: str = "orchestrator", correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None, **extra) -> Event:
        return self.bus.emit(
            project_id=task.project_id,
            event_type=event_type,
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={"task_id": str(task.id), **extra},
        )

    def mark_ready(self, task: Task, **trace) -> Event:
        return self.transition(task, "task.ready", **trace)

    def assign(self, task: Task, agent_id: str, **trace) -> Event:
        return self.transition(task, "task.assigned", agent_id=agent_id, **trace)

    def start(self, task: Task, **trace) -> Event:
        return self.transition(task, "task.started", **trace)

    def request_review(self, task: Task, **trace) -> Event:
        return self.transition(task, "review.requested", **trace)

    def accept_review(self, task: Task, **trace) -> Event:
        return self.transition(task, "review.accepted", **trace)

    def reject_review(self, task: Task, **trace) -> Event:
        return self.transition(task, "review.rejected", **trace)

    def block(self, task: Task, reason: str, **trace) -> Event:
        return self.transition(task, "task.blocked", reason=reason, **trace)
