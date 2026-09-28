from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.models import Review, Task
from orchestrator.command_bus import CommandBus


class ReviewService:
    def __init__(self, session: Session):
        self.session = session
        self.bus = CommandBus(session)

    def request(self, *, task: Task, creator_agent_id: str | None, reviewer_agent_id: str, correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None) -> Review:
        review_id = uuid.uuid4()
        self.bus.emit(
            project_id=task.project_id,
            event_type="review.requested",
            actor="orchestrator",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "task_id": str(task.id),
                "review_id": str(review_id),
                "creator_agent_id": creator_agent_id,
                "reviewer_agent_id": reviewer_agent_id,
            },
        )
        return self.session.get(Review, review_id)

    def accept(self, *, review: Review, task: Task, summary: str, findings: list, correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None) -> None:
        self.bus.emit(
            project_id=task.project_id,
            event_type="review.accepted",
            actor=review.reviewer_agent_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "task_id": str(task.id),
                "review_id": str(review.id),
                "summary": summary,
                "findings": findings,
            },
        )

    def reject(self, *, review: Review, task: Task, summary: str, findings: list, correlation_id: uuid.UUID, causation_id: uuid.UUID | None = None) -> None:
        self.bus.emit(
            project_id=task.project_id,
            event_type="review.rejected",
            actor=review.reviewer_agent_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "task_id": str(task.id),
                "review_id": str(review.id),
                "summary": summary,
                "findings": findings,
            },
        )
