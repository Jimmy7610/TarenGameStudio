from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.models import Event, Project
from orchestrator.command_bus import CommandBus


class ProjectService:
    def __init__(self, session: Session):
        self.session = session
        self.bus = CommandBus(session)

    def set_status(
        self,
        *,
        project: Project,
        event_type: str,
        correlation_id: uuid.UUID,
        causation_id: uuid.UUID | None = None,
        actor: str = "orchestrator",
    ) -> Event:
        return self.bus.emit(
            project_id=project.id,
            event_type=event_type,
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={"project_id": str(project.id)},
        )

    def activate(self, *, project: Project, correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None) -> Event:
        return self.set_status(project=project, event_type="project.activated", correlation_id=correlation_id, causation_id=causation_id)

    def ready(self, *, project: Project, correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None) -> Event:
        return self.set_status(project=project, event_type="project.ready", correlation_id=correlation_id, causation_id=causation_id)
