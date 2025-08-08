import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class ViewerWidget(QWidget):
    """Placeholder viewer oparty na pyqtgraph ImageView."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        # ImageView daje toolbar z play/levels; można podmienić na GraphicsLayoutWidget + ImageItem
        self.image_view = pg.ImageView(view=pg.PlotItem())
        # sensowniejsze etykiety osi (nm ustawimy, gdy będziemy znać skalę)
        self.image_view.getView().setLabel("bottom", "x (px)")
        self.image_view.getView().setLabel("left", "y (px)")
        layout.addWidget(self.image_view)

    def set_image(self, img):
        """img: numpy.ndarray 2D lub 3D (t, y, x). Na razie zakładamy 2D."""
        self.image_view.setImage(img, autoLevels=True, autoHistogramRange=True)

    def clear(self):
        self.image_view.clear()

    def set_axis_labels_nm(self, scale_nm_per_px: float | None):
        if scale_nm_per_px:
            self.image_view.getView().setLabel("bottom", f"x (nm)")
            self.image_view.getView().setLabel("left", f"y (nm)")
            item = self.image_view.getImageItem()
            if item is not None:
                tr = pg.QtGui.QTransform()
                tr.scale(scale_nm_per_px, scale_nm_per_px)
                item.setTransform(tr)
        else:
            self.image_view.getView().setLabel("bottom", "x (px)")
            self.image_view.getView().setLabel("left", "y (px)")
