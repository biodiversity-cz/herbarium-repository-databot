import logging

from bots.base.abstract import AbstractDatabot
from core.domain.DatabotRole import DatabotRole
from utils.types import Score

logger = logging.getLogger(__name__)


class DatabaseConnectionTestDatabot(AbstractDatabot):
    NAME = "database_connection_tester"
    DESCRIPTION = "Test database connection from Databot container to the repository"
    VERSION = 2
    ROLE = DatabotRole.VALIDATOR

    def compute(self, image_local_path: str, record: dict) -> Score:
        pass

    def run(self):
        """Provéří, že se databot dostane do databáze přes connection pool."""
        row = self.DATABASE.fetchone("SELECT 1 AS ok")
        if not row or row["ok"] != 1:
            raise RuntimeError("Unexpected result while testing the database connection")
        logger.info("Connection successful, pool stats: %s", self.DATABASE.pool_stats())
