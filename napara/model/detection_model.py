from dataclasses import dataclass, field
import numpy as np

@dataclass
class Detection:
    id: int
    contour_px: np.ndarray              # (N,2) w pikselach GLOBALNYCH
    centroid_px: tuple[float, float]
    area_px2: float
    path_item: object = None            # QGraphicsPathItem (ustawisz w kroku 3)
    label_item: object = None           # QGraphicsSimpleTextItem (krok 3)