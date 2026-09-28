from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.enums import MeetingStatus
from database.models import Decision, Event, Meeting, MeetingMessage


class MeetingReducer:
    def apply(self, session: Session, event: Event) -> Meeting | Decision | MeetingMessage | None:
        p = event.payload_json
        et = event.event_type

        if et == "meeting.started":
            meeting = Meeting(
                id=uuid.UUID(p["meeting_id"]),
                project_id=event.project_id,
                meeting_type=p["meeting_type"],
                topic=p["topic"],
                status=MeetingStatus.ACTIVE,
                participants_json=p["participants"],
                devil_advocate_agent_id=p.get("devil_advocate_agent_id"),
            )
            session.add(meeting)
            session.flush()
            return meeting

        if et == "meeting.message":
            meeting_id = uuid.UUID(p["meeting_id"])
            meeting = session.get(Meeting, meeting_id)
            if meeting is None:
                raise KeyError(f"unknown meeting: {meeting_id}")
            if meeting.status != MeetingStatus.ACTIVE:
                raise ValueError("messages can only be added to active meetings")
            message = MeetingMessage(
                id=uuid.UUID(p["message_id"]),
                meeting_id=meeting_id,
                sequence=int(p["sequence"]),
                actor=p["actor"],
                content=p["content"],
            )
            session.add(message)
            session.flush()
            return message

        if et == "meeting.resolved":
            meeting = session.get(Meeting, uuid.UUID(p["meeting_id"]))
            if meeting is None:
                raise KeyError(f"unknown meeting: {p['meeting_id']}")
            if meeting.status != MeetingStatus.ACTIVE:
                raise ValueError("only active meetings can be resolved")
            meeting.status = MeetingStatus.RESOLVED
            meeting.outcome_summary = p.get("outcome_summary", "")
            meeting.version += 1
            session.flush()
            return meeting

        if et == "decision.accepted":
            decision = Decision(
                id=uuid.UUID(p["decision_id"]),
                project_id=event.project_id,
                decision_key=p["decision_key"],
                meeting_id=uuid.UUID(p["meeting_id"]) if p.get("meeting_id") else None,
                decision=p["decision"],
                reason=p["reason"],
                rejected_json=p.get("rejected", []),
                impacts_json=p.get("impacts", []),
                markdown_path=p.get("markdown_path"),
            )
            session.add(decision)
            session.flush()
            return decision

        return None
