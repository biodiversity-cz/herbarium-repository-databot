from src.bots.base.abstract import AbstractDatabot
from src.core.domain.DatabotRole import DatabotRole
from brisque import BRISQUE
import cv2
from src.utils.types import Score
import numpy as np


class NoReferenceImageMetricsDatabot(AbstractDatabot):
    NAME = "jacq-metadata"
    DESCRIPTION = """
    Harvest specimen metadata from JACQ.ORG to keep these data available and actual for public search via repository or NMA
    """

    VERSION = 1
    ROLE = DatabotRole.SCANNER

    def compute(self, image_local_path: str) -> Score:
        image = cv2.imread(image_local_path, cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Image file not found or cannot be read: {image_local_path}")

        brisque = BRISQUE()
        brisque_score = brisque.score(image)

        # Convert to grayscale for the rest of metrics
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Sharpness (Laplacian variance)
        _laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = _laplacian.var()

        # Contrast (standard deviation)
        contrast = gray.std()

        # Clarity = sharpness * contrast
        clarity = sharpness * contrast

        # Resolution (Sobel)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
        sobel = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        resolution = np.mean(sobel)

        # # Výstup
        # print(f"BRISQUE score:           {brisque_score:.4f}")
        # print(f"Ostrost (Laplacian):     {sharpness:.4f}")
        # print(f"Kontrast:                {contrast:.4f}")
        # print(f"Jasnost (sharp × contr): {clarity:.4f}")
        # print(f"Rozlišení (Sobel):       {resolution:.4f}")

        # JSON serializovatelný výstup
        values = [
            {"name": "sharpness", "value": round(sharpness, 4)},
            {"name": "contrast", "value": round(contrast, 4)},
            {"name": "clarity", "value": round(clarity, 4)},
            {"name": "resolution", "value": round(resolution, 4)},
            {"name": "brisque_score", "value": round(brisque_score, 4)},
        ]
        return values




