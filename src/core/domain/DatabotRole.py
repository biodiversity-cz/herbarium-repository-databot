from enum import Enum

class DatabotRole(str, Enum):
    EXPORTER = "exporter"
    VALIDATOR = "validator"
    SCANNER = "scanner"