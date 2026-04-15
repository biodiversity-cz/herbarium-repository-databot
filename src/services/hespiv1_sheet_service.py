import os
from pathlib import Path
from ultralytics import YOLO

DEFAULT_WEIGHTS_URL = (
    "https://github.com/rbturnbull/hespi/releases/download/v0.4.0/sheet-component.pt.gz"
)
DEFAULT_CONFIDENCE_THRESHOLD = 0.25
DEFAULT_DEVICE = "cpu"

SHEET_COMPONENT_CATEGORIES = [
    "small database label",
    "handwritten data",
    "stamp",
    "annotation label",
    "scale",
    "swing tag",
    "full database label",
    "database label",
    "swatch",
    "primary specimen label",
    "number",
]

# The trained YOLO model internally uses "institutional label";
# hespi remaps it to "primary specimen label" after loading.
MODEL_NAME_REMAP = {
    "institutional label": "primary specimen label",
}


def _default_weights_path() -> str:
    cache_dir = Path.home() / ".cache" / "hespi-bbox-detector"
    return str(cache_dir / "sheet-component.pt")


class HespiV1SheetService:
    """
    Detects herbarium sheet components via a YOLO model (Sheet-Component,
    11 classes) and produces a COCO JSON dict with bounding boxes.

    Model weights are resolved in this order:
      1. Constructor argument ``weights_path``
      2. Env var ``SHEET_COMPONENT_WEIGHTS_PATH``
      3. ``~/.cache/hespi-bbox-detector/sheet-component.pt``

    If the file does not exist at the resolved path it is automatically
    downloaded (and decompressed if ``.gz``) from the configured URL.
    """

    def __init__(
        self,
        weights_path: str | None = None,
        weights_url: str | None = None,
        confidence_threshold: float | None = None,
        imgsz: int = 1280,
        device: str | None = None,
    ):
        self.weights_path = (
            weights_path
            or os.environ.get("SHEET_COMPONENT_WEIGHTS_PATH")
            or _default_weights_path()
        )
        self.weights_url = (
            weights_url
            or os.environ.get("SHEET_COMPONENT_WEIGHTS_URL", DEFAULT_WEIGHTS_URL)
        )
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else float(os.environ.get("BBOX_CONFIDENCE_THRESHOLD", DEFAULT_CONFIDENCE_THRESHOLD))
        )
        self.device = device or os.environ.get("HESPI_DEVICE", DEFAULT_DEVICE)
        self.imgsz = imgsz
        self._model: YOLO | None = None



    def _get_model(self) -> YOLO:
        if self._model is None:
            weights = self.weights_path
            self._model = YOLO(weights)
            # Use configured device (defaults to CPU to avoid CUDA compatibility issues)
            self._model.to(self.device)
            self._model.model.names = {
                key: MODEL_NAME_REMAP.get(name, name)
                for key, name in self._model.names.items()
            }
        return self._model

    # ------------------------------------------------------------------
    # COCO helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_categories() -> list[dict]:
        return [
            {"id": i, "name": name, "supercategory": "herbarium_sheet"}
            for i, name in enumerate(SHEET_COMPONENT_CATEGORIES)
        ]

    @staticmethod
    def _category_name_to_id() -> dict[str, int]:
        return {name: i for i, name in enumerate(SHEET_COMPONENT_CATEGORIES)}

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_from_file(
        self,
        image_path: str,
        record: dict
    ) -> dict:
        """Run Sheet-Component detection on a local image file.

        Returns a complete COCO JSON dict (one image, N annotations).
        Each annotation includes a non-standard "score" field with the
        model's confidence for that detection, also bbox_normalized is non-standard but usefull value.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        model = self._get_model()
        results = model.predict(
            source=[str(path)],
            show=False,
            save=False,
            imgsz=self.imgsz,
            verbose=False,
            device=self.device,
        )
        predictions = next(iter(results))

        name_to_id = self._category_name_to_id()
        annotations: list[dict] = []
        annotation_id = 0
        master_width = record["width"]
        master_height = record["height"]

        for boxes in predictions.boxes:
            conf = float(boxes.conf.cpu().item())
            if conf < self.confidence_threshold:
                continue

            category_index = int(boxes.cls.cpu().item())
            category_name = model.names.get(category_index, f"unknown_{category_index}")
            category_id = name_to_id.get(category_name)
            if category_id is None:
                continue

            x0, y0, x1, y1 = boxes.xyxyn.cpu().numpy()[0]
            x = int(round(x0 * master_width))
            y = int(round(y0 * master_height))
            w = int(round((x1 - x0) * master_width))
            h = int(round((y1 - y0) * master_height))

            annotations.append({
                "id": annotation_id,
                "image_id": 0,
                "category_id": category_id,
                "bbox": [x, y, w, h],
                "bbox_normalized": [float(x0), float(y0), float(x1), float(y1)],
                "area": w * h,
                "iscrowd": 0,
                "score": round(conf, 4),
            })
            annotation_id += 1

        return {
            "categories": self._build_categories(),
            "images": [
                {
                    "id": 0,
                    "height": master_height,
                    "width": master_width,
                }
            ],
            "annotations": annotations,
        }

