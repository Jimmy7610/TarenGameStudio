from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from database.models import Event
from orchestrator.event_store import EventStore
from orchestrator.reducers import ReducerRegistry


class CommandBus:
    """Persists the event first, then applies reducers in the same transaction."""

    def __init__(self, session: Session, *, reducers: ReducerRegistry | None = None):
        self.session = session
        self.events = EventStore(session)
        self.reducers = reducers or ReducerRegistry()

    def emit(
        self,
        *,
        project_id: uuid.UUID,
        event_type: str,
        actor: str,
        payload: dict[str, Any] | None = None,
        correlation_id: uuid.UUID | None = None,
        causation_id: uuid.UUID | None = None,
    ) -> Event:
        event = self.events.append(
            project_id=project_id,
            event_type=event_type,
            actor=actor,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.reducers.apply(self.session, event)
        return event
