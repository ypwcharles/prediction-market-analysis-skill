from enum import StrEnum


class RunType(StrEnum):
    SCAN = "scan"
    MONITOR = "monitor"
    REPORT = "report"


class RunStatus(StrEnum):
    RUNNING = "running"
    CLEAN = "clean"
    DEGRADED = "degraded"
    FAILED = "failed"
