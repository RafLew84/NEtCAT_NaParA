from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
import pyqtgraph as pg
import numpy as np

class ROIPreviewWidget(QWidget):
    """Small preview of the current ROI (axes in nm)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._nm_scale = (None, None)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.title = QLabel("ROI Preview")
        lay.addWidget(self.title)

        # Plot with axes
        self.plot_item = pg.PlotItem()
        self.plot_item.setAspectLocked(True)
        self.plot_item.setLabel('bottom', 'x', units='nm')
        self.plot_item.setLabel('left', 'y', units='nm')
        self.plot_item.getViewBox().invertY(True)  
        self.view = pg.GraphicsLayoutWidget()
        self.view.addItem(self.plot_item)
        lay.addWidget(self.view, 1)

        # Image
        self.image_item = pg.ImageItem()
        self.plot_item.addItem(self.image_item)

        # Sensowne domyślne rozmiary górnego pasa (użytkownik zmieni splitterem)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def set_preview(
            self, 
            roi_img: np.ndarray, 
            scale_nm_per_px: tuple[float | None, float | None],
            levels: tuple[float, float] | None = None,
            lut: np.ndarray | None = None,
    ):
        """Show ROI image; axes are in nm."""
        if roi_img is None or roi_img.size == 0:
            self.clear()
            return
        self._nm_scale = scale_nm_per_px

        # pokaż obraz i przeskaluj do nm
        self.image_item.setImage(
            roi_img, 
            autoLevels=False, 
            levels=levels,
            autoDownsample=True, 
        )

        if lut is not None:
            self.image_item.setLookupTable(lut, update=True)

        self._apply_scale_transform()

        br = self.image_item.mapRectToParent(self.image_item.boundingRect())
        self.plot_item.getViewBox().setRange(br, padding=0.0)

    def clear(self):
        self.image_item.clear()
        self.image_item.setLookupTable(None)

    def _apply_scale_transform(self):
        sx, sy = self._nm_scale
        sx = sx if (sx and sx > 0) else 1.0
        sy = sy if (sy and sy > 0) else 1.0
        tr = pg.QtGui.QTransform()
        tr.scale(sx, sy)
        self.image_item.setTransform(tr)