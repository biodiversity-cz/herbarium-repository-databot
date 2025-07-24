from bots.abstract import AbstractDatabot
from DatabotRole import DatabotRole

class ConnectionTester(AbstractDatabot):
    NAME = "connection_tester"
    DESCRIPTION = "Test database connection from Databot container to the repository"
    VERSION = 2
    ROLE = DatabotRole.VALIDATOR

    def run(self):
        print(f"do something")
