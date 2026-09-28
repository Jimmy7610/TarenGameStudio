from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event as sa_event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, utcnow
from .enums import (
    AgentRunStatus,
    AgentState,
    ArtifactType,
    MeetingStatus,
    Priority,
    ProjectStatus,
    ReviewStatus,
    TaskStatus,
)


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, native_enum=False), default=ProjectStatus.CREATED, nullable=False
    )
    current_milestone: Mapped[str | None] = mapped_column(String(200))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_project_timestamp", "project_id", "timestamp"),
        Index("ix_events_correlation", "correlation_id", "timestamp"),
        Index("ix_events_causation", "causation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    schema_version: Mapped[str] = mapped_column(String(16), default="0.1", nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="RESTRICT")
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


@sa_event.listens_for(Event, "before_update", propagate=True)
def _prevent_event_update(mapper, connection, target) -> None:  # pragma: no cover - safety hook
    raise ValueError("Event rows are immutable and cannot be updated")


@sa_event.listens_for(Event, "before_delete", propagate=True)
def _prevent_event_delete(mapper, connection, target) -> None:  # pragma: no cover - safety hook
    raise ValueError("Event rows are immutable and cannot be deleted")


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[AgentState] = mapped_column(
        Enum(AgentState, native_enum=False), default=AgentState.OFFLINE, nullable=False
    )
    current_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False), default=TaskStatus.TODO, nullable=False, index=True
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False), default=Priority.MEDIUM, nullable=False
    )
    owner_agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="SET NULL")
    )
    acceptance_criteria: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    max_rework_cycles: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    rework_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("max_rework_cycles >= 0", name="ck_tasks_max_rework_nonnegative"),
        CheckConstraint("rework_count >= 0", name="ck_tasks_rework_nonnegative"),
    )


class TaskDependency(TimestampMixin, Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),
        CheckConstraint("task_id <> depends_on_task_id", name="ck_task_no_self_dependency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, native_enum=False), default=AgentRunStatus.QUEUED, nullable=False
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "creator_agent_id IS NULL OR reviewer_agent_id <> creator_agent_id",
            name="ck_review_not_self",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="SET NULL")
    )
    reviewer_agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False), default=ReviewStatus.REQUESTED, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    findings_json: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meeting_type: Mapped[str] = mapped_column(String(80), nullable=False)
    topic: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, native_enum=False), default=MeetingStatus.SCHEDULED, nullable=False
    )
    participants_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    devil_advocate_agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="SET NULL")
    )
    outcome_summary: Mapped[str | None] = mapped_column(Text)


class MeetingMessage(Base):
    __tablename__ = "meeting_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("meeting_id", "sequence", name="uq_meeting_message_sequence"),
        CheckConstraint("sequence >= 0", name="ck_meeting_message_sequence_nonnegative"),
    )


class Decision(TimestampMixin, Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_key: Mapped[str] = mapped_column(String(32), nullable=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("meetings.id", ondelete="SET NULL")
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_json: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    impacts_json: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    markdown_path: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint("project_id", "decision_key", name="uq_project_decision_key"),
    )


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("decisions.id", ondelete="SET NULL"), index=True
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, native_enum=False), nullable=False
    )
    ref: Mapped[str] = mapped_column(String(1000), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(128))
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
