import logging
from abc import ABC, abstractmethod

import requests

from bots.base.lifecycle import DatabotLifecycle
from core.domain.DatabotRole import DatabotRole
from core.infrastructure.database.url_database import UrlDatabase

logger = logging.getLogger(__name__)


class AbstractUrlDatabot(DatabotLifecycle, ABC):
    NAME: str = None
    DESCRIPTION: str = None
    VERSION: int = None
    ROLE: DatabotRole = None
    DATABASE_CLASS = UrlDatabase

    def __init__(self, config: dict = None):
        """
        Initialize the URL-based databot.

        Only cheap, connection-less state is created here. Registration happens
        lazily on the first access to DB_ID (inside run()), so constructing or
        enqueueing a bot no longer opens a database connection.

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
    def get_url(self, record: dict) -> str:
        """
        Generate the URL to fetch data for a given record.
        This method must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def fetch_data_from_url(self, url: str) -> dict:
        """
        Fetch data from the specified URL and return it as a dictionary.
        This method must be implemented by subclasses.
        """
        pass

    def compute(self, data: dict) -> dict:
        """
        Process the data fetched from the URL and return a data in final format.
        """
        return data

    def selectRecords(self) -> dict:
        """
        Provides rows from the database that are not yet processed by this bot..
        """
        return self.DATABASE.fetch_url_records(self.DB_ID)

    def run(self):
        """
        Main execution method that fetches records from the database,
        retrieves data from URLs, processes it, and saves results.

        Database connections are borrowed per statement from the shared pool,
        so nothing has to be closed here.
        """
        records = self.selectRecords()
        logger.info("%s: %s record(s) to process", self.NAME, len(records) if records else 0)

        for record in records:
            rec_id = record["id"]
            try:
                # Get the URL for this record
                url = self.get_url(record)

                # Fetch data from the URL
                data = self.fetch_data_from_url(url)

                # Process the data
                result = self.compute(data)

                # Save successful result
                self.DATABASE.save_success_result(self.DB_ID, rec_id, result)
            except Exception as e:
                # Save error result
                self.DATABASE.save_error_result(self.DB_ID, rec_id, str(e))
                logger.error("❌ %s: record %s -> %s", self.NAME, rec_id, e)