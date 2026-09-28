from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import AgentState, Priority, TaskStatus
from database.models import Agent, Task, TaskDependency
from orchestrator.agent_service import AgentService
from orchestrator.task_service import TaskService


_PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


class Scheduler:
    """Deterministic v0.1 scheduler. No creative decisions live here."""

    def __init__(self, session: Session):
        self.session = session
        self.tasks = TaskService(session)
        self.agents = AgentService(session)

    def dependencies_satisfied(self, task: Task) -> bool:
        dep_ids = list(self.session.scalars(
            select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == task.id)
        ))
        if not dep_ids:
            return True
        deps = list(self.session.scalars(select(Task).where(Task.id.in_(dep_ids))))
        return len(deps) == len(dep_ids) and all(x.status == TaskStatus.DONE for x in deps)

    def promote_ready(self, *, project_id: uuid.UUID, correlation_id: uuid.UUID) -> list[Task]:
        candidates = list(self.session.scalars(
            select(Task).where(Task.project_id == project_id, Task.status == TaskStatus.TODO)
        ))
        promoted: list[Task] = []
        for task in candidates:
            if self.dependencies_satisfied(task):
                self.tasks.mark_ready(task, actor="orchestrator", correlation_id=correlation_id)
                promoted.append(task)
        return promoted

    def assign_ready(self, *, project_id: uuid.UUID, correlation_id: uuid.UUID) -> list[tuple[Task, Agent]]:
        ready = list(self.session.scalars(
            select(Task).where(Task.project_id == project_id, Task.status == TaskStatus.READY)
        ))
        ready.sort(key=lambda t: (_PRIORITY_ORDER[t.priority], t.created_at, str(t.id)))
        idle = list(self.session.scalars(select(Agent).where(Agent.state == AgentState.IDLE)))
        idle.sort(key=lambda a: a.id)

        assignments: list[tuple[Task, Agent]] = []
        for task in ready:
            agent = None
            if task.owner_agent_id:
                agent = next((a for a in idle if a.id == task.owner_agent_id), None)
            elif idle:
                agent = idle[0]
            if agent is None:
                continue
            assign_event = self.tasks.assign(task, agent.id, actor="orchestrator", correlation_id=correlation_id)
            self.tasks.start(task, actor="orchestrator", correlation_id=correlation_id, causation_id=assign_event.id)
            self.agents.set_state(
                project_id=project_id,
                agent=agent,
                state=AgentState.WORKING,
                current_task_id=task.id,
                correlation_id=correlation_id,
            )
            assignments.append((task, agent))
            idle.remove(agent)
        return assignments
