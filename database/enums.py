from enum import StrEnum


class ProjectStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskStatus(StrEnum):
    TODO = "TODO"
    READY = "READY"
    WORKING = "WORKING"
    REVIEW = "REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentState(StrEnum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    REVIEWING = "REVIEWING"
    TESTING = "TESTING"
    MEETING = "MEETING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    OFFLINE = "OFFLINE"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgentRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReviewStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"


class MeetingStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class ArtifactType(StrEnum):
    COMMIT = "COMMIT"
    PULL_REQUEST = "PULL_REQUEST"
    FILE = "FILE"
    BUILD = "BUILD"
    SCREENSHOT = "SCREENSHOT"
    VIDEO = "VIDEO"
    REPORT = "REPORT"
    OTHER = "OTHER"
