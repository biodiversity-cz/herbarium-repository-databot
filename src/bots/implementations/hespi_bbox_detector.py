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

    def __init__(self, config: dict = None):
        """
        Initialize the Hespi bounding box detector databot.

        Args:
            config: Bot-specific configuration with optional keys:
                   - weights_path: Path to the YOLO model weights
                   - conf_threshold: Confidence threshold for detections (0.0-1.0)
                   - device: Device to run inference on ('cpu', 'cuda', etc.)
        """
        super().__init__(config)
        # Extract config values with defaults
        weights_path = self.config.get("weights_path")
        conf_threshold = self.config.get("conf_threshold")
        device = self.config.get("device", "cpu")

        self.SERVICE = HespiV1SheetService(
            weights_path=weights_path,
            confidence_threshold=conf_threshold,
            device=device
        )

    def selectRecords(self) -> dict:
        return self.DATABASE.fetch_specimen_type_records(self.DB_ID, 50)

    def compute(self, path: str, record: dict) -> dict:
        return self.SERVICE.detect_from_file(path, record)
