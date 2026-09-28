from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import Decision, Meeting, MeetingMessage
from orchestrator.command_bus import CommandBus


class MeetingService:
    def __init__(self, session: Session):
        self.session = session
        self.bus = CommandBus(session)

    def _next_devil_advocate(self, project_id: uuid.UUID, participants: list[str]) -> str | None:
        if not participants:
            return None
        count = self.session.scalar(
            select(func.count()).select_from(Meeting).where(Meeting.project_id == project_id)
        ) or 0
        return participants[count % len(participants)]

    def start(
        self,
        *,
        project_id: uuid.UUID,
        meeting_type: str,
        topic: str,
        participants: list[str],
        correlation_id: uuid.UUID,
        causation_id: uuid.UUID | None = None,
        actor: str = "orchestrator",
    ) -> tuple[Meeting, object]:
        meeting_id = uuid.uuid4()
        devil = self._next_devil_advocate(project_id, participants)
        event = self.bus.emit(
            project_id=project_id,
            event_type="meeting.started",
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "meeting_id": str(meeting_id),
                "meeting_type": meeting_type,
                "topic": topic,
                "participants": participants,
                "devil_advocate_agent_id": devil,
            },
        )
        return self.session.get(Meeting, meeting_id), event

    def add_message(
        self,
        *,
        meeting: Meeting,
        actor: str,
        content: str,
        correlation_id: uuid.UUID,
        causation_id: uuid.UUID | None = None,
    ) -> MeetingMessage:
        sequence = self.session.scalar(
            select(func.count()).select_from(MeetingMessage).where(MeetingMessage.meeting_id == meeting.id)
        ) or 0
        message_id = uuid.uuid4()
        self.bus.emit(
            project_id=meeting.project_id,
            event_type="meeting.message",
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "meeting_id": str(meeting.id),
                "message_id": str(message_id),
                "sequence": sequence,
                "actor": actor,
                "content": content,
            },
        )
        return self.session.get(MeetingMessage, message_id)

    def resolve(
        self,
        *,
        meeting: Meeting,
        outcome_summary: str,
        correlation_id: uuid.UUID,
        causation_id: uuid.UUID | None = None,
    ) -> None:
        self.bus.emit(
            project_id=meeting.project_id,
            event_type="meeting.resolved",
            actor="orchestrator",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={"meeting_id": str(meeting.id), "outcome_summary": outcome_summary},
        )

    def accept_decision(
        self,
        *,
        project_id: uuid.UUID,
        decision_key: str,
        decision: str,
        reason: str,
        correlation_id: uuid.UUID,
        meeting: Meeting | None = None,
        rejected: list | None = None,
        impacts: list | None = None,
        causation_id: uuid.UUID | None = None,
    ) -> Decision:
        decision_id = uuid.uuid4()
        self.bus.emit(
            project_id=project_id,
            event_type="decision.accepted",
            actor="orchestrator",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "decision_id": str(decision_id),
                "decision_key": decision_key,
                "meeting_id": str(meeting.id) if meeting else None,
                "decision": decision,
                "reason": reason,
                "rejected": rejected or [],
                "impacts": impacts or [],
                "markdown_path": f"DECISIONS/{decision_key}.md",
            },
        )
        return self.session.get(Decision, decision_id)
