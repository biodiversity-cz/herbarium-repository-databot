from enum import Enum

class ResultStatus(Enum):
    OK = "ok"
    ERROR = "error"
    WARNING = 'warning'
    SKIPPED = 'skipped'
