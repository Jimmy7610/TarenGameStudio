from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.enums import Priority, TaskStatus
from database.models import Event, Task, TaskDependency
from orchestrator.transitions import ensure_task_transition


class TaskReducer:
    def apply(self, session: Session, event: Event) -> Task | None:
        p = event.payload_json
        et = event.event_type

        if et == "task.created":
            task = Task(
                id=uuid.UUID(p["task_id"]),
                project_id=event.project_id,
                title=p["title"],
                description=p.get("description", ""),
                status=TaskStatus.TODO,
                priority=Priority(p.get("priority", Priority.MEDIUM.value)),
                owner_agent_id=p.get("owner_agent_id"),
                acceptance_criteria=p.get("acceptance_criteria", []),
                max_rework_cycles=int(p.get("max_rework_cycles", 3)),
                rework_count=0,
            )
            session.add(task)
            session.flush()
            for dep in p.get("depends_on", []):
                session.add(TaskDependency(task_id=task.id, depends_on_task_id=uuid.UUID(dep)))
            session.flush()
            return task

        task_id = p.get("task_id")
        if not task_id:
            return None
        task = session.get(Task, uuid.UUID(task_id))
        if task is None:
            raise KeyError(f"unknown task: {task_id}")

        if et == "task.assigned":
            task.owner_agent_id = p["agent_id"]
        elif et == "task.ready":
            ensure_task_transition(task.status, TaskStatus.READY)
            task.status = TaskStatus.READY
        elif et == "task.started":
            ensure_task_transition(task.status, TaskStatus.WORKING)
            task.status = TaskStatus.WORKING
        elif et == "review.requested":
            ensure_task_transition(task.status, TaskStatus.REVIEW)
            task.status = TaskStatus.REVIEW
        elif et == "review.rejected":
            ensure_task_transition(task.status, TaskStatus.WORKING)
            task.status = TaskStatus.WORKING
            task.rework_count += 1
        elif et == "review.accepted" or et == "task.completed":
            if task.status != TaskStatus.DONE:
                ensure_task_transition(task.status, TaskStatus.DONE)
                task.status = TaskStatus.DONE
        elif et == "task.blocked":
            ensure_task_transition(task.status, TaskStatus.BLOCKED)
            task.status = TaskStatus.BLOCKED
        elif et == "task.failed":
            ensure_task_transition(task.status, TaskStatus.FAILED)
            task.status = TaskStatus.FAILED
        elif et == "task.cancelled":
            ensure_task_transition(task.status, TaskStatus.CANCELLED)
            task.status = TaskStatus.CANCELLED
        else:
            return None

        task.version += 1
        session.flush()
        return task
