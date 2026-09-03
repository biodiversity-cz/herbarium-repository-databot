import logging
import os
import tempfile
from abc import ABC, abstractmethod

from bots.base.lifecycle import DatabotLifecycle
from core.infrastructure.database.database import Database
from core.infrastructure.storage.s3_storage import BucketType
from core.domain.DatabotRole import DatabotRole
from utils.types import Score

logger = logging.getLogger(__name__)


class AbstractDatabot(DatabotLifecycle, ABC):
    NAME: str = None
    DESCRIPTION: str = None
    VERSION: int = None
    ROLE: DatabotRole = None
    DATABASE_CLASS = Database

    def __init__(self, config: dict = None):
        """
        Initialize the databot.

        Only cheap, connection-less state is created here. The bot registers
        itself in the database lazily on the first access to DB_ID (which
        happens inside run()), so constructing or enqueueing a bot no longer
        opens a database connection.

        Args:
            config: Bot-specific configuration dictionary from config.yaml.
                   Can be None for bots that don't need additional configuration.
        """
        if self.NAME is None:
            raise ValueError(f"{self.__class__.__name__} must define a NAME class attribute")
        if self.DESCRIPTION is None:
            raise ValueError(f"{self.__class__.__name__} must define a DESCRIPTION class attribute")
        if self.VERSION is None:
            raise ValueError(f"{self.__class__.__name__} must define a VERSION class attribute")
        if self.ROLE is None:
            raise ValueError(f"{self.__class__.__name__} must define a ROLE class attribute")

        # Store bot-specific configuration (instance-level, not class-level)
        self.config = config or {}

    @abstractmethod
    def compute(self, image_local_path: str, record: dict) -> Score:
        pass

    def selectRecords(self) -> dict:
        """
        Provides rows from the database that are not yet processed by this bot..
        """
        return self.DATABASE.fetch_records(self.DB_ID)

    def run(self):
        """Process every pending record; connections are borrowed per statement."""
        records = self.selectRecords()
        logger.info("%s: %s record(s) to process", self.NAME, len(records) if records else 0)

        for record in records:
            rec_id = record["id"]
            thumb_key = record["databot_thumb_filename"]
            bucket_suffix = record["bucket_suffix"]
            local_path = None
            try:
                if not thumb_key:
                    raise ValueError(
                        f"Photo {rec_id} has no databot_thumb_filename, "
                        "there is nothing to download"
                    )

                # Vytvoř dočasný soubor pro stažení miniatury
                fd, local_path = tempfile.mkstemp(suffix=os.path.splitext(thumb_key)[-1])
                os.close(fd)

                # Stažení miniatury z thumb bucketu s suffixem pro číslování
                self.s3storage.download_file_to_path(
                    BucketType.THUMB,
                    bucket_suffix,
                    thumb_key,
                    local_path
                )

                result = self.compute(local_path, record)

                self.DATABASE.save_success_result(self.DB_ID, rec_id, result)
            except Exception as e:
                self.DATABASE.save_error_result(self.DB_ID, rec_id, str(e))
                logger.error("❌ %s: record %s -> %s", self.NAME, rec_id, e)
            finally:
                if local_path:
                    try:
                        os.remove(local_path)
                    except FileNotFoundError:
                        pass