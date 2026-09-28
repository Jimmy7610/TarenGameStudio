# TAREN GAME STUDIO — IMPLEMENTATION PLAN v0.1

**Status: APPROVED / Core build sequence locked**

## Goal

Build and verify the deterministic Game Studio Core before using paid/real AI agents. The first complete E2E target is Pong, but only after fake-runner verification.

## Phase 0 — Repository & Frozen Specification

Deliverables:

- `ARCHITECTURE.md`
- `IMPLEMENTATION_PLAN.md`
- `PROJECT_CHARTER.md`
- Python package/test skeleton
- Git repository on `main`

## Phase 1 — Persistence Foundation

Build in this order:

1. enums
2. database base/session foundation
3. SQLAlchemy models
4. Alembic configuration and initial migration
5. append-only EventStore
6. persistence tests

Required tables:

- projects
- events
- agents
- agent_runs
- tasks
- task_dependencies
- reviews
- meetings
- meeting_messages
- decisions
- artifacts
- idempotency_keys

Hard requirements:

- events are append-only
- event `causation_id` must reference an existing event when present
- state objects carry timestamps/version as applicable
- task dependencies use a relation table
- self-dependency is invalid
- important agent-authored work cannot be reviewed by the same agent

## Phase 2 — Reducers & State Machines

Implement pure/transactional reducers:

- ProjectReducer
- TaskReducer
- AgentReducer
- MeetingReducer
- ReviewReducer

Invariant:

> Every state transition must originate from a persisted event.

## Phase 3 — Task & Agent Lifecycles

Task states:

`TODO, READY, WORKING, REVIEW, DONE, BLOCKED, FAILED, CANCELLED`

Agent states:

`IDLE, WORKING, REVIEWING, TESTING, MEETING, WAITING, BLOCKED, OFFLINE`

Implement transition validation and dependency readiness.

## Phase 4 — FakeAgentRunner

Implement four deterministic fake runners:

- FakeChatGPT
- FakeClaude
- FakeCodex
- FakeAntigravity

They implement the exact AgentRunner contract and emit predefined outputs without external model calls.

## Phase 5 — Meetings & Decisions

Implement:

- kickoff
- concept review
- architecture review
- conflict meeting
- milestone review
- release review
- rotating Devil's Advocate
- structured decision materialization

## Phase 6 — Scheduler

Scheduler responsibilities:

- determine READY tasks
- honor dependencies/priorities
- select eligible/available agents
- request required reviews
- stop rework loops
- trigger meetings when guardrails require escalation

## Phase 7 — API & Realtime

Initial endpoints:

- `POST /api/projects`
- `POST /api/projects/{id}/prompt`
- `GET /api/studio/state`
- `POST /api/webhooks/github`
- `GET /api/tasks`
- `GET /api/meetings`
- `WS /ws/events`

HQ receives a snapshot first and incremental events after.

## Phase 8 — Minimal Game Studio HQ

Reuse the existing HQ technology as a separate application/data domain.

First version visualizes:

- agent states and positions
- active tasks
- meetings
- blockers
- latest events
- project/build summary

No direct GitHub or model API calls from HQ.

## Phase 9 — GitHub Integration

Normalize:

- push
- pull request
- review
- merge
- build/check events

Use GitHub delivery IDs for idempotency.

## Phase 10 — Runner Verification Ladder

### Test Level 1

Four fake runners.

Proves orchestrator, event flow, state, meetings, scheduler, realtime, and HQ without model variability.

### Test Level 2

One real runner + three fake runners.

Proves the adapter/runner boundary.

### Test Level 3

Four real integrations.

Proves actual multi-agent collaboration.

## Phase 11 — Pong End-to-End Verification

Owner prompt:

> Create a very simple Pong game for Windows.

Expected chain:

`PROMPT → KICKOFF → DISCUSSION → DECISION → TASKS → IMPLEMENTATION → REVIEW → REWORK → BUILD → HQ`

Pong is infrastructure verification, not the commercial product.

## Phase 12 — AI Playtesting

Add automated build execution, telemetry, screenshots/video, experience review, and improvement-task generation.

## Phase 13 — First Commercial Game

Owner prompt:

> Analyze the PC game market and build the game you jointly judge to have the strongest combination of commercial potential, feasibility, marketability, and fit for this AI studio. You have 99% creative freedom.

Pipeline:

`MARKET RESEARCH → CONCEPTS → ADVERSARIAL REVIEW → GREENLIGHT → GDD → TECHNICAL DESIGN → PROTOTYPE → PLAYTEST → VERTICAL SLICE → PRODUCTION → ALPHA → BETA → QA → RELEASE CANDIDATE`
