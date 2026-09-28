from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from database.models import Event, Project


class EventStoreError(RuntimeError):
    pass


class UnknownProjectError(EventStoreError):
    pass


class UnknownCausationEventError(EventStoreError):
    pass


class CrossProjectCausationError(EventStoreError):
    pass


class EventStore:
    """Append-only access to immutable production history."""

    def __init__(self, session: Session):
        self.session = session

    def append(
        self,
        *,
        project_id: uuid.UUID,
        event_type: str,
        actor: str,
        payload: dict[str, Any] | None = None,
        correlation_id: uuid.UUID | None = None,
        causation_id: uuid.UUID | None = None,
        schema_version: str = "0.1",
    ) -> Event:
        project = self.session.get(Project, project_id)
        if project is None:
            raise UnknownProjectError(str(project_id))

        correlation_id = correlation_id or uuid.uuid4()

        if causation_id is not None:
            cause = self.session.get(Event, causation_id)
            if cause is None:
                raise UnknownCausationEventError(str(causation_id))
            if cause.project_id != project_id:
                raise CrossProjectCausationError(
                    f"cause {causation_id} belongs to project {cause.project_id}, not {project_id}"
                )
            # A child normally remains inside the same end-to-end flow.
            if correlation_id != cause.correlation_id:
                raise EventStoreError(
                    "caused events must use the same correlation_id as their cause"
                )

        record = Event(
            project_id=project_id,
            event_type=event_type,
            actor=actor,
            payload_json=payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
            schema_version=schema_version,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get(self, event_id: uuid.UUID) -> Event | None:
        return self.session.get(Event, event_id)

    def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        correlation_id: uuid.UUID | None = None,
        limit: int = 1000,
    ) -> list[Event]:
        stmt: Select[tuple[Event]] = select(Event).where(Event.project_id == project_id)
        if correlation_id is not None:
            stmt = stmt.where(Event.correlation_id == correlation_id)
        stmt = stmt.order_by(Event.timestamp.asc(), Event.id.asc()).limit(limit)
        return list(self.session.scalars(stmt))
