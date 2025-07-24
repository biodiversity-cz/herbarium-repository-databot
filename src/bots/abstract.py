from abc import ABC, abstractmethod
from db import register_databot
import sys
from DatabotRole import DatabotRole

class AbstractDatabot(ABC):
    NAME: str = None
    DESCRIPTION: str = None
    VERSION: int = None
    ROLE: DatabotRole = None

    def __init__(self):
        if self.NAME is None:
            raise ValueError(f"{self.__class__.__name__} must define a NAME class attribute")
        if self.DESCRIPTION is None:
            raise ValueError(f"{self.__class__.__name__} must define a DESCRIPTION class attribute")
        if self.VERSION is None:
            raise ValueError(f"{self.__class__.__name__} must define a VERSION class attribute")
        if self.ROLE is None:
            raise ValueError(f"{self.__class__.__name__} must define a ROLE class attribute")

        try:
            success = register_databot(self.NAME, self.DESCRIPTION, self.VERSION, self.ROLE.value)
            if not success:
                print(f"❌ Registration of databot '{self.NAME}' failed – probably higher version already registered?", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"❌ Registration error for bot '{self.NAME}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Databot {self.NAME} runs...")

    @abstractmethod
    def run(self):
        pass
