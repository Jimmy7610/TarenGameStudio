from __future__ import annotations

from database.enums import AgentState, TaskStatus


class InvalidTransitionError(ValueError):
    pass


TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.TODO: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.WORKING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.WORKING: {TaskStatus.REVIEW, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.REVIEW: {TaskStatus.WORKING, TaskStatus.DONE, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.WORKING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.FAILED: set(),
    TaskStatus.DONE: set(),
    TaskStatus.CANCELLED: set(),
}


AGENT_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.OFFLINE: {AgentState.IDLE},
    AgentState.IDLE: {AgentState.WORKING, AgentState.REVIEWING, AgentState.TESTING, AgentState.MEETING, AgentState.WAITING, AgentState.OFFLINE},
    AgentState.WORKING: {AgentState.IDLE, AgentState.REVIEWING, AgentState.TESTING, AgentState.MEETING, AgentState.WAITING, AgentState.BLOCKED, AgentState.OFFLINE},
    AgentState.REVIEWING: {AgentState.IDLE, AgentState.WORKING, AgentState.MEETING, AgentState.WAITING, AgentState.BLOCKED, AgentState.OFFLINE},
    AgentState.TESTING: {AgentState.IDLE, AgentState.WORKING, AgentState.MEETING, AgentState.WAITING, AgentState.BLOCKED, AgentState.OFFLINE},
    AgentState.MEETING: {AgentState.IDLE, AgentState.WORKING, AgentState.REVIEWING, AgentState.WAITING, AgentState.BLOCKED, AgentState.OFFLINE},
    AgentState.WAITING: {AgentState.IDLE, AgentState.WORKING, AgentState.REVIEWING, AgentState.TESTING, AgentState.MEETING, AgentState.BLOCKED, AgentState.OFFLINE},
    AgentState.BLOCKED: {AgentState.IDLE, AgentState.MEETING, AgentState.OFFLINE},
}


def ensure_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target not in TASK_TRANSITIONS[current]:
        raise InvalidTransitionError(f"invalid task transition: {current} -> {target}")


def ensure_agent_transition(current: AgentState, target: AgentState) -> None:
    if target not in AGENT_TRANSITIONS[current]:
        raise InvalidTransitionError(f"invalid agent transition: {current} -> {target}")
