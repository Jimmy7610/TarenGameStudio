from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import AgentState, Priority, TaskStatus
from database.models import Agent, Event, Meeting, Project, Task
from orchestrator.agent_service import AgentService
from orchestrator.command_bus import CommandBus
from orchestrator.meeting_service import MeetingService
from orchestrator.scheduler import Scheduler
from orchestrator.task_service import TaskService
from runners import AgentRunRequest, FakeAntigravity, FakeChatGPT, FakeClaude, FakeCodex


DEFAULT_ROSTER = {
    "chatgpt": "game_director",
    "claude": "lead_engineer",
    "codex": "engineering_review",
    "antigravity": "experience_visual",
}


class StudioEngine:
    def __init__(self, session: Session, runners: dict | None = None):
        self.session = session
        self.bus = CommandBus(session)
        self.agents = AgentService(session)
        self.tasks = TaskService(session)
        self.meetings = MeetingService(session)
        self.scheduler = Scheduler(session)
        self.runners = runners or {
            "chatgpt": FakeChatGPT(),
            "claude": FakeClaude(),
            "codex": FakeCodex(),
            "antigravity": FakeAntigravity(),
        }

    def create_project(self, name: str) -> Project:
        project = Project(name=name)
        self.session.add(project)
        self.session.flush()
        return project

    def ensure_roster(self, project: Project, correlation_id: uuid.UUID) -> list[Agent]:
        agents: list[Agent] = []
        for agent_id, role in DEFAULT_ROSTER.items():
            existing = self.session.get(Agent, agent_id)
            if existing is None:
                existing = self.agents.register(
                    project_id=project.id,
                    agent_id=agent_id,
                    role=role,
                    initial_state=AgentState.IDLE,
                    correlation_id=correlation_id,
                )
            elif existing.state == AgentState.OFFLINE:
                self.agents.set_state(
                    project_id=project.id,
                    agent=existing,
                    state=AgentState.IDLE,
                    correlation_id=correlation_id,
                )
            agents.append(existing)
        return agents

    def kickoff(self, project: Project, owner_prompt: str) -> dict:
        flow = uuid.uuid4()
        roster = self.ensure_roster(project, flow)

        instruction = self.bus.emit(
            project_id=project.id,
            event_type="instruction.received",
            actor="jimmy",
            correlation_id=flow,
            payload={"prompt": owner_prompt},
        )

        meeting, meeting_started = self.meetings.start(
            project_id=project.id,
            meeting_type="kickoff",
            topic="Analyze the owner instruction and agree on the first production plan.",
            participants=[a.id for a in roster],
            correlation_id=flow,
            causation_id=instruction.id,
        )

        for agent in roster:
            self.agents.set_state(
                project_id=project.id,
                agent=agent,
                state=AgentState.MEETING,
                correlation_id=flow,
                causation_id=meeting_started.id,
            )

        summaries: dict[str, str] = {}
        previous_cause = meeting_started.id
        for agent in roster:
            runner = self.runners[agent.id]
            result = runner.run(
                AgentRunRequest(
                    run_id=str(uuid.uuid4()),
                    agent=agent.id,
                    role=agent.role,
                    objective="Critically analyze the owner prompt from your specialist role. Identify the strongest next step and at least one risk.",
                    context_package={
                        "owner_prompt": owner_prompt,
                        "meeting_type": "kickoff",
                        "devil_advocate": meeting.devil_advocate_agent_id == agent.id,
                    },
                )
            )
            message = self.meetings.add_message(
                meeting=meeting,
                actor=agent.id,
                content=result.summary,
                correlation_id=flow,
                causation_id=previous_cause,
            )
            summaries[agent.id] = result.summary
            previous_cause = self.session.scalar(
                select(Event.id)
                .where(Event.project_id == project.id, Event.event_type == "meeting.message")
                .order_by(Event.timestamp.desc(), Event.id.desc())
                .limit(1)
            ) or previous_cause

        decision = self.meetings.accept_decision(
            project_id=project.id,
            decision_key="DEC-0001",
            decision="Proceed with a deliberately small first playable plan derived from the owner prompt, using cross-agent review before expansion.",
            reason="The studio must prove the complete collaboration and review pipeline before increasing production scope.",
            correlation_id=flow,
            meeting=meeting,
            rejected=["Start with uncontrolled broad implementation before validating the pipeline."],
            impacts=["Initial design task", "Implementation task", "Engineering review", "Experience review"],
            causation_id=previous_cause,
        )

        self.meetings.resolve(
            meeting=meeting,
            outcome_summary="Kickoff complete. First production tasks approved.",
            correlation_id=flow,
        )

        for agent in roster:
            self.agents.set_state(
                project_id=project.id,
                agent=agent,
                state=AgentState.IDLE,
                correlation_id=flow,
            )

        design_task, design_event = self.tasks.create(
            project_id=project.id,
            title="Define first playable",
            description=f"Translate owner instruction into a constrained first playable plan: {owner_prompt}",
            priority=Priority.CRITICAL,
            owner_agent_id="chatgpt",
            acceptance_criteria=[
                "Core gameplay loop is explicit",
                "Scope is small enough for first playable",
                "Primary risks are documented",
            ],
            correlation_id=flow,
        )
        implementation_task, _ = self.tasks.create(
            project_id=project.id,
            title="Implement first playable",
            description="Build the first playable approved by the design task.",
            priority=Priority.HIGH,
            owner_agent_id="claude",
            acceptance_criteria=["Build runs", "Core loop is playable", "Implementation is reviewable"],
            depends_on=[design_task.id],
            correlation_id=flow,
        )
        review_task, _ = self.tasks.create(
            project_id=project.id,
            title="Engineering review",
            description="Critically review the first playable implementation.",
            priority=Priority.HIGH,
            owner_agent_id="codex",
            acceptance_criteria=["Critical defects identified", "Acceptance criteria independently checked"],
            depends_on=[implementation_task.id],
            correlation_id=flow,
        )
        experience_task, _ = self.tasks.create(
            project_id=project.id,
            title="Experience review",
            description="Evaluate UI, clarity and game feel of the first playable.",
            priority=Priority.HIGH,
            owner_agent_id="antigravity",
            acceptance_criteria=["Visual clarity assessed", "Game-feel risks documented"],
            depends_on=[implementation_task.id],
            correlation_id=flow,
        )

        self.scheduler.promote_ready(project_id=project.id, correlation_id=flow)
        assignments = self.scheduler.assign_ready(project_id=project.id, correlation_id=flow)
        self.session.commit()

        return {
            "project_id": str(project.id),
            "correlation_id": str(flow),
            "meeting_id": str(meeting.id),
            "decision_id": str(decision.id),
            "devil_advocate": meeting.devil_advocate_agent_id,
            "summaries": summaries,
            "tasks": [str(x.id) for x in [design_task, implementation_task, review_task, experience_task]],
            "assignments": [{"task_id": str(task.id), "agent_id": agent.id} for task, agent in assignments],
        }

    def state_snapshot(self, project_id: uuid.UUID) -> dict:
        project = self.session.get(Project, project_id)
        if project is None:
            raise KeyError(str(project_id))
        agents = list(self.session.scalars(select(Agent).order_by(Agent.id)))
        tasks = list(self.session.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at, Task.id)))
        meetings = list(self.session.scalars(select(Meeting).where(Meeting.project_id == project_id).order_by(Meeting.created_at.desc())))
        latest_events = list(self.session.scalars(
            select(Event).where(Event.project_id == project_id).order_by(Event.timestamp.desc(), Event.id.desc()).limit(50)
        ))
        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "status": project.status.value,
                "current_milestone": project.current_milestone,
            },
            "agents": [
                {
                    "id": a.id,
                    "role": a.role,
                    "state": a.state.value,
                    "current_task_id": str(a.current_task_id) if a.current_task_id else None,
                }
                for a in agents
            ],
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "owner_agent_id": t.owner_agent_id,
                    "rework_count": t.rework_count,
                }
                for t in tasks
            ],
            "meetings": [
                {
                    "id": str(m.id),
                    "type": m.meeting_type,
                    "topic": m.topic,
                    "status": m.status.value,
                    "participants": m.participants_json,
                    "devil_advocate_agent_id": m.devil_advocate_agent_id,
                    "outcome_summary": m.outcome_summary,
                }
                for m in meetings
            ],
            "events": [
                {
                    "id": str(e.id),
                    "type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "actor": e.actor,
                    "correlation_id": str(e.correlation_id),
                    "causation_id": str(e.causation_id) if e.causation_id else None,
                    "payload": e.payload_json,
                }
                for e in reversed(latest_events)
            ],
        }
