from src.bots.base.abstract_url import AbstractUrlDatabot
from src.core.domain.DatabotRole import DatabotRole
from src.services.cetaf_sid_service import CetafSidService


class CetafMetadataDatabot(AbstractUrlDatabot):
    NAME = "cetaf_metadata"
    DESCRIPTION = "Harvest specimen metadata from CETAF SID endpoint to keep these data available and actual for public search via repository or NMA"
    VERSION = 1
    ROLE = DatabotRole.SCANNER

    def selectRecords(self) -> dict:
        return self.DATABASE.records_with_specimen(self.DB_ID, 50)

    def get_url(self, record: dict) -> str:
        return record["specimen_pid"]

    def fetch_data_from_url(self, url: str) -> dict:
        client = CetafSidService()
        return client.fetch_sid_as_dict(url)






