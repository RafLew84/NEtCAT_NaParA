# napara/gui/widgets/viewer_widget.py
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel
from PyQt6.QtCore import QRectF, Qt, pyqtSignal 
from PyQt6.QtGui import QTransform
import numpy as np

class ViewerWidget(QWidget):
    """
    Image viewer using ViewBox + ImageItem + HistogramLUTWidget.
    - Maps pixel grid to physical nm using per-axis scale via QTransform.
    - Preserves zoom/pan between images.
    - Exposes gamma control via LUT.
    """

    lutChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_view_range = None
        self._nm_scale = (None, None)
        self._gamma = 1.0
        self._build()

    def _build(self):
        root = QVBoxLayout(self)

        # Create a PlotItem with axes instead of bare ViewBox
        self.plot_item = pg.PlotItem()
        self.plot_item.setAspectLocked(True)
        self.plot_item.invertY(True)
        self.plot_item.getAxis("bottom").setLabel("x", units="nm")
        self.plot_item.getAxis("left").setLabel("y", units="nm")

        # ImageItem inside PlotItem
        self.image_item = pg.ImageItem()
        self.plot_item.addItem(self.image_item)

        # GraphicsLayoutWidget to host the PlotItem
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.addItem(self.plot_item)

        # Histogram + LUT (levels)
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(self.image_item)

        # Gamma slider
        gamma_row = QHBoxLayout()
        gamma_row.addWidget(QLabel("γ"))
        self.slider_gamma = QSlider(Qt.Orientation.Horizontal)
        self.slider_gamma.setRange(10, 400)
        self.slider_gamma.setValue(100)
        self.slider_gamma.valueChanged.connect(self._on_gamma_changed)
        gamma_row.addWidget(self.slider_gamma)

        # Layout: plot with axes on left, histogram on right
        hl = QHBoxLayout()
        hl.addWidget(self.glw, 1)
        hl.addWidget(self.hist, 0)

        root.addLayout(hl, 1)
        root.addLayout(gamma_row)


    def _on_gamma_changed(self, v: int):
        """Update LUT gamma when slider moves."""
        self.set_gamma(v / 100.0)
        self.lutChanged.emit()

    def set_gamma(self, gamma: float):
        """Apply gamma to the image LUT (does not alter the data)."""
        self._gamma = max(0.01, float(gamma))
        # build LUT 256 entries with gamma curve
        x = np.linspace(0.0, 1.0, 256)
        lut = np.clip(x ** (1.0 / self._gamma), 0, 1)
        lut = (lut * 255).astype(np.ubyte)
        lut = np.stack([lut, lut, lut], axis=1)  # grayscale RGB
        self.image_item.setLookupTable(lut)

    def clear(self):
        """Clear image content and view state."""
        self.image_item.clear()
        self._last_view_range = None

    def _image_rect_nm(self, w_px: int, h_px: int) -> QRectF:
        sx, sy = self._nm_scale
        if sx and sy:
            return QRectF(0.0, 0.0, w_px * sx, h_px * sy)
        return QRectF(0.0, 0.0, float(w_px), float(h_px))

    def _apply_scale_transform(self):
        """Apply nm-per-pixel scaling to the ImageItem via QTransform."""
        self.image_item.resetTransform()
        sx, sy = self._nm_scale
        if sx and sy:
            tr = QTransform()
            tr.scale(sx, sy)
            self.image_item.setTransform(tr)

    def fit_to_view(self, img_shape_px: tuple[int, int]):
        """Fit the whole image rect into the ViewBox (no padding)."""
        h, w = img_shape_px
        rect = self._image_rect_nm(w, h)
        self.plot_item.getViewBox().setRange(rect, padding=0.0)

    def get_plot_item(self):
        """Return underlying PlotItem to attach ROI items."""
        return self.plot_item

    def set_image(
        self,
        img,
        *,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
        preserve_zoom: bool = True,
        auto_levels: bool = True,
    ):
        """
        Set a new image and map pixel grid to physical nm using QTransform.
        - On the first image (or when preserve_zoom=False) it performs an auto-fit
        equivalent to pressing 'A' (using transformed bounds), so axes show 'nm'
        instead of tiny prefixes like 'mnm'.
        - When preserve_zoom=True and a previous view exists, it restores the last view.
        """
        # Save current view before content changes
        vb = self.plot_item.getViewBox()
        if preserve_zoom and hasattr(self, "_ever_shown") and getattr(self, "_ever_shown"):
            self._last_view_range = vb.viewRange()
        else:
            self._last_view_range = None

        # Store scale and set image (avoid ViewBox autorange)
        self._nm_scale = scale_nm_per_px
        self.image_item.setImage(img, autoLevels=auto_levels, autoDownsample=True)

        # Apply px->nm transform
        self._apply_scale_transform()

        # Decide whether to restore previous view or fit
        restore = preserve_zoom and (self._last_view_range is not None)

        if restore:
            # Restore previous view range
            x_rng, y_rng = self._last_view_range
            vb.setRange(xRange=x_rng, yRange=y_rng, padding=0.0)
        else:
            # Robust auto-fit in physical coords (like pressing 'A')
            bounds = self.image_item.mapRectToParent(self.image_item.boundingRect())
            if bounds.isEmpty():
                # Fallback: build bounds from shape and scale
                h, w = img.shape[:2]
                sx, sy = self._nm_scale
                w_nm = w * (sx or 1.0)
                h_nm = h * (sy or 1.0)
                bounds = QRectF(0.0, 0.0, float(w_nm), float(h_nm))
            vb.setRange(bounds, padding=0.0)

        # Re-apply gamma LUT in case pyqtgraph reset it
        self.set_gamma(self._gamma)

        # Mark that at least one image was shown
        self._ever_shown = True
