from bots.abstract import AbstractDatabot
from core.DatabotRole import DatabotRole
from brisque import BRISQUE
import cv2
import numpy as np


class NoReferenceImageMetricsDatabot(AbstractDatabot):
    NAME = "no-ref-image-metrics"
    DESCRIPTION = "Calculates BRISQUE image quality score (1 = best, 100 = worst) [<a href=\"https://quality.nfdi4ing.de/en/latest/image_quality/BRISQUE.html\">link</a>]"
    VERSION = 1
    ROLE = DatabotRole.SCANNER

    def run(self):
        try:
            img_path = "src/data/image.png"
            image = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if image is None:
                raise FileNotFoundError(f"Image file not found or cannot be read: {img_path}")

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

            # Výstup
            print(f"BRISQUE score:           {brisque_score:.4f}")
            print(f"Ostrost (Laplacian):     {sharpness:.4f}")
            print(f"Kontrast:                {contrast:.4f}")
            print(f"Jasnost (sharp × contr): {clarity:.4f}")
            print(f"Rozlišení (Sobel):       {resolution:.4f}")

            # JSON serializovatelný výstup
            values = [
                {"name": "brisque_score", "value": round(brisque_score, 4)},
                {"name": "sharpness", "value": round(sharpness, 4)},
                {"name": "contrast", "value": round(contrast, 4)},
                {"name": "clarity", "value": round(clarity, 4)},
                {"name": "resolution", "value": round(resolution, 4)},
            ]
            result_json = json.dumps({"values": values})

            # Uložení do databáze
            self.save_result(result_json)

        except FileNotFoundError:
            print(f"❌ Image file not found: {img_path}")
        except Exception as e:
            print(f"❌ Error computing BRISQUE score: {e}")

"""
===================================================================================================
📊 Metriky kvality obrazu – přehled
===================================================================================================

| Proměnná      | Název (CZ)                  | Rozsah hodnot      | Co je lepší?       | Význam                                                                 |
|---------------|-----------------------------|---------------------|---------------------|------------------------------------------------------------------------|
| sharpness     | Ostrost (Laplacian)         | ~0 až tisíce+       | Vyšší je lepší      | Měří množství detailů pomocí rozptylu Laplaceova filtru.              |
| contrast      | Kontrast                    | 0 až 255            | Vyšší je lepší      | Standardní odchylka jasových hodnot – rozdíl mezi světlým/tmavým.     |
| clarity       | Jasnost (ostrost × kontrast)| 0 až ∞              | Vyšší je lepší      | Kombinovaná metrika – subjektivní dojem čistoty a výraznosti.         |
| resolution    | Rozlišení (Sobel)           | ~0 až stovky        | Vyšší je lepší      | Průměrná síla hran detekovaných Sobelovým operátorem.                 |
| brisque_score | Skóre kvality (BRISQUE)     | 0 až 100            | Nižší je lepší      | No-reference metrika – čím nižší skóre, tím lepší vizuální kvalita.   |

Poznámky:
- "Vyšší je lepší" znamená více detailu / větší kontrast / ostrost.
- BRISQUE je výjimka – skóre 0 je perfektní kvalita, 100 velmi špatná.
- Skutečné rozsahy mohou záviset na obsahu a rozlišení obrázku.
"""



