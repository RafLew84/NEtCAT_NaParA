from __future__ import annotations
from PyQt6.QtCore import QObject, pyqtSignal, QRectF, QPointF
import pyqtgraph as pg
from dataclasses import dataclass
from typing import Dict, Optional, List

@dataclass
class ROIRecord:
    """Holds the single ROI item and its kind for an image index."""
    kind: str            # "rect" | "poly"
    item: pg.ROI         # RectROI or PolyLineROI

class ROIManager(QObject):
    """
    Manages a single ROI per image (rect or polygon). If a new ROI is created
    for the same image, the previous one is replaced. Coordinates are in plot units (nm).
    """
    roiAdded = pyqtSignal(int)       # image_index
    roiChanged = pyqtSignal(int)     # image_index
    roiRemoved = pyqtSignal(int)     # image_index
    roiSelected = pyqtSignal(int)    # image_index

    def __init__(self, plot_item: pg.PlotItem, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plot_item = plot_item
        self._active_image: Optional[int] = None
        self._records: Dict[int, ROIRecord] = {}

    # ----- context -----
    def set_active_image(self, image_index: Optional[int]) -> None:
        """Show only the ROI for the given image index."""
        # Hide all
        for rec in self._records.values():
            rec.item.setVisible(False)
        self._active_image = image_index
        # Show current
        if image_index is not None and image_index in self._records:
            self._records[image_index].item.setVisible(True)

    # ----- create/replace -----
    def set_rect_roi(self, image_index: int, rect: QRectF) -> None:
        """Create or replace a rectangular ROI for given image index."""
        # Remove existing
        self.remove_roi(image_index)
        roi = pg.RectROI([rect.left(), rect.top()], [rect.width(), rect.height()],
                         movable=True, rotatable=False, resizable=True, pen=pg.mkPen('y', width=2))
        roi.addScaleHandle([1, 1], [0, 0]); roi.addScaleHandle([0, 0], [1, 1])
        self._attach(image_index, ROIRecord(kind="rect", item=roi))

    def set_poly_roi(self, image_index: int, points: List[QPointF]) -> None:
        """Create or replace a polygon ROI for given image index."""
        # Remove existing
        self.remove_roi(image_index)
        pts = [(p.x(), p.y()) for p in points]
        roi = pg.PolyLineROI(pts, closed=True, pen=pg.mkPen('c', width=2), movable=True)
        self._attach(image_index, ROIRecord(kind="poly", item=roi))

    def _attach(self, image_index: int, rec: ROIRecord) -> None:
        """Add ROI to scene and connect signals."""
        self._records[image_index] = rec
        self._plot_item.addItem(rec.item)
        rec.item.setVisible(self._active_image == image_index)
        rec.item.sigRegionChanged.connect(lambda _=None, i=image_index: self._on_changed(i))
        rec.item.sigClicked.connect(lambda _=None, i=image_index: self._on_selected(i))
        self.roiAdded.emit(image_index)

    # ----- remove -----
    def remove_roi(self, image_index: int) -> None:
        """Remove ROI for given image index if present."""
        rec = self._records.pop(image_index, None)
        if rec:
            self._plot_item.removeItem(rec.item)
            self.roiRemoved.emit(image_index)

    # ----- query -----
    def has_roi(self, image_index: int) -> bool:
        return image_index in self._records

    def get_kind(self, image_index: int) -> Optional[str]:
        return self._records.get(image_index).kind if image_index in self._records else None

    def get_rect(self, image_index: int) -> Optional[QRectF]:
        """Return QRectF for rect ROI; None if not rect or missing."""
        rec = self._records.get(image_index)
        if not rec or rec.kind != "rect":
            return None
        pos = rec.item.pos()
        size = rec.item.size()
        return QRectF(pos.x(), pos.y(), size.x(), size.y())

    def get_polygon(self, image_index: int) -> Optional[List[QPointF]]:
        """Return polygon points for poly ROI; None if not poly or missing."""
        rec = self._records.get(image_index)
        if not rec or rec.kind != "poly":
            return None
        st = rec.item.getState()
        pts = [QPointF(*p) for p in st.get("points", [])]
        return pts if pts else None

    # ----- helpers -----
    def add_centered_rect(self, image_index: int, size_nm: float = 20.0) -> None:
        """Create centered square ROI of given size (nm) in current view."""
        vb = self._plot_item.getViewBox()
        (x0, x1), (y0, y1) = vb.viewRange()
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        rect = QRectF(cx - size_nm/2, cy - size_nm/2, size_nm, size_nm)
        self.set_rect_roi(image_index, rect)

    # ----- signals -----
    def _on_changed(self, image_index: int) -> None:
        self.roiChanged.emit(image_index)

    def _on_selected(self, image_index: int) -> None:
        self.roiSelected.emit(image_index)
