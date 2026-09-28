import uuid

import pytest
from sqlalchemy import select

from database.models import Event, Project
from orchestrator.event_store import (
    CrossProjectCausationError,
    EventStore,
    EventStoreError,
    UnknownCausationEventError,
    UnknownProjectError,
)


def create_project(session, name="Test Game"):
    project = Project(name=name)
    session.add(project)
    session.flush()
    return project


def test_append_creates_event_with_flow_identity(session):
    project = create_project(session)
    store = EventStore(session)

    event = store.append(
        project_id=project.id,
        event_type="instruction.received",
        actor="jimmy",
        payload={"prompt": "Build Pong"},
    )

    assert event.id is not None
    assert event.correlation_id is not None
    assert event.causation_id is None
    assert event.payload_json["prompt"] == "Build Pong"


def test_caused_event_must_share_correlation(session):
    project = create_project(session)
    store = EventStore(session)
    root = store.append(
        project_id=project.id,
        event_type="instruction.received",
        actor="jimmy",
    )

    child = store.append(
        project_id=project.id,
        event_type="meeting.started",
        actor="orchestrator",
        correlation_id=root.correlation_id,
        causation_id=root.id,
    )

    assert child.causation_id == root.id
    assert child.correlation_id == root.correlation_id

    with pytest.raises(EventStoreError):
        store.append(
            project_id=project.id,
            event_type="task.created",
            actor="orchestrator",
            correlation_id=uuid.uuid4(),
            causation_id=root.id,
        )


def test_unknown_project_rejected(session):
    with pytest.raises(UnknownProjectError):
        EventStore(session).append(
            project_id=uuid.uuid4(),
            event_type="task.created",
            actor="orchestrator",
        )


def test_unknown_causation_event_rejected(session):
    project = create_project(session)
    with pytest.raises(UnknownCausationEventError):
        EventStore(session).append(
            project_id=project.id,
            event_type="task.created",
            actor="orchestrator",
            correlation_id=uuid.uuid4(),
            causation_id=uuid.uuid4(),
        )


def test_cross_project_causation_rejected(session):
    a = create_project(session, "A")
    b = create_project(session, "B")
    store = EventStore(session)
    root = store.append(project_id=a.id, event_type="instruction.received", actor="jimmy")

    with pytest.raises(CrossProjectCausationError):
        store.append(
            project_id=b.id,
            event_type="task.created",
            actor="orchestrator",
            correlation_id=root.correlation_id,
            causation_id=root.id,
        )


def test_events_are_immutable_in_orm(session):
    project = create_project(session)
    store = EventStore(session)
    event = store.append(project_id=project.id, event_type="task.created", actor="orchestrator")
    session.commit()

    event.actor = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        session.commit()
    session.rollback()


def test_event_delete_is_forbidden(session):
    project = create_project(session)
    store = EventStore(session)
    event = store.append(project_id=project.id, event_type="task.created", actor="orchestrator")
    session.commit()

    session.delete(event)
    with pytest.raises(ValueError, match="immutable"):
        session.commit()


def test_list_for_project_orders_and_filters_flow(session):
    project = create_project(session)
    store = EventStore(session)
    root = store.append(project_id=project.id, event_type="instruction.received", actor="jimmy")
    store.append(
        project_id=project.id,
        event_type="meeting.started",
        actor="orchestrator",
        correlation_id=root.correlation_id,
        causation_id=root.id,
    )
    store.append(project_id=project.id, event_type="system.other_flow", actor="orchestrator")

    flow_events = store.list_for_project(project.id, correlation_id=root.correlation_id)
    assert [x.event_type for x in flow_events] == ["instruction.received", "meeting.started"]
