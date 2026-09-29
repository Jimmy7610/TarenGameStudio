from sqlalchemy import func, select

from database.enums import AgentState, ProjectStatus, TaskStatus
from database.models import Agent, AgentRun, Decision, Event, Meeting, Project, Review, Task
from orchestrator.studio_engine import StudioEngine


def test_fake_studio_runs_kickoff_and_complete_pipeline(session):
    engine = StudioEngine(session)
    project = engine.create_project("Pong Verification")
    session.flush()

    kickoff = engine.kickoff(project, "Create a very simple Pong game for Windows.")

    assert kickoff["devil_advocate"] == "chatgpt"
    assert set(kickoff["summaries"]) == {"chatgpt", "claude", "codex", "antigravity"}
    assert len(kickoff["tasks"]) == 4
    assert kickoff["assignments"][0]["agent_id"] == "chatgpt"

    result = engine.run_until_idle(project.id)

    tasks = list(session.scalars(select(Task).where(Task.project_id == project.id)))
    assert len(tasks) == 4
    assert all(task.status == TaskStatus.DONE for task in tasks)

    agents = list(session.scalars(select(Agent)))
    assert all(agent.state == AgentState.IDLE for agent in agents)

    assert session.scalar(select(func.count()).select_from(Review)) == 4
    assert session.scalar(select(func.count()).select_from(AgentRun)) == 8
    assert session.scalar(select(func.count()).select_from(Decision)) == 1
    assert session.scalar(select(func.count()).select_from(Meeting)) == 1

    event_types = list(session.scalars(
        select(Event.event_type).where(Event.project_id == project.id)
    ))
    assert "instruction.received" in event_types
    assert "meeting.started" in event_types
    assert "decision.accepted" in event_types
    assert "agent.run.started" in event_types
    assert "agent.run.completed" in event_types
    assert "review.accepted" in event_types
    assert "project.activated" in event_types
    assert "project.ready" in event_types

    snapshot = result["state"]
    assert project.status == ProjectStatus.READY
    assert snapshot["project"]["status"] == "READY"
    assert all(task["status"] == "DONE" for task in snapshot["tasks"])
    assert len(snapshot["decisions"]) == 1
    assert len(snapshot["reviews"]) == 4
    assert "artifacts" in snapshot


def test_api_module_exposes_hq_and_realtime_routes():
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/hq" in paths
    assert "/projects" in paths
    assert "/tasks" in paths
    assert "/meetings" in paths
    assert "/decisions" in paths
    assert "/builds" in paths
    assert "/playtests" in paths
    assert "/logs" in paths
    assert "/settings" in paths
    assert "/api/projects" in paths
    assert "/api/projects/{project_id}/reconcile-status" in paths
    assert "/api/projects/{project_id}/prompt" in paths
    assert "/api/projects/{project_id}/run-cycle" in paths
    assert "/api/projects/{project_id}/run-until-idle" in paths
    assert "/api/studio/state" in paths
    assert "/ws/events" in paths
