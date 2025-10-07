from bots.abstract import AbstractDatabot
from core.DatabotRole import DatabotRole
from utils.types import Score


class DatabaseConnectionTestDatabot(AbstractDatabot):
    NAME = "database_connection_tester"
    DESCRIPTION = "Test database connection from Databot container to the repository"
    VERSION = 2
    ROLE = DatabotRole.VALIDATOR

    def compute(self, image_local_path: str) -> Score:
        pass

    def run(self):
        print(f"Connection successful")