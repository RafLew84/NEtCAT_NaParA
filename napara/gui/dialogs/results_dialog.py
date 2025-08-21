# napara/gui/results_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTabWidget, QWidget, QFileDialog, QHBoxLayout
from PyQt6.QtCore import Qt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
try:
    from scipy.stats import gaussian_kde
except Exception:
    gaussian_kde = None

import os, re

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

        self._img_ids = []          # numery z nazw plików
        self._meta = {}             # id -> (time_s, ep_mV)
        self._x_mode = "index"      # "index"|"time"|"ep"
        self._x_time = None         # array[n] lub None
        self._x_ep = None           # array[n] lub None

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
        summ_head = QHBoxLayout()
        self.btn_import_meta = QPushButton("Import metadata…", summ)
        summ_head.addWidget(self.btn_import_meta)
        summ_head.addStretch(1)
        summ_head.addWidget(QLabel("X axis:", summ))
        self.cmb_xaxis = QComboBox(summ)
        self.cmb_xaxis.addItems(["Image index", "Time [s]", "Ep vs RHE [mV]"])
        summ_head.addWidget(self.cmb_xaxis)
        summ_v.addLayout(summ_head)  # to jest PRZED plot_mean_area i plot_mean_nn
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
        self.btn_import_meta.clicked.connect(self._on_import_meta)
        self.cmb_xaxis.currentIndexChanged.connect(self._on_xaxis_changed)

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
        self._names = [os.path.basename(str(getattr(im, "file_name", f"img_{i}"))) for i, im in enumerate(images)]
        self._img_ids = [self._extract_id(nm) for nm in self._names]

    def _extract_id(self, name: str) -> int | None:
        """Wyciągnij pierwszy blok cyfr z nazwy (np. '3839a.stp' -> 3839)."""
        m = re.search(r"(\d+)", name)
        return int(m.group(1)) if m else None

    def _on_import_meta(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import metadata", "", "Text/CSV (*.txt *.csv);;All files (*)")
        if not path:
            return
        meta = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                # pomiń nagłówek, parsuj wiersze: file \t time_[s] \t Ep_vs_RHE_[mV]
                lines = [ln.strip() for ln in f if ln.strip()]
            # znajdź start danych: pomiń nagłówek jeśli jest
            start = 0
            if not lines[0][0].isdigit():
                start = 1
            for ln in lines[start:]:
                parts = re.split(r"[,\t; ]+", ln.strip())
                if len(parts) < 3:
                    continue
                # pierwszy element = identyfikator pliku (liczba)
                try:
                    fid = int(re.sub(r"\D", "", parts[0]))
                except Exception:
                    continue
                # zamień przecinek na kropkę w liczbach
                def to_float(s):
                    return float(s.replace(",", "."))
                try:
                    t = to_float(parts[1])
                    ep = to_float(parts[2])
                except Exception:
                    continue
                meta[fid] = (t, ep)
        except Exception as e:
            # prosty komunikat, bez QMessageBox żeby trzymać dialog niezależny
            print("Metadata import error:", e)
            return

        self._meta = meta
        # zbuduj osie X dla obecnych obrazów
        n = len(self._images)
        self._x_time = np.full(n, np.nan, float)
        self._x_ep   = np.full(n, np.nan, float)
        for i, fid in enumerate(self._img_ids):
            if fid is not None and fid in meta:
                self._x_time[i] = float(meta[fid][0])
                self._x_ep[i]   = float(meta[fid][1])

        self._update_summary()

    def _on_xaxis_changed(self, _idx: int):
        txt = self.cmb_xaxis.currentText()
        self._x_mode = "index" if "index" in txt.lower() else ("time" if "time" in txt.lower() else "ep")
        self._update_summary()

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

        # wybór osi X
        if self._x_mode == "time" and self._x_time is not None and np.isfinite(self._x_time).any():
            x = self._x_time.copy()
            xlabel = "Time [s]"
            xticks = None
        elif self._x_mode == "ep" and self._x_ep is not None and np.isfinite(self._x_ep).any():
            x = self._x_ep.copy()
            xlabel = "Ep vs RHE [mV]"
            xticks = None
        else:
            x = np.arange(n)
            xlabel = "Image index"
            xticks = self._names

        # rysuj
        self.plot_mean_area.ax.clear()
        self.plot_mean_area.ax.plot(x, mean_area, marker="o")
        self.plot_mean_area.ax.set_title("Mean area per image")
        self.plot_mean_area.ax.set_xlabel(xlabel); self.plot_mean_area.ax.set_ylabel("Mean area [nm²]")
        if xticks is not None:
            self.plot_mean_area.ax.set_xticks(x); self.plot_mean_area.ax.set_xticklabels(xticks, rotation=45, ha="right")

        self.plot_mean_nn.ax.clear()
        self.plot_mean_nn.ax.plot(x, mean_nn, marker="o")
        self.plot_mean_nn.ax.set_title("Mean NN distance per image")
        self.plot_mean_nn.ax.set_xlabel(xlabel); self.plot_mean_nn.ax.set_ylabel("Mean NN [nm]")
        if xticks is not None:
            self.plot_mean_nn.ax.set_xticks(x); self.plot_mean_nn.ax.set_xticklabels(xticks, rotation=45, ha="right")

        self.plot_mean_area.draw(); self.plot_mean_nn.draw()
