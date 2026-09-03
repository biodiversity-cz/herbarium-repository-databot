from bots.base.abstract import AbstractDatabot
from core.domain.DatabotRole import DatabotRole
from core.infrastructure.storage.s3_storage import BucketType
from utils.types import Score
import logging
import os
import tempfile
import requests

from config import config

logger = logging.getLogger(__name__)


class VouvisDatabot(AbstractDatabot):
    NAME = "vouvis_v1_sheet_detector"
    DESCRIPTION = (
        "Detect bounding boxes of herbarium sheet components "
        "(labels, stamps, handwriting, etc.) using a VoucherVision model "
        "and proceed DarwinCore transcription using Qwen3.5 model."
    )
    VERSION = 1
    ROLE = DatabotRole.SCANNER
    
    # URL pro API endpoint - upravte podle potřeby
    API_ENDPOINT = "http://vouvis-herbarium-svc/v1/transcribe-full"

    def selectRecords(self) -> dict:
        return self.DATABASE.fetch_records(self.DB_ID, 2)

    def compute(self, image_local_path: str, record: dict) -> Score:
        pass

    def run(self):
        # Spojení patří connection poolu - žádný finally close.
        records = self.selectRecords()
        logger.info("%s: %s record(s) to process", self.NAME, len(records) if records else 0)

        for record in records:
            rec_id = record["id"]
            local_path = None
            try:
                # Získání klíče fullsize obrázku z databáze
                fullsize_key = record.get("archive_filename")
                bucket_suffix = record.get("bucket_suffix", "")

                if not fullsize_key:
                    raise ValueError("Missing fullsize filename for record {}".format(rec_id))

                # Vytvoření dočasného souboru pro stažení fullsize obrázku
                fd, local_path = tempfile.mkstemp(suffix=os.path.splitext(fullsize_key)[-1])
                os.close(fd)

                # Stažení fullsize obrázku z S3
                self.s3storage.download_file_to_path(
                    BucketType.FULLSIZE,
                    bucket_suffix,
                    fullsize_key,
                    local_path
                )

                # POST request na API s fullsize obrázkem
                with open(local_path, 'rb') as f:
                    photo = {'file': (os.path.basename(local_path), f, 'image/tiff')}
                    # Transkripce trvá - krátký connect timeout, dlouhý read timeout.
                    response = requests.post(
                        self.API_ENDPOINT,
                        files=photo,
                        timeout=config.get_http_timeout("ml_read_timeout", 600),
                    )

                # Kontrola status kodu
                if response.status_code == 200:
                    result = response.json()
                    # Uložení úspěšného výsledku
                    self.DATABASE.save_success_result(self.DB_ID, rec_id, result)
                else:
                    error_msg = f"API returned status {response.status_code}: {response.text}"
                    raise Exception(error_msg)

            except Exception as e:
                # Uložení chybového výsledku
                self.DATABASE.save_error_result(self.DB_ID, rec_id, str(e))
                logger.error("❌ %s -> %s", rec_id, e)
            finally:
                # Vyčištění dočasného souboru
                if local_path:
                    try:
                        os.remove(local_path)
                    except FileNotFoundError:
                        pass

