from abc import ABC, abstractmethod
from core.UrlDatabase import UrlDatabase
import sys
from utils.types import Score
from core.DatabotRole import DatabotRole
import requests
import json


class AbstractUrlDatabot(ABC):
    NAME: str = None
    DESCRIPTION: str = None
    VERSION: int = None
    ROLE: DatabotRole = None
    DB_ID: int = None
    DATABASE: UrlDatabase = None

    def __init__(self):
        if self.NAME is None:
            raise ValueError(f"{self.__class__.__name__} must define a NAME class attribute")
        if self.DESCRIPTION is None:
            raise ValueError(f"{self.__class__.__name__} must define a DESCRIPTION class attribute")
        if self.VERSION is None:
            raise ValueError(f"{self.__class__.__name__} must define a VERSION class attribute")
        if self.ROLE is None:
            raise ValueError(f"{self.__class__.__name__} must define a ROLE class attribute")
        self.DATABASE = UrlDatabase()

        try:
            db_id = self.DATABASE.register_databot(self.NAME, self.DESCRIPTION, self.VERSION, self.ROLE.value)
            if db_id is None:
                print(f"❌ Registration of databot '{self.NAME}' failed – probably higher version already registered?", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"❌ Registration error for bot '{self.NAME}': {e}", file=sys.stderr)
            sys.exit(1)

        self.DB_ID = db_id
        print(f"Databot ID:{self.DB_ID} name:{self.NAME} is running...")

    @abstractmethod
    def compute(self, data: dict) -> Score:
        """
        Process the data fetched from the URL and return a Score.
        This method must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def get_data_url(self, record: dict) -> str:
        """
        Generate the URL to fetch data for a given record.
        This method must be implemented by subclasses.
        """
        pass

    def fetch_data_from_url(self, url: str) -> dict:
        """
        Fetch data from the specified URL and return it as a dictionary.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch data from {url}: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON from {url}: {e}")

    def run(self):
        """
        Main execution method that fetches records from the database,
        retrieves data from URLs, processes it, and saves results.
        """
        records = self.DATABASE.fetch_url_records(self.DB_ID)
        for record in records:
            rec_id = record["id"]
            try:
                # Get the URL for this record
                url = self.get_data_url(record)
                
                # Fetch data from the URL
                data = self.fetch_data_from_url(url)
                
                # Process the data
                result = self.compute(data)
                
                # Save successful result
                self.DATABASE.save_success_result(self.DB_ID, rec_id, result)
            except Exception as e:
                # Save error result
                self.DATABASE.save_error_result(self.DB_ID, rec_id, str(e))
                print(f"❌ {rec_id} -> {e}")