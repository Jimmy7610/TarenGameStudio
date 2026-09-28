# Taren Game Studio

Taren Game Studio is an AI-native game-production orchestrator. Multiple specialized AI agents collaborate through a deterministic orchestration core, shared Git history, structured decisions, reviews, and a realtime HQ.

## Current milestone

**Game Studio Core v0.1 — Phase 0–1**

Implemented in this baseline:
- frozen `ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md`
- SQLAlchemy persistence model
- Alembic migration foundation
- PostgreSQL append-only protection for the event store
- event lineage with `project_id`, `correlation_id`, and `causation_id`
- explicit tables for agent runs, reviews, task dependencies, artifacts, meetings, decisions, and idempotency keys
- tested `EventStore`

The next milestone is reducers, task/agent lifecycles, scheduler, and `FakeAgentRunner`.
