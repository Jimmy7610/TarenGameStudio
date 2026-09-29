from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import AgentState, Priority, TaskStatus
from database.models import Agent, Artifact, Decision, Event, Meeting, Project, Review, Task
from orchestrator.agent_service import AgentService
from orchestrator.command_bus import CommandBus
from orchestrator.meeting_service import MeetingService
from orchestrator.review_service import ReviewService
from orchestrator.scheduler import Scheduler
from orchestrator.task_service import TaskService
from runners import AgentRunRequest, FakeAntigravity, FakeChatGPT, FakeClaude, FakeCodex


DEFAULT_ROSTER = {
    "chatgpt": "game_director",
    "claude": "lead_engineer",
    "codex": "engineering_review",
    "antigravity": "experience_visual",
}

AGENT_DISPLAY = {
    "chatgpt": {"name": "ChatGPT", "role": "Game Director"},
    "claude": {"name": "Claude Code", "role": "Lead Engineer"},
    "codex": {"name": "Codex", "role": "Engineering Review / QA"},
    "antigravity": {"name": "Antigravity", "role": "Experience / Visual"},
}


class StudioEngine:
    def __init__(self, session: Session, runners: dict | None = None):
        self.session = session
        self.bus = CommandBus(session)
        self.agents = AgentService(session)
        self.tasks = TaskService(session)
        self.meetings = MeetingService(session)
        self.reviews = ReviewService(session)
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
            self.meetings.add_message(
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

        design_task, _ = self.tasks.create(
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

    def _latest_flow(self, project_id: uuid.UUID) -> uuid.UUID:
        correlation_id = self.session.scalar(
            select(Event.correlation_id)
            .where(Event.project_id == project_id)
            .order_by(Event.timestamp.desc(), Event.id.desc())
            .limit(1)
        )
        if correlation_id is None:
            raise ValueError("project has no active flow")
        return correlation_id

    def _available_reviewer(self, owner_agent_id: str) -> Agent:
        preference = ["codex", "claude", "chatgpt", "antigravity"]
        for agent_id in preference:
            if agent_id == owner_agent_id:
                continue
            agent = self.session.get(Agent, agent_id)
            if agent is not None and agent.state == AgentState.IDLE:
                return agent
        raise RuntimeError("no independent reviewer is available")

    def run_cycle(self, project_id: uuid.UUID) -> dict:
        flow = self._latest_flow(project_id)
        working = list(self.session.scalars(
            select(Task).where(Task.project_id == project_id, Task.status == TaskStatus.WORKING)
            .order_by(Task.created_at, Task.id)
        ))
        completed: list[str] = []
        reviews: list[dict] = []

        for task in working:
            owner = self.session.get(Agent, task.owner_agent_id)
            if owner is None:
                raise RuntimeError(f"task {task.id} has no available owner")
            runner = self.runners[owner.id]
            run_id = uuid.uuid4()
            started = self.bus.emit(
                project_id=project_id,
                event_type="agent.run.started",
                actor=owner.id,
                correlation_id=flow,
                payload={
                    "run_id": str(run_id),
                    "agent_id": owner.id,
                    "task_id": str(task.id),
                    "objective": task.description,
                    "input": {"acceptance_criteria": task.acceptance_criteria},
                },
            )
            result = runner.run(
                AgentRunRequest(
                    run_id=str(run_id),
                    agent=owner.id,
                    role=owner.role,
                    objective=task.description,
                    context_package={"acceptance_criteria": task.acceptance_criteria, "task_id": str(task.id)},
                )
            )
            finished = self.bus.emit(
                project_id=project_id,
                event_type="agent.run.completed",
                actor=owner.id,
                correlation_id=flow,
                causation_id=started.id,
                payload={"run_id": str(run_id), "output": {"summary": result.summary}},
            )
            self.agents.set_state(
                project_id=project_id,
                agent=owner,
                state=AgentState.WAITING,
                current_task_id=task.id,
                correlation_id=flow,
                causation_id=finished.id,
            )

            reviewer = self._available_reviewer(owner.id)
            review = self.reviews.request(
                task=task,
                creator_agent_id=owner.id,
                reviewer_agent_id=reviewer.id,
                correlation_id=flow,
                causation_id=finished.id,
            )
            self.agents.set_state(
                project_id=project_id,
                agent=reviewer,
                state=AgentState.REVIEWING,
                current_task_id=task.id,
                correlation_id=flow,
            )

            review_run_id = uuid.uuid4()
            review_started = self.bus.emit(
                project_id=project_id,
                event_type="agent.run.started",
                actor=reviewer.id,
                correlation_id=flow,
                payload={
                    "run_id": str(review_run_id),
                    "agent_id": reviewer.id,
                    "task_id": str(task.id),
                    "objective": f"Independently review task: {task.title}",
                    "input": {"creator_summary": result.summary, "acceptance_criteria": task.acceptance_criteria},
                },
            )
            review_result = self.runners[reviewer.id].run(
                AgentRunRequest(
                    run_id=str(review_run_id),
                    agent=reviewer.id,
                    role=reviewer.role,
                    objective=f"Independently review task: {task.title}",
                    context_package={"creator_summary": result.summary, "acceptance_criteria": task.acceptance_criteria},
                )
            )
            review_finished = self.bus.emit(
                project_id=project_id,
                event_type="agent.run.completed",
                actor=reviewer.id,
                correlation_id=flow,
                causation_id=review_started.id,
                payload={"run_id": str(review_run_id), "output": {"summary": review_result.summary}},
            )
            self.reviews.accept(
                review=review,
                task=task,
                summary=review_result.summary,
                findings=list(review_result.findings),
                correlation_id=flow,
                causation_id=review_finished.id,
            )
            self.agents.set_state(project_id=project_id, agent=reviewer, state=AgentState.IDLE, correlation_id=flow)
            self.agents.set_state(project_id=project_id, agent=owner, state=AgentState.IDLE, correlation_id=flow)
            completed.append(str(task.id))
            reviews.append({"task_id": str(task.id), "reviewer": reviewer.id})

        promoted = self.scheduler.promote_ready(project_id=project_id, correlation_id=flow)
        assigned = self.scheduler.assign_ready(project_id=project_id, correlation_id=flow)
        self.session.commit()
        return {
            "completed_tasks": completed,
            "reviews": reviews,
            "promoted_tasks": [str(t.id) for t in promoted],
            "assignments": [{"task_id": str(t.id), "agent_id": a.id} for t, a in assigned],
        }

    def run_until_idle(self, project_id: uuid.UUID, max_cycles: int = 12) -> dict:
        cycles = []
        for _ in range(max_cycles):
            result = self.run_cycle(project_id)
            cycles.append(result)
            remaining = self.session.scalar(
                select(Task.id).where(
                    Task.project_id == project_id,
                    Task.status.in_([TaskStatus.WORKING, TaskStatus.READY, TaskStatus.TODO, TaskStatus.REVIEW]),
                ).limit(1)
            )
            if remaining is None:
                break
            if not result["completed_tasks"] and not result["assignments"] and not result["promoted_tasks"]:
                break
        return {"cycles": cycles, "state": self.state_snapshot(project_id)}

    def state_snapshot(self, project_id: uuid.UUID) -> dict:
        project = self.session.get(Project, project_id)
        if project is None:
            raise KeyError(str(project_id))
        agents = list(self.session.scalars(select(Agent).order_by(Agent.id)))
        tasks = list(self.session.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at, Task.id)))
        meetings = list(self.session.scalars(select(Meeting).where(Meeting.project_id == project_id).order_by(Meeting.created_at.desc())))
        decisions = list(self.session.scalars(select(Decision).where(Decision.project_id == project_id).order_by(Decision.created_at.desc())))
        reviews = list(self.session.scalars(select(Review).where(Review.project_id == project_id).order_by(Review.created_at.desc())))
        artifacts = list(self.session.scalars(select(Artifact).where(Artifact.project_id == project_id).order_by(Artifact.created_at.desc())))
        latest_events = list(self.session.scalars(
            select(Event).where(Event.project_id == project_id).order_by(Event.timestamp.desc(), Event.id.desc()).limit(100)
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
                    "display_name": AGENT_DISPLAY.get(a.id, {}).get("name", a.id),
                    "display_role": AGENT_DISPLAY.get(a.id, {}).get("role", a.role),
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
            "decisions": [
                {
                    "id": str(d.id),
                    "key": d.decision_key,
                    "decision": d.decision,
                    "reason": d.reason,
                    "rejected": d.rejected_json,
                    "impacts": d.impacts_json,
                    "markdown_path": d.markdown_path,
                    "created_at": d.created_at.isoformat(),
                }
                for d in decisions
            ],
            "reviews": [
                {
                    "id": str(r.id),
                    "task_id": str(r.task_id),
                    "creator_agent_id": r.creator_agent_id,
                    "reviewer_agent_id": r.reviewer_agent_id,
                    "status": r.status.value,
                    "summary": r.summary,
                    "findings": r.findings_json,
                    "created_at": r.created_at.isoformat(),
                }
                for r in reviews
            ],
            "artifacts": [
                {
                    "id": str(a.id),
                    "task_id": str(a.task_id) if a.task_id else None,
                    "type": a.artifact_type.value,
                    "ref": a.ref,
                    "metadata": a.metadata_json,
                    "created_at": a.created_at.isoformat(),
                }
                for a in artifacts
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
