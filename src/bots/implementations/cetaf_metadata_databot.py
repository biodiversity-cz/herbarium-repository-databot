from bots.base.abstract_url import AbstractUrlDatabot
from core.domain.DatabotRole import DatabotRole
from services.cetaf_sid_service import CetafSidService


class CetafMetadataDatabot(AbstractUrlDatabot):
    NAME = "cetaf_metadata"
    DESCRIPTION = "Harvest specimen metadata from CETAF SID endpoint to keep these data available and actual for public search via repository or NMA"
    VERSION = 1
    ROLE = DatabotRole.SYNCHRONIZER

    def selectRecords(self) -> dict:
        return self.DATABASE.cetaf_harvest(self.DB_ID, 50)

    def get_url(self, record: dict) -> str:
        return record["specimen_pid"]

    def fetch_data_from_url(self, url: str) -> dict:
        client = CetafSidService()
        return client.fetch_sid_as_dict(url)

    def run(self):
        records = self.selectRecords()
        for record in records:
            rec_id = record["id"]
            try:
                # Get the URL for this record
                url = self.get_url(record)

                # Fetch data from the URL
                data = self.fetch_data_from_url(url)

                # Process the data
                result = self.compute(data)

                # UPSERT successful result
                self.DATABASE.upsert_success_result(self.DB_ID, rec_id, result)
            except Exception as e:
                # Save error result
                self.DATABASE.save_error_result(self.DB_ID, rec_id, str(e))
                print(f"❌ {rec_id} -> {e}")





