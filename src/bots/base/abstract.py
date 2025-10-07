from abc import ABC, abstractmethod
from core.Database import Database
from core.S3Storage import S3Storage
import sys
from utils.types import Score
from core.DatabotRole import DatabotRole

class AbstractDatabot(ABC):
    NAME: str = None
    DESCRIPTION: str = None
    VERSION: int = None
    ROLE: DatabotRole = None
    DB_ID: int = None
    DATABASE: Database = None

    def __init__(self):
        if self.NAME is None:
            raise ValueError(f"{self.__class__.__name__} must define a NAME class attribute")
        if self.DESCRIPTION is None:
            raise ValueError(f"{self.__class__.__name__} must define a DESCRIPTION class attribute")
        if self.VERSION is None:
            raise ValueError(f"{self.__class__.__name__} must define a VERSION class attribute")
        if self.ROLE is None:
            raise ValueError(f"{self.__class__.__name__} must define a ROLE class attribute")
        self.DATABASE = Database()

        try:
            db_id = self.DATABASE.register_databot(self.NAME, self.DESCRIPTION, self.VERSION, self.ROLE.value)
            if db_id is None:
                print(f"❌ Registration of databot '{self.NAME}' failed – probably higher version already registered?", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"❌ Registration error for bot '{self.NAME}': {e}", file=sys.stderr)
            sys.exit(1)

        self.DB_ID = db_id
        self.s3storage = S3Storage()
        print(f"Databot ID:{self.DB_ID} name:{self.NAME} is running...")

    @abstractmethod
    def compute(self, image_local_path: str) -> Score:
        pass

    def run(self):
        records = self.DATABASE.fetch_records(self.DB_ID)
        # print(records)
        # exit()
        for record in records:
            rec_id = record["id"]
            thumb_key = record["databot_thumb_filename"]
            local_path = None
            try:
                local_path = self.s3storage.download_file(thumb_key)

                result = self.compute(local_path)

                self.DATABASE.save_success_result(self.DB_ID, rec_id, result)
                # print(f"✅ {rec_id} -> {result}")
            except Exception as e:
                self.DATABASE.save_error_result(self.DB_ID, rec_id, str(e))
                print(f"❌ {rec_id} -> {e}")
            finally:
                if local_path:
                    self.s3storage.cleanup_file(local_path)