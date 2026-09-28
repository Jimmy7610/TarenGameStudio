from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.base import utcnow
from database.enums import AgentRunStatus
from database.models import AgentRun, Event


class RunReducer:
    def apply(self, session: Session, event: Event) -> AgentRun | None:
        p = event.payload_json
        if event.event_type == "agent.run.started":
            run = AgentRun(
                id=uuid.UUID(p["run_id"]),
                project_id=event.project_id,
                agent_id=p["agent_id"],
                task_id=uuid.UUID(p["task_id"]) if p.get("task_id") else None,
                meeting_id=uuid.UUID(p["meeting_id"]) if p.get("meeting_id") else None,
                status=AgentRunStatus.RUNNING,
                objective=p["objective"],
                input_json=p.get("input", {}),
                started_at=utcnow(),
            )
            session.add(run)
            session.flush()
            return run

        if event.event_type == "agent.run.completed":
            run = session.get(AgentRun, uuid.UUID(p["run_id"]))
            if run is None:
                raise KeyError(f"unknown agent run: {p['run_id']}")
            run.status = AgentRunStatus.COMPLETED
            run.output_json = p.get("output", {})
            run.finished_at = utcnow()
            run.version += 1
            session.flush()
            return run

        if event.event_type == "agent.run.failed":
            run = session.get(AgentRun, uuid.UUID(p["run_id"]))
            if run is None:
                raise KeyError(f"unknown agent run: {p['run_id']}")
            run.status = AgentRunStatus.FAILED
            run.output_json = p.get("output", {})
            run.finished_at = utcnow()
            run.version += 1
            session.flush()
            return run

        return None
