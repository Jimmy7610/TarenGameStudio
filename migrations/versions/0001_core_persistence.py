"""core persistence foundation

Revision ID: 0001
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_milestone", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("causation_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="RESTRICT")),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_events_project_timestamp", "events", ["project_id", "timestamp"])
    op.create_index("ix_events_correlation", "events", ["correlation_id", "timestamp"])
    op.create_index("ix_events_causation", "events", ["causation_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])

    # PostgreSQL-level enforcement. Application hooks add a second line of defense.
    op.execute("""
    CREATE OR REPLACE FUNCTION tgs_forbid_event_mutation()
    RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'events is append-only: % is forbidden', TG_OP;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_events_append_only
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION tgs_forbid_event_mutation();
    """)

    op.create_table(
        "agents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("current_task_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False),
        sa.Column("owner_agent_id", sa.String(64), sa.ForeignKey("agents.id", ondelete="SET NULL")),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("max_rework_cycles", sa.Integer(), nullable=False),
        sa.Column("rework_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("max_rework_cycles >= 0", name="ck_tasks_max_rework_nonnegative"),
        sa.CheckConstraint("rework_count >= 0", name="ck_tasks_rework_nonnegative"),
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_foreign_key(
        "fk_agents_current_task", "agents", "tasks", ["current_task_id"], ["id"], ondelete="SET NULL"
    )
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depends_on_task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),
        sa.CheckConstraint("task_id <> depends_on_task_id", name="ck_task_no_self_dependency"),
    )
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index("ix_task_dependencies_depends_on_task_id", "task_dependencies", ["depends_on_task_id"])

    op.create_table(
        "meetings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_type", sa.String(80), nullable=False),
        sa.Column("topic", sa.String(400), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("participants_json", sa.JSON(), nullable=False),
        sa.Column("devil_advocate_agent_id", sa.String(64), sa.ForeignKey("agents.id", ondelete="SET NULL")),
        sa.Column("outcome_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_meetings_project_id", "meetings", ["project_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_task_id", "agent_runs", ["task_id"])
    op.create_index("ix_agent_runs_meeting_id", "agent_runs", ["meeting_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_agent_id", sa.String(64), sa.ForeignKey("agents.id", ondelete="SET NULL")),
        sa.Column("reviewer_agent_id", sa.String(64), sa.ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("creator_agent_id IS NULL OR reviewer_agent_id <> creator_agent_id", name="ck_review_not_self"),
    )
    op.create_index("ix_reviews_task_id", "reviews", ["task_id"])

    op.create_table(
        "meeting_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "sequence", name="uq_meeting_message_sequence"),
        sa.CheckConstraint("sequence >= 0", name="ck_meeting_message_sequence_nonnegative"),
    )
    op.create_index("ix_meeting_messages_meeting_id", "meeting_messages", ["meeting_id"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_key", sa.String(32), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id", ondelete="SET NULL")),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rejected_json", sa.JSON(), nullable=False),
        sa.Column("impacts_json", sa.JSON(), nullable=False),
        sa.Column("markdown_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("project_id", "decision_key", name="uq_project_decision_key"),
    )
    op.create_index("ix_decisions_project_id", "decisions", ["project_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("agent_run_id", sa.Uuid(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL")),
        sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("decisions.id", ondelete="SET NULL")),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("ref", sa.String(1000), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"])
    op.create_index("ix_artifacts_agent_run_id", "artifacts", ["agent_run_id"])
    op.create_index("ix_artifacts_decision_id", "artifacts", ["decision_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(300), primary_key=True),
        sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(128)),
        sa.Column("response_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("artifacts")
    op.drop_table("decisions")
    op.drop_table("meeting_messages")
    op.drop_table("reviews")
    op.drop_table("agent_runs")
    op.drop_table("meetings")
    op.drop_table("task_dependencies")
    op.drop_constraint("fk_agents_current_task", "agents", type_="foreignkey")
    op.drop_table("tasks")
    op.drop_table("agents")
    op.execute("DROP TRIGGER IF EXISTS trg_events_append_only ON events")
    op.execute("DROP FUNCTION IF EXISTS tgs_forbid_event_mutation()")
    op.drop_table("events")
    op.drop_table("projects")
