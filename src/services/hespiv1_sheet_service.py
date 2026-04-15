import os
import gzip
import shutil
import tempfile
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image
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

# The trained model internally uses "institutional label";
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

    # Class-level cache for verified weights path to avoid repeated file system checks
    _weights_verified_path: str | None = None

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

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def _ensure_weights(self) -> str:
        # Return cached verified path if already checked
        if HespiV1SheetService._weights_verified_path is not None:
            return HespiV1SheetService._weights_verified_path

        path = Path(self.weights_path)
        if path.exists() and path.stat().st_size > 0:
            HespiV1SheetService._weights_verified_path = str(path)
            return str(path)

        print(f"Model weights not found at {path}, downloading from {self.weights_url} ...")
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.weights_url.endswith(".gz"):
            gz_path = Path(str(path) + ".gz")
            urllib.request.urlretrieve(self.weights_url, gz_path)
            with gzip.open(gz_path, "rb") as f_in, open(path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            gz_path.unlink()
        else:
            urllib.request.urlretrieve(self.weights_url, path)

        if not path.exists() or path.stat().st_size == 0:
            raise IOError(f"Failed to download model weights to {path}")

        print(f"Model weights saved to {path}")
        HespiV1SheetService._weights_verified_path = str(path)
        return str(path)

    def _get_model(self) -> YOLO:
        if self._model is None:
            weights = self._ensure_weights()
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
        image_id: int = 0,
        source_url: str = "",
    ) -> dict:
        """Run Sheet-Component detection on a local image file.

        Returns a complete COCO JSON dict (one image, N annotations).
        Each annotation includes a non-standard ``score`` field with the
        model's confidence for that detection.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        im = Image.open(path)
        width, height = im.size

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

        for boxes in predictions.boxes:
            conf = float(boxes.conf.cpu().item())
            if conf < self.confidence_threshold:
                continue

            category_index = int(boxes.cls.cpu().item())
            category_name = model.names.get(category_index, f"unknown_{category_index}")
            category_id = name_to_id.get(category_name)
            if category_id is None:
                continue

            x0, y0, x1, y1 = boxes.xyxy.cpu().numpy()[0]
            x = int(round(float(x0)))
            y = int(round(float(y0)))
            w = int(round(float(x1 - x0)))
            h = int(round(float(y1 - y0)))

            annotations.append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_id,
                "bbox": [x, y, w, h],
                "area": w * h,
                "segmentation": [],
                "iscrowd": 0,
                "score": round(conf, 4),
            })
            annotation_id += 1

        now = datetime.now(timezone.utc).isoformat()

        return {
            # "info": {
            #     "year": str(datetime.now().year),
            #     "version": "1",
            #     "description": "Herbarium sheet component bounding box detection (Sheet-Component model of HESPI v1)",
            #     "contributor": "biodiversity.cz",
            #     "url": source_url,
            #     "date_created": now,
            # },
            # "licenses": [
            #     {
            #         "id": 1,
            #         "url": "https://creativecommons.org/publicdomain/zero/1.0/",
            #         "name": "Public Domain",
            #     }
            # ],
            "categories": self._build_categories(),
            "images": [
                {
                    "id": image_id,
                    # "license": 1,
                    # "file_name": path.name,
                    "height": height,
                    "width": width,
                    # "date_captured": now,
                }
            ],
            "annotations": annotations,
        }

    def detect_from_url(self, url: str, image_id: int = 0) -> dict:
        """Download an image from *url* and run detection.

        The temporary file is removed after processing.
        """
        suffix = Path(url.split("?")[0].split("/")[-1]).suffix or ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        try:
            urllib.request.urlretrieve(url, tmp_path)
            return self.detect_from_file(tmp_path, image_id=image_id, source_url=url)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
