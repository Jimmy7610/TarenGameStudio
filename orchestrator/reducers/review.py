from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.enums import ReviewStatus
from database.models import Event, Review


class ReviewReducer:
    def apply(self, session: Session, event: Event) -> Review | None:
        p = event.payload_json
        if event.event_type == "review.requested" and p.get("review_id"):
            review = Review(
                id=uuid.UUID(p["review_id"]),
                project_id=event.project_id,
                task_id=uuid.UUID(p["task_id"]),
                creator_agent_id=p.get("creator_agent_id"),
                reviewer_agent_id=p["reviewer_agent_id"],
                status=ReviewStatus.REQUESTED,
                summary="",
                findings_json=[],
            )
            session.add(review)
            session.flush()
            return review

        if event.event_type in {"review.accepted", "review.rejected"} and p.get("review_id"):
            review = session.get(Review, uuid.UUID(p["review_id"]))
            if review is None:
                raise KeyError(f"unknown review: {p['review_id']}")
            review.status = (
                ReviewStatus.APPROVED if event.event_type == "review.accepted"
                else ReviewStatus.CHANGES_REQUESTED
            )
            review.summary = p.get("summary", "")
            review.findings_json = p.get("findings", [])
            review.version += 1
            session.flush()
            return review
        return None
