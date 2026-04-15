from bots.base.abstract import AbstractDatabot
from core.domain.DatabotRole import DatabotRole
from services.hespiv1_sheet_service import HespiV1SheetService


class HespiBboxDetectorDatabot(AbstractDatabot):
    NAME = "hespi_v1_sheet_detector"
    DESCRIPTION = (
        "Detect bounding boxes of herbarium sheet components "
        "(labels, stamps, handwriting, etc.) using a YOLO model "
        "derived from the hespi project. Output is in COCO JSON format."
    )
    VERSION = 1
    ROLE = DatabotRole.SCANNER
    DEVICE = "cpu"  # Default, can be overridden by BotScheduler
    SERVICE = None

    def __init__(self):
        super().__init__()
        self.SERVICE = HespiV1SheetService(device=self.DEVICE)

    def selectRecords(self) -> dict:
        return self.DATABASE.fetch_specimen_type_records(self.DB_ID, 50)

    def compute(self, path: str, record: dict) -> dict:
        return self.SERVICE.detect_from_file(path, record)
