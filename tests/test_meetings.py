import uuid

from database.enums import MeetingStatus
from database.models import Project
from orchestrator.meeting_service import MeetingService


def make_project(session):
    p = Project(name="Pong")
    session.add(p)
    session.flush()
    return p


def test_meeting_records_messages_and_structured_decision(session):
    p = make_project(session)
    flow = uuid.uuid4()
    service = MeetingService(session)
    participants = ["chatgpt", "claude", "codex", "antigravity"]

    meeting, started = service.start(
        project_id=p.id,
        meeting_type="kickoff",
        topic="How should we build Pong?",
        participants=participants,
        correlation_id=flow,
    )
    assert meeting.status == MeetingStatus.ACTIVE
    assert meeting.devil_advocate_agent_id == "chatgpt"

    m1 = service.add_message(
        meeting=meeting,
        actor="chatgpt",
        content="Use a deliberately tiny scope.",
        correlation_id=flow,
        causation_id=started.id,
    )
    m2 = service.add_message(
        meeting=meeting,
        actor="claude",
        content="Keep the architecture engine-agnostic.",
        correlation_id=flow,
    )
    assert (m1.sequence, m2.sequence) == (0, 1)

    decision = service.accept_decision(
        project_id=p.id,
        decision_key="DEC-0001",
        decision="Build Pong as the first end-to-end verification game.",
        reason="Minimal scope proves orchestration before commercial production.",
        correlation_id=flow,
        meeting=meeting,
        rejected=["Start with a commercial-scale game"],
        impacts=["Core verification", "FakeAgent pipeline"],
    )
    assert decision.decision_key == "DEC-0001"
    assert decision.markdown_path == "DECISIONS/DEC-0001.md"

    service.resolve(meeting=meeting, outcome_summary="Pong approved.", correlation_id=flow)
    assert meeting.status == MeetingStatus.RESOLVED


def test_devil_advocate_rotates_by_meeting(session):
    p = make_project(session)
    flow = uuid.uuid4()
    service = MeetingService(session)
    participants = ["chatgpt", "claude", "codex", "antigravity"]

    first, _ = service.start(project_id=p.id, meeting_type="kickoff", topic="A", participants=participants, correlation_id=flow)
    second, _ = service.start(project_id=p.id, meeting_type="review", topic="B", participants=participants, correlation_id=flow)
    assert first.devil_advocate_agent_id == "chatgpt"
    assert second.devil_advocate_agent_id == "claude"
