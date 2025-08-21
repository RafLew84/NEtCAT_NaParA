# napara/gui/results_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTabWidget, QWidget
from PyQt6.QtCore import Qt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
try:
    from scipy.stats import gaussian_kde
except Exception:
    gaussian_kde = None

class _Mpl(FigureCanvas):
    def __init__(self):
        self.fig = Figure(constrained_layout=True)
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
    def clear(self):
        self.ax.clear()

class ResultsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Results")
        self._images = []
        self._detections = {}
        self._names = []
        self._scales = []  # (sx, sy) nm/px per image

        tabs = QTabWidget(self)
        # --- Per-image tab ---
        per = QWidget(self); per_v = QVBoxLayout(per)
        head = QHBoxLayout()
        head.addWidget(QLabel("Image:", per))
        self.cmb_img = QComboBox(per)
        head.addWidget(self.cmb_img, 1)
        self.btn_refresh = QPushButton("Refresh", per)
        head.addWidget(self.btn_refresh)
        per_v.addLayout(head)

        row = QHBoxLayout()
        self.plot_area = _Mpl(); self.plot_nn = _Mpl()
        row.addWidget(self.plot_area, 1); row.addWidget(self.plot_nn, 1)
        per_v.addLayout(row, 1)
        tabs.addTab(per, "Per image")

        # --- Summary tab ---
        summ = QWidget(self); summ_v = QVBoxLayout(summ)
        self.plot_mean_area = _Mpl()
        self.plot_mean_nn = _Mpl()
        summ_v.addWidget(self.plot_mean_area, 1)
        summ_v.addWidget(self.plot_mean_nn, 1)
        tabs.addTab(summ, "Summary")

        # layout
        root = QVBoxLayout(self)
        root.addWidget(tabs, 1)
        self.setLayout(root)
        self.resize(900, 700)

        # signals
        self.cmb_img.currentIndexChanged.connect(self._update_per_image)
        self.btn_refresh.clicked.connect(self.refresh_all)

    # API
    def set_data(self, images, detections: dict[int, list]):
        self._images = images
        self._detections = detections or {}
        self._names = [str(getattr(im, "file_name", f"img_{i}")).split("\\")[-1].split("/")[-1]
                       for i, im in enumerate(images)]
        self._scales = [tuple(getattr(im, "get_pixel_size_nm")()) for im in images]
        self.cmb_img.blockSignals(True)
        self.cmb_img.clear()
        self.cmb_img.addItems(self._names)
        self.cmb_img.blockSignals(False)
        if self._names:
            self.cmb_img.setCurrentIndex(0)

    def refresh_all(self):
        self._update_per_image()
        self._update_summary()

    # internals
    def _areas_nm2(self, idx):
        dets = self._detections.get(idx, [])
        sx, sy = self._scales[idx] if idx < len(self._scales) else (1.0, 1.0)
        return np.array([d.area_px2 * (sx or 1.0) * (sy or 1.0) for d in dets], dtype=float)

    def _nnd_nm(self, idx):
        dets = self._detections.get(idx, [])
        vals = [d.nn_dist_nm for d in dets if getattr(d, "nn_dist_nm", None) is not None]
        return np.array(vals, dtype=float)

    def _plot_kde_or_hist(self, ax, data, xlabel, title):
        ax.clear()
        if data.size == 0 or not np.isfinite(data).any():
            ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel("Density")
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return
        x = data[np.isfinite(data)]
        if x.size >= 2 and gaussian_kde is not None:
            kde = gaussian_kde(x)
            xs = np.linspace(x.min(), x.max(), 256)
            ax.plot(xs, kde(xs))
        ax.hist(x, bins="auto", density=True, alpha=0.3)
        ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel("Density")

    def _update_per_image(self):
        i = self.cmb_img.currentIndex()
        if i < 0 or i >= len(self._images):
            return
        a = self._areas_nm2(i)
        d = self._nnd_nm(i)
        self._plot_kde_or_hist(self.plot_area.ax, a, "Area [nm²]", f"Area distribution — {self._names[i]}")
        self._plot_kde_or_hist(self.plot_nn.ax, d, "NN distance [nm]", f"Nearest-neighbour — {self._names[i]}")
        self.plot_area.draw(); self.plot_nn.draw()

    def _update_summary(self):
        n = len(self._images)
        mean_area = np.zeros(n, float); mean_nn = np.zeros(n, float)
        for i in range(n):
            a = self._areas_nm2(i); mean_area[i] = np.nan if a.size==0 else float(np.mean(a))
            d = self._nnd_nm(i);   mean_nn[i]   = np.nan if d.size==0 else float(np.mean(d))
        x = np.arange(n)

        self.plot_mean_area.ax.clear()
        self.plot_mean_area.ax.plot(x, mean_area, marker="o")
        self.plot_mean_area.ax.set_title("Mean area per image")
        self.plot_mean_area.ax.set_xlabel("Image index"); self.plot_mean_area.ax.set_ylabel("Mean area [nm²]")
        self.plot_mean_area.ax.set_xticks(x); self.plot_mean_area.ax.set_xticklabels(self._names, rotation=45, ha="right")

        self.plot_mean_nn.ax.clear()
        self.plot_mean_nn.ax.plot(x, mean_nn, marker="o")
        self.plot_mean_nn.ax.set_title("Mean NN distance per image")
        self.plot_mean_nn.ax.set_xlabel("Image index"); self.plot_mean_nn.ax.set_ylabel("Mean NN [nm]")
        self.plot_mean_nn.ax.set_xticks(x); self.plot_mean_nn.ax.set_xticklabels(self._names, rotation=45, ha="right")

        self.plot_mean_area.draw(); self.plot_mean_nn.draw()
