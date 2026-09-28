import uuid

import pytest

from database.enums import AgentState, Priority, TaskStatus
from database.models import Project
from orchestrator.agent_service import AgentService
from orchestrator.scheduler import Scheduler
from orchestrator.task_service import TaskService
from orchestrator.transitions import InvalidTransitionError
from runners import AgentRunRequest, FakeAntigravity, FakeChatGPT, FakeClaude, FakeCodex


def project(session):
    p = Project(name="Pong")
    session.add(p)
    session.flush()
    return p


def test_task_creation_and_valid_transitions_are_event_driven(session):
    p = project(session)
    correlation = uuid.uuid4()
    service = TaskService(session)
    task, created = service.create(
        project_id=p.id,
        title="Build paddle",
        acceptance_criteria=["moves up and down"],
        correlation_id=correlation,
    )
    assert task.status == TaskStatus.TODO
    ready = service.mark_ready(task, correlation_id=correlation, causation_id=created.id)
    assert task.status == TaskStatus.READY
    service.start(task, correlation_id=correlation, causation_id=ready.id)
    assert task.status == TaskStatus.WORKING
    service.request_review(task, correlation_id=correlation)
    assert task.status == TaskStatus.REVIEW
    service.accept_review(task, correlation_id=correlation)
    assert task.status == TaskStatus.DONE


def test_invalid_task_transition_is_rejected(session):
    p = project(session)
    task, _ = TaskService(session).create(project_id=p.id, title="X", correlation_id=uuid.uuid4())
    with pytest.raises(InvalidTransitionError):
        TaskService(session).request_review(task, correlation_id=uuid.uuid4())


def test_scheduler_respects_dependencies_and_assigns_idle_agent(session):
    p = project(session)
    flow = uuid.uuid4()
    agents = AgentService(session)
    claude = agents.register(project_id=p.id, agent_id="claude", role="lead_engineer", initial_state=AgentState.IDLE, correlation_id=flow)
    tasks = TaskService(session)
    first, _ = tasks.create(project_id=p.id, title="Core", priority=Priority.HIGH, correlation_id=flow)
    second, _ = tasks.create(project_id=p.id, title="UI", depends_on=[first.id], correlation_id=flow)

    scheduler = Scheduler(session)
    promoted = scheduler.promote_ready(project_id=p.id, correlation_id=flow)
    assert [x.id for x in promoted] == [first.id]
    assignments = scheduler.assign_ready(project_id=p.id, correlation_id=flow)
    assert assignments[0][0].id == first.id
    assert assignments[0][1].id == "claude"
    assert first.status == TaskStatus.WORKING
    assert second.status == TaskStatus.TODO
    assert claude.state == AgentState.WORKING

    tasks.request_review(first, correlation_id=flow)
    tasks.accept_review(first, correlation_id=flow)
    agents.set_state(project_id=p.id, agent=claude, state=AgentState.IDLE, correlation_id=flow)
    promoted2 = scheduler.promote_ready(project_id=p.id, correlation_id=flow)
    assert [x.id for x in promoted2] == [second.id]


def test_four_fake_runners_obey_same_contract():
    runners = [FakeChatGPT(), FakeClaude(), FakeCodex(), FakeAntigravity()]
    for runner in runners:
        result = runner.run(AgentRunRequest(
            run_id=str(uuid.uuid4()),
            agent=runner.agent_id,
            role=runner.role,
            objective="Contribute to Pong kickoff",
            context_package={"project": "Pong"},
        ))
        assert result.status == "completed"
        assert runner.agent_id in result.summary
        assert result.needs_meeting is False
