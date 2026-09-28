from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import Event
from .agent import AgentReducer
from .task import TaskReducer
from .meeting import MeetingReducer
from .run import RunReducer
from .review import ReviewReducer


class ReducerRegistry:
    def __init__(self) -> None:
        self._reducers = (TaskReducer(), AgentReducer(), MeetingReducer(), RunReducer(), ReviewReducer())

    def apply(self, session: Session, event: Event) -> None:
        for reducer in self._reducers:
            reducer.apply(session, event)


__all__ = ["ReducerRegistry", "TaskReducer", "AgentReducer", "MeetingReducer", "RunReducer", "ReviewReducer"]
