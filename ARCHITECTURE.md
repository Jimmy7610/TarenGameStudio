# TAREN GAME STUDIO — ARCHITECTURE v0.1

**Status: FROZEN for Core v0.1**

## 01. Vision & Design Principles

Taren Game Studio is an autonomous AI-native game-production pipeline. A human owner supplies vision and high-level feedback; specialized agents collaborate to research, design, implement, review, test, and iterate toward a releasable PC game.

Core principles:

1. **Autonomous production, human authority.** Routine design, implementation, review, testing, and planning are automated. Money, legal commitments, external publishing, and owner veto remain human-gated.
2. **Constructive friction.** Important work is not self-approved. Agents review and challenge one another, with rotating Devil's Advocate duties for major decisions.
3. **Deterministic orchestration, creative intelligence.** Taren Orchestrator executes rules and workflows. It does not make creative game decisions.
4. **Events are immutable history; state is current reality.** Every state transition originates from an event.
5. **Traceability by default.** Every event belongs to a project and flow and may identify the event that caused it.
6. **Context is scoped.** Each agent receives only the context relevant to its objective.
7. **Visualizability.** The Game Studio HQ is a reactive client of orchestrator state and events.
8. **Recoverability and idempotency.** Restarts and repeated external deliveries must not corrupt state or duplicate work.

## 02. System Overview

The system has four primary parts:

- **Taren Orchestrator Core** — deterministic workflow, event store, state, guardrails, scheduling, recovery, and integration routing.
- **Agent Runners** — adapters for ChatGPT, Claude Code, Codex, and Antigravity behind one contract.
- **GitHub** — source of truth for code, long-lived Markdown knowledge, branches, pull requests, reviews, and build artifacts.
- **Taren Game Studio HQ** — a separate visual realtime client driven by state snapshots plus incremental events.

## 03. Canonical Data Flow

```text
COMMAND
  ↓
VALIDATION / IDEMPOTENCY
  ↓
EVENT (append-only)
  ↓
STATE REDUCER
  ↓
CURRENT STATE
  ↓
SCHEDULER / NEXT COMMANDS
  ↓
WEBSOCKET / SSE
  ↓
GAME STUDIO HQ
```

No state mutation is valid without a corresponding event.

## 04. Core Data Models

Persistent models:

- Project
- Event
- Agent
- AgentRun
- Task
- TaskDependency
- Review
- Meeting
- MeetingMessage
- Decision
- Artifact
- IdempotencyKey

State entities carry `created_at`, `updated_at`, and optimistic-concurrency `version` where applicable.

## 05. Event Model

Every event contains:

```json
{
  "id": "uuid",
  "schema_version": "0.1",
  "event_type": "task.started",
  "timestamp": "ISO-8601 UTC",
  "project_id": "uuid",
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "actor": "claude",
  "payload": {}
}
```

`project_id` scopes the game project. `correlation_id` groups a complete production flow. `causation_id` points to the event that directly caused the current event.

## 06. Event Families

Initial families include:

- `instruction.*`
- `agent.*`
- `task.*`
- `review.*`
- `meeting.*`
- `decision.*`
- `build.*`
- `playtest.*`
- `github.*`
- `system.*`

The protocol is versioned. Compatible additions retain the existing schema version; breaking changes require migration/version changes.

## 07. Event Immutability

The event store is append-only.

Allowed:
- INSERT
- SELECT

Forbidden:
- UPDATE
- DELETE

Protection exists at both application and PostgreSQL database level. Event corrections are represented by new compensating events, never mutation of old history.

## 08. Task Lifecycle

```text
TODO → READY → WORKING → REVIEW → DONE
                  ↘          ↘
                  BLOCKED     BLOCKED
                  FAILED      FAILED
                  CANCELLED   CANCELLED
```

Tasks include priority, acceptance criteria, owner, rework limits, dependencies, and produced artifacts.

Dependencies are explicit relational records, not only JSON metadata.

## 09. Agent State Model

Agents may be:

- IDLE
- WORKING
- REVIEWING
- TESTING
- MEETING
- WAITING
- BLOCKED
- OFFLINE

HQ presentation reacts to these states but does not own them.

## 10. Agent Runner Contract

All model-specific integrations implement the same logical contract.

Input:

```json
{
  "run_id": "uuid",
  "agent": "claude",
  "role": "lead_engineer",
  "objective": "...",
  "context_package": {},
  "allowed_actions": [],
  "expected_output": {}
}
```

Output:

```json
{
  "status": "completed",
  "summary": "...",
  "findings": [],
  "proposals": [],
  "artifacts": [],
  "requested_actions": [],
  "needs_meeting": false
}
```

The orchestrator must not depend on whether an implementation uses CLI, API, connector, local process, or a future runtime.

## 11. Context Package Builder

Each run receives a bounded context package composed from:

- `PROJECT_CHARTER.md`
- relevant current-state summary
- assigned task/objective
- acceptance criteria
- relevant source files
- relevant architecture documents
- relevant decisions
- directly related reviews/artifacts

The system does not dump the complete project history into every run.

## 12. Meetings & Decisions

Meeting types include:

- kickoff
- concept review
- architecture review
- conflict/problem meeting
- milestone review
- release review

Participants are dynamic. Kickoff normally includes all primary agents; later meetings include only relevant roles.

Major meetings assign a rotating Devil's Advocate.

Accepted decisions are persisted structurally and may also be materialized as `DEC-XXXX.md` in Git.

## 13. Review & Criticism

Important work cannot be accepted solely by its creator. Reviews record creator, reviewer, verdict, findings, and linked artifacts. The data model prevents a reviewer from being the same agent as the creator for normal agent-authored work.

## 14. Guardrails & Loop Limits

Tasks define `max_rework_cycles` and `rework_count`.

Default limit: 3.

When the limit is reached:

1. further automatic rework stops;
2. the task becomes blocked;
3. an architecture/problem meeting is required;
4. the issue must be resolved at a higher abstraction level.

## 15. Persistence & Recovery

Production persistence uses PostgreSQL.

No important state exists only in memory. On restart, the orchestrator reconstructs active work from persisted state and event history. Interrupted agent runs are reconciled explicitly rather than silently restarted.

## 16. Idempotency

External deliveries and commands can include an idempotency key. Repeated deliveries with the same key cannot create duplicate effects.

GitHub webhook delivery IDs are persisted as idempotency keys.

## 17. GitHub Integration

GitHub stores code and durable project knowledge. Agents work on isolated branches and submit changes for review. Expected flow:

```text
TASK → BRANCH → IMPLEMENT → TEST → COMMIT → PR → REVIEW → MERGE
```

The orchestrator consumes GitHub webhooks and normalizes them into internal events.

## 18. HQ Realtime Protocol

HQ is not a GitHub client and does not query AI products directly.

On connection:

1. `GET /api/studio/state` returns a current snapshot.
2. `WS /ws/events` streams incremental events.

HQ maps state/events to animation and UI.

## 19. Permissions & Authority

- **Owner (Jimmy):** ultimate authority; expenditure, publication, legal and commercial gates, veto.
- **ChatGPT / Game Director:** game vision, design, story, progression, product planning.
- **Claude Code / Lead Engineer:** architecture and implementation.
- **Codex / Engineering Review & QA:** review, tests, bugs, technical risk.
- **Antigravity / Experience & Visual:** gameplay feel, UI/UX, prototyping, visual evaluation.
- **Taren Orchestrator:** workflow execution only; no creative authority.

## 20. Protocol & Schema Versioning

Events and external state payloads contain schema versions. Breaking changes require explicit migrations and adapter compatibility handling.

## 21. Logging & Observability

The system records:

- agent run timing/status
- task timing/status
- event lineage
- failures and retries
- token/cost metadata when available
- artifacts and revisions

Secrets must never be copied into HQ event payloads or normal logs.

## 22. Failure Handling

Runner failures generate events and explicit run states. Retry policy is bounded. Repeated failures move work to BLOCKED and may require a problem meeting or owner attention.

## 23. Security

Credentials and tokens remain outside source control. Service credentials follow least privilege. Webhooks are authenticated. HQ receives normalized non-secret data only.

## 24. Future Playtesting Interface

Playtesting builds on the same event model:

- `playtest.started`
- `playtest.metric`
- `playtest.capture`
- `playtest.completed`

Future runners may execute the game, collect telemetry, capture screenshots/video, and create improvement tasks from experience reviews.
