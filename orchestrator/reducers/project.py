from __future__ import annotations

from sqlalchemy.orm import Session

from database.enums import ProjectStatus
from database.models import Event, Project


_EVENT_TO_STATUS = {
    "project.activated": ProjectStatus.ACTIVE,
    "project.ready": ProjectStatus.READY,
    "project.paused": ProjectStatus.PAUSED,
    "project.completed": ProjectStatus.COMPLETED,
    "project.cancelled": ProjectStatus.CANCELLED,
}

_ALLOWED = {
    ProjectStatus.CREATED: {ProjectStatus.ACTIVE, ProjectStatus.CANCELLED},
    ProjectStatus.ACTIVE: {ProjectStatus.READY, ProjectStatus.PAUSED, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED},
    ProjectStatus.READY: {ProjectStatus.ACTIVE, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED},
    ProjectStatus.PAUSED: {ProjectStatus.ACTIVE, ProjectStatus.CANCELLED},
    ProjectStatus.COMPLETED: set(),
    ProjectStatus.CANCELLED: set(),
}


class ProjectReducer:
    def apply(self, session: Session, event: Event) -> Project | None:
        target = _EVENT_TO_STATUS.get(event.event_type)
        if target is None:
            return None

        project = session.get(Project, event.project_id)
        if project is None:
            raise KeyError(f"unknown project: {event.project_id}")

        if project.status == target:
            return project
        if target not in _ALLOWED.get(project.status, set()):
            raise ValueError(f"invalid project transition: {project.status.value} -> {target.value}")

        project.status = target
        project.version += 1
        session.flush()
        return project
