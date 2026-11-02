"""Pixel-edge paths preserve every hole and separate neighbouring domain IDs."""

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage as ndi
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath


def domain_shapes(labels: NDArray[np.int32]) -> dict[int, tuple[QPainterPath, QPointF]]:
    shapes = {}
    for identity, bounds in enumerate(ndi.find_objects(labels), 1):
        if bounds is None:
            continue
        rows, columns = bounds
        mask = labels[bounds] == identity
        path = QPainterPath()
        # Merge straight runs of edges instead of adding one path segment per pixel.
        horizontal = np.diff(np.pad(mask.astype(np.int8), ((1, 1), (0, 0))), axis=0) != 0
        vertical = (np.diff(np.pad(mask.astype(np.int8), ((0, 0), (1, 1))), axis=1) != 0).T
        for edges, transpose in ((horizontal, False), (vertical, True)):
            transitions = np.diff(np.pad(edges.astype(np.int8), ((0, 0), (1, 1))), axis=1)
            line, start = np.nonzero(transitions == 1)
            _, stop = np.nonzero(transitions == -1)
            for fixed, first, last in zip(line, start, stop):
                x1, y1, x2, y2 = ((fixed, first, fixed, last) if transpose
                                  else (first, fixed, last, fixed))
                path.moveTo(float(x1 + columns.start), float(y1 + rows.start))
                path.lineTo(float(x2 + columns.start), float(y2 + rows.start))
        yy, xx = np.nonzero(mask)
        nearest = int(np.argmin((xx - xx.mean()) ** 2 + (yy - yy.mean()) ** 2))
        anchor = QPointF(float(xx[nearest] + columns.start) + .5,
                         float(yy[nearest] + rows.start) + .5)
        shapes[identity] = path, anchor
    return shapes
