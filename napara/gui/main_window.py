from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QDialog, QMainWindow,
    QCheckBox, QTableWidget, QTableWidgetItem, QPushButton, QFileDialog, QMessageBox,
    QListWidgetItem
)

from .panels.image_list_panel import ImageListPanel
from .panels.processing_panel import ProcessingPanel
from .widgets.metadata_widget import MetadataWidget
from .widgets.viewer_widget import ViewerWidget
from napara.logic.roi_manager import ROIManager
from napara.processing.pipeline_spec import PipelineSpec
from .dialogs.preprocessing_dialog import PreprocessingDialog
from ..core.data_models import Detection

import os, io, json, zipfile, time
from datetime import datetime
import numpy as np
from scipy.spatial import cKDTree
from collections import defaultdict

from napara.io.factory import load_from_paths
from napara.processing.pipeline import run_pipeline

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Holds loaded STMImage objects flattened (STP/S94 -> 1 each; MPP -> many frames)
        self._images = []  # list[STMImage]
        self._contours_by_image = {}  # dict[int, list[np.ndarray]]  # per-image detected contours
        self._overlay_items = {}      # dict[int, list[pg.PlotDataItem]]  # drawn items per image
        self._spec = PipelineSpec()   # default pipeline
        self._active_index = None  # int | None
        self.detections = defaultdict(list)
        self._detections: dict[int, list[Detection]] = {}   # image_idx -> [Detection]
        self._next_id_counter: dict[int, int] = {}          # image_idx -> next ID
        self._project_dir: str | None = None
        self._last_quick_dir: str | None = None
        self._quick_slot = 0
        self._setup_ui()
        self._connect_signals()

        self._sc_detect_return = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self._sc_detect_enter  = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        for sc in (self._sc_detect_return, self._sc_detect_enter):
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(self.on_detect_roi)

        self.roi_manager = ROIManager(self.viewer.get_plot_item(), self)
        self.roi_manager.roiAdded.connect(self.on_roi_added)
        self.roi_manager.roiChanged.connect(self.on_roi_changed)
        # self.roi_manager.roiRemoved.connect(self.on_roi_removed)
        self.roi_manager.roiSelected.connect(self.on_roi_selected)

        self._show_contours = True
        self._show_labels = False
        self._build_detections_panel()

    def _setup_ui(self):
        self.setWindowTitle("NaParA – Nanoparticle Analyzer")
        self.resize(1200, 800)
        self._create_menu()
        self._create_central()
        self._create_docks()
        self.statusBar().showMessage("Ready")

    def _create_central(self):
        from PyQt6.QtWidgets import QSplitter
        from PyQt6.QtCore import Qt

        # widgets
        self.meta_widget = MetadataWidget(self)
        from .widgets.roi_preview_widget import ROIPreviewWidget
        self.roi_preview = ROIPreviewWidget(self)
        self.viewer = ViewerWidget(self)

        self.viewer.lutChanged.connect(self._update_roi_preview)

        # top: meta | preview
        top_split = QSplitter(Qt.Orientation.Horizontal, self)
        top_split.addWidget(self.meta_widget)
        top_split.addWidget(self.roi_preview)
        top_split.setStretchFactor(0, 10)
        top_split.setStretchFactor(1, 1)

        # main: (top) / (viewer)
        main_split = QSplitter(Qt.Orientation.Vertical, self)
        main_split.addWidget(top_split)
        main_split.addWidget(self.viewer)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(10, 1)

        self.setCentralWidget(main_split)

    def _normalize_project_dir(self, path_or_dir: str) -> str:
        d = path_or_dir if os.path.isdir(path_or_dir) else os.path.dirname(path_or_dir)
        if os.path.basename(d).lower() == "saves":
            d = os.path.dirname(d)
        return d

    def _quick_root_dir(self) -> str:
        # priorytet: projekt → wspólny katalog obrazów → ostatni quick → fallback
        if self._project_dir: 
            return self._normalize_project_dir(self._project_dir)
        if getattr(self, "_images", None):
            roots = [os.path.dirname(str(im.file_name)) for im in self._images]
            try:
                return os.path.commonpath(roots)
            except Exception:
                return roots[0]
        if getattr(self, "_last_quick_dir", None):
            return self._normalize_project_dir(self._last_quick_dir)
        return self._normalize_project_dir(os.path.expanduser("~/Documents/Napara"))
    
    def _rect_to_list(self, rect: QRectF | None) -> list[float]:
        if rect is None:
            return [0.0, 0.0, 0.0, 0.0]
        return [float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height())]

    def _pack_detections(self, dets: list[Detection]) -> dict[str, np.ndarray]:
        m = len(dets)
        lens = [len(d.contour_px) for d in dets]
        offs = np.zeros(m+1, dtype=np.int64)
        offs[1:] = np.cumsum(lens, dtype=np.int64)
        coords = np.empty((offs[-1], 2), np.float32)
        ids = np.empty(m, np.int32)
        areas = np.empty(m, np.float32)
        cents = np.empty((m,2), np.float32)
        pos = 0
        for i, d in enumerate(dets):
            n = lens[i]
            coords[pos:pos+n] = d.contour_px.astype(np.float32, copy=False)
            ids[i] = d.id
            areas[i] = d.area_px2
            cents[i] = d.centroid_px
            pos += n
        return {"coords": coords, "offsets": offs, "ids": ids, "areas_px2": areas, "centroids_px": cents}

    def _unpack_detections(self, blob: dict[str, np.ndarray]) -> list[Detection]:
        coords = blob["coords"]; offs = blob["offsets"]
        ids = blob["ids"]; areas = blob["areas_px2"]; cents = blob["centroids_px"]
        out: list[Detection] = []
        for i in range(len(ids)):
            sl = slice(offs[i], offs[i+1])
            poly = coords[sl].astype(np.float32, copy=False)
            cx, cy = map(float, cents[i])
            out.append(Detection(int(ids[i]), poly, (cx, cy), float(areas[i])))
        return out
    
    def _save_project_to_path(self, path: str, *, include_preproc: bool = True):
        if not self._images:
            raise RuntimeError("No images to save.")
        # baza ścieżek względnych
        roots = [os.path.dirname(str(im.file_name)) for im in self._images]
        base = os.path.commonpath(roots) if roots else os.getcwd()
        self._project_dir = os.path.dirname(path)

        manifest = {
            "schema": "napara.project.v1",
            "created": datetime.now().isoformat(timespec="seconds"),
            "active_index": self._active_index,
            "base_dir": base,
            "images": []
        }

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # manifest tymczasowo pusty, uzupełnimy po plikach
            # zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

            for idx, im in enumerate(self._images):
                rel = os.path.relpath(str(im.file_name), base)
                r = self.roi_manager.get_rect(idx)
                info = {
                    "index": idx,
                    "name": os.path.basename(str(im.file_name)),
                    "relpath": rel,
                    "shape": [im.pixels_y, im.pixels_x],
                    "size_nm": [im.size_nm_x, im.size_nm_y],
                    "scale_nm_per_px": list(im.get_pixel_size_nm()),
                    "channel": im.image_type,
                    "has_preprocessed": bool(getattr(im, "preprocessed_data", None) is not None) and include_preproc,
                    "detections": True,
                    # "roi_rect_nm": list(self.roi_manager.get_rect(self._active_index if self._active_index==idx else idx) or [0,0,0,0]),
                    "roi_rect_nm": self._rect_to_list(r),
                }
                manifest["images"].append(info)

                # detekcje
                dets = self._detections.get(idx, [])
                pack = self._pack_detections(dets)
                buf = io.BytesIO()
                np.savez_compressed(buf, **pack)
                zf.writestr(f"images/{idx}/dets.npz", buf.getvalue())

                # preproc
                if info["has_preprocessed"]:
                    arr = im.preprocessed_data.astype(np.float32, copy=False)
                    buf = io.BytesIO()
                    np.savez_compressed(buf, arr=arr)
                    zf.writestr(f"images/{idx}/preprocessed.npz", buf.getvalue())

            # zaktualizuj manifest w archiwum
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    
    def _load_project_from_path(self, path: str):
        with zipfile.ZipFile(path, "r") as zf:
            man = json.loads(zf.read("manifest.json").decode("utf-8"))
            base = man.get("base_dir") or os.path.dirname(path)
            # wyczyść stan
            self.viewer.clear_overlay()
            self._images.clear()
            self.image_list_panel.list.clear()
            self._detections.clear()
            self._next_id_counter.clear()

            # odtwórz obrazy
            for info in man["images"]:
                abs_path = os.path.join(base, info["relpath"])
                # wczytaj z oryginału (Factory)
                try:
                    imgs = load_from_paths([abs_path])  # użyj Twojej fabryki
                    im = imgs[0]
                except Exception:
                    # jeśli nie ma pliku, pomiń lub zrób placeholder
                    continue

                # przypnij preproc z projektu
                pfile = f"images/{info['index']}/preprocessed.npz"
                if pfile in zf.namelist():
                    arr = np.load(io.BytesIO(zf.read(pfile)))["arr"]
                    im.preprocessed_data = arr.astype(np.float32, copy=False)

                # dodaj do UI
                self._images.append(im)
                name = info.get("name") or os.path.basename(str(im.file_name))
                item = QListWidgetItem(name)
                item.setToolTip(os.path.abspath(abs_path))  # pełna ścieżka w podpowiedzi
                self.image_list_panel.list.addItem(item)

                roi = info.get("roi_rect_nm")
                if isinstance(roi, (list, tuple)) and len(roi) == 4 and roi[2] > 0 and roi[3] > 0:
                    self.roi_manager.set_rect_roi(len(self._images)-1, QRectF(*roi))

                # detekcje
                dfile = f"images/{info['index']}/dets.npz"
                if dfile in zf.namelist():
                    npz = np.load(io.BytesIO(zf.read(dfile)))
                    dets = self._unpack_detections({k: npz[k] for k in npz.files})
                    self._detections[len(self._images)-1] = dets
                    # ustaw next_id
                    max_id = max([d.id for d in dets], default=0)
                    self._next_id_counter[len(self._images)-1] = max_id + 1

            # aktywuj obraz
            ai = man.get("active_index", 0)
            if 0 <= ai < len(self._images):
                self.image_list_panel.list.setCurrentRow(ai)
            else:
                self.image_list_panel.list.setCurrentRow(0)

        # odbuduj overlay i tabelę
        self._rebuild_overlays_for_active_image()
        self._refresh_detections_table()
        self._update_overlay_visibility()

    def quick_save(self):
        root = self._quick_root_dir()
        saves = os.path.join(root, "saves")
        os.makedirs(saves, exist_ok=True)
        path = os.path.join(saves, f"quick_{self._quick_slot % 3}.napara")
        self._save_project_to_path(path, include_preproc=True)
        self._quick_slot += 1
        self._last_quick_dir = root
        self.statusBar().showMessage(f"Quick-saved to: {path}", 3000)

    def quick_load(self):
        root = self._quick_root_dir()
        saves = os.path.join(root, "saves")
        if not os.path.isdir(saves):
            QMessageBox.information(self, "Quick Load", f"No quick saves in: {saves}")
            return
        candidates = []
        for i in range(3):
            p = os.path.join(saves, f"quick_{i}.napara")
            if os.path.isfile(p):
                candidates.append((os.path.getmtime(p), p))
        if not candidates:
            QMessageBox.information(self, "Quick Load", f"No quick saves in: {saves}")
            return
        _, latest = max(candidates)
        self._load_project_from_path(latest)
        self._project_dir = self._normalize_project_dir(latest)  # kluczowe
        self._last_quick_dir = root
        self.statusBar().showMessage(f"Quick-loaded: {latest}", 3000)
    
    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save project as", "", "Napara Project (*.napara)")
        if not path: return
        if not path.endswith(".napara"): path += ".napara"
        self._save_project_to_path(path, include_preproc=True)
        self._project_dir = self._normalize_project_dir(path)

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "Napara Project (*.napara)")
        if not path: return
        self._load_project_from_path(path)
        self._project_dir = self._normalize_project_dir(path)

    def _next_id(self, idx: int) -> int:
        n = self._next_id_counter.get(idx, 1)
        self._next_id_counter[idx] = n + 1
        return n

    def _poly_area_px2(self, poly_px: np.ndarray) -> float:
        """Pole wielokąta (piksele^2). poly_px: (N,2) w (x,y)."""
        if poly_px is None or len(poly_px) < 3:
            return 0.0
        x = poly_px[:, 0]
        y = poly_px[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    
    def _build_detections_panel(self):
        dock = QDockWidget("Detections", self)
        dock.setObjectName("dockDetections")
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)

        w = QWidget(dock)
        v = QVBoxLayout(w)

        # widoczność
        box_vis = QGroupBox("Visibility", w)
        vvis = QHBoxLayout(box_vis)
        self.chk_show_contours = QCheckBox("Show contours", box_vis)
        self.chk_show_contours.setChecked(self._show_contours)
        self.chk_show_labels = QCheckBox("Show labels", box_vis)
        self.chk_show_labels.setChecked(self._show_labels)
        vvis.addWidget(self.chk_show_contours)
        vvis.addWidget(self.chk_show_labels)
        v.addWidget(box_vis)
        self.btn_nn = QPushButton("Detect nearest neighbours", w)
        v.addWidget(self.btn_nn)

        # tabela
        self.det_table = QTableWidget(w)
        self.det_table.setColumnCount(4)
        self.det_table.setHorizontalHeaderLabels(["ID", "Area [nm²]",  "NN ID", "NNeighbour [nm]"])
        self.det_table.setSelectionBehavior(self.det_table.SelectionBehavior.SelectRows)
        self.det_table.setSelectionMode(self.det_table.SelectionMode.SingleSelection)
        self.det_table.verticalHeader().setVisible(False)
        self.det_table.setEditTriggers(self.det_table.EditTrigger.NoEditTriggers)
        v.addWidget(self.det_table, 1)

        # akcje
        h = QHBoxLayout()
        self.btn_det_delete = QPushButton("Delete selected", w)
        self.btn_det_clear = QPushButton("Clear all", w)
        h.addWidget(self.btn_det_delete)
        h.addWidget(self.btn_det_clear)
        v.addLayout(h)

        w.setLayout(v)
        dock.setWidget(w)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        # sygnały
        self.chk_show_contours.toggled.connect(self._on_toggle_contours)
        self.chk_show_labels.toggled.connect(self._on_toggle_labels)
        self.det_table.itemSelectionChanged.connect(self._on_select_detection)
        self.btn_det_delete.clicked.connect(self._on_delete_selected)
        self.btn_det_clear.clicked.connect(self._on_clear_all)
        self.btn_nn.clicked.connect(self._on_detect_nearest_neighbours)

        # start
        self._refresh_detections_table()

    def _refresh_detections_table(self):
        idx = getattr(self, "_active_index", None)
        rows = []
        if idx is not None and idx in self._detections:
            img = self._images[idx]; sx, sy = img.get_pixel_size_nm()
            for d in self._detections[idx]:
                area_nm2 = d.area_px2 * (sx or 1.0) * (sy or 1.0)
                rows.append((d.id, area_nm2, d.nn_id, d.nn_dist_nm))

        self.det_table.setRowCount(len(rows))
        for r, (det_id, area_nm2, nn_id, nn_nm) in enumerate(rows):
            self.det_table.setItem(r, 0, QTableWidgetItem(str(det_id)))

            it_area = QTableWidgetItem(f"{area_nm2:.2f}")
            it_area.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.det_table.setItem(r, 1, it_area)

            it_nnid = QTableWidgetItem("" if nn_id is None else str(nn_id))
            it_nnid.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.det_table.setItem(r, 2, it_nnid)

            it_nn = QTableWidgetItem("" if nn_nm is None else f"{nn_nm:.2f}")
            it_nn.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.det_table.setItem(r, 3, it_nn)

        self.det_table.resizeColumnsToContents()

    def _on_detect_nearest_neighbours(self):
        idx = self._active_index
        if idx is None or idx not in self._detections:
            return
        dets = self._detections[idx]
        if len(dets) < 2:
            # nic do liczenia
            for d in dets:
                d.nn_id = None
                d.nn_dist_nm = None
            self._refresh_detections_table()
            return

        img = self._images[idx]
        sx, sy = img.get_pixel_size_nm()  # nm/px

        # punkty w nm
        pts = np.array([[d.centroid_px[0] * (sx or 1.0),
                        d.centroid_px[1] * (sy or 1.0)] for d in dets],
                    dtype=np.float64)

        tree = cKDTree(pts)
        # k=2: pierwszy to punkt sam w sobie, drugi to NN
        dist, nn_idx = tree.query(pts, k=2)
        nn_d = dist[:, 1]
        nn_i = nn_idx[:, 1]

        for i, d in enumerate(dets):
            d.nn_id = dets[int(nn_i[i])].id
            d.nn_dist_nm = float(nn_d[i])

        self._refresh_detections_table()

    def _on_toggle_contours(self, checked: bool):
        self._show_contours = checked
        self._update_overlay_visibility()  # implementujesz w kroku 3

    def _on_toggle_labels(self, checked: bool):
        self._show_labels = checked
        self._update_overlay_visibility()  # implementujesz w kroku 3

    def _on_select_detection(self):
        self._highlight_detection_row(self.det_table.currentRow())

    def _on_delete_selected(self):
        idx = self._active_index
        if idx is None: return
        row = self.det_table.currentRow()
        dets = self._detections.get(idx, [])
        if row < 0 or row >= len(dets): return
        d = dets.pop(row)
        if d.path_item: self.viewer.remove_item(d.path_item)
        if d.label_item: self.viewer.remove_item(d.label_item)
        self._refresh_detections_table()
        self._on_detect_nearest_neighbours()
        self._update_overlay_visibility()

    def _on_clear_all(self):
        idx = self._active_index
        if idx is None: return
        for d in self._detections.get(idx, []):
            if d.path_item: self.viewer.remove_item(d.path_item)
            if d.label_item: self.viewer.remove_item(d.label_item)
        self._detections[idx] = []
        self._refresh_detections_table()
        self._update_overlay_visibility()

    def _px_to_nm(self, poly_px: np.ndarray, sx: float|None, sy: float|None) -> np.ndarray:
        return np.column_stack([poly_px[:, 0] * (sx or 1.0),
                                poly_px[:, 1] * (sy or 1.0)]).astype(np.float32)

    def _highlight_detection_row(self, row: int):
        dets = self._detections.get(self._active_index, [])
        for i, d in enumerate(dets):
            self.viewer.set_item_highlight(d.path_item, i == row)
            if d.label_item: self.viewer.set_item_highlight(d.label_item, i == row)

    def _item_alive(self, item) -> bool:
        return bool(item) and (item.scene() is not None)

    def _update_overlay_visibility(self):
        idx = self._active_index
        if idx is None:
            return
        dets = self._detections.get(idx, [])
        show_c = bool(getattr(self, "_show_contours", True))
        show_l = bool(getattr(self, "_show_labels", False)) and show_c

        img = self._images[idx]
        sx, sy = img.get_pixel_size_nm()

        for d in dets:
            # kontury: odtwórz jeśli brak lub martwy
            if show_c:
                if not self._item_alive(d.path_item):
                    poly_nm = self._px_to_nm(d.contour_px, sx, sy)
                    d.path_item = self.viewer.add_polyline_nm(poly_nm, name=f"det-{d.id}")
                self.viewer.set_item_visible(d.path_item, True)
            else:
                if self._item_alive(d.path_item):
                    self.viewer.set_item_visible(d.path_item, False)

            # etykiety: jak wcześniej, on-demand
            if show_l:
                if not self._item_alive(d.label_item):
                    cx_nm = d.centroid_px[0] * (sx or 1.0)
                    cy_nm = d.centroid_px[1] * (sy or 1.0)
                    d.label_item = self.viewer.add_text_nm(str(d.id), (cx_nm, cy_nm))
                self.viewer.set_item_visible(d.label_item, True)
            else:
                if self._item_alive(d.label_item):
                    self.viewer.set_item_visible(d.label_item, False)

    def _apply_roi_detections(self, image_idx: int, roi_rect_nm, contours_px: list[np.ndarray]):
        img = self._images[image_idx]
        sx, sy = img.get_pixel_size_nm()
        x, y, w, h = roi_rect_nm
        x1, y1 = x + w, y + h

        # usuń stare detekcje z ROI (po centroidzie w nm) + skasuj ich itemy
        kept = []
        for d in self._detections.get(image_idx, []):
            cx_nm = d.centroid_px[0] * (sx or 1.0)
            cy_nm = d.centroid_px[1] * (sy or 1.0)
            if x <= cx_nm <= x1 and y <= cy_nm <= y1:
                if d.path_item: self.viewer.remove_item(d.path_item); d.path_item = None
                if d.label_item: self.viewer.remove_item(d.label_item); d.label_item = None
            else:
                kept.append(d)
        self._detections[image_idx] = kept

        # dodaj nowe
        self._detections.setdefault(image_idx, [])
        for poly_px in contours_px or []:
            if poly_px is None or len(poly_px) < 3:
                continue
            area_px2 = self._poly_area_px2(poly_px)
            cx = float(np.mean(poly_px[:, 0])); cy = float(np.mean(poly_px[:, 1]))
            det_id = self._next_id(image_idx)

            poly_nm = self._px_to_nm(poly_px, sx, sy)
            path_item = self.viewer.add_polyline_nm(poly_nm, name=f"det-{det_id}")
            label_item = None  # tworzone on-demand w _update_overlay_visibility()

            self._detections[image_idx].append(
                Detection(det_id, poly_px.astype(np.float32), (cx, cy), area_px2, path_item, label_item)
            )

        self._refresh_detections_table()
        self._update_overlay_visibility()

    def _update_roi_preview(self):
        """
        Run a lightweight version of the pipeline on the ROI
        and show the result in the preview widget.
        """
        if self._active_index is None or not self._images:
            self.roi_preview.clear()
            return

        img = self._images[self._active_index]
        roi_rect_nm = self._get_active_roi_rect_nm()
        if not roi_rect_nm:
            self.roi_preview.clear()
            return
        
        if img.preprocessed_data is not None:
            source_data = img.preprocessed_data
            self.roi_preview.title.setText("ROI Preview (Processed)")
        else:
            source_data = img.data
            self.roi_preview.title.setText("ROI Preview (Original)")
        
        # Get physical scaling and current viewer visual settings
        px_x, px_y = img.get_pixel_size_nm()
        levels = self.viewer.image_item.getLevels()
        lut = self.viewer.image_item.lut

        try:
            result = run_pipeline(
                source_data,
                roi_rect_nm=roi_rect_nm,
                nm_per_px=(px_x, px_y),
                spec=self._spec
            )
            processed_roi_img = result["debug"]["roi_preview"]
        except Exception as e:
            print(f"Error during preview update: {e}")
            self.roi_preview.clear()
            return

        self.roi_preview.set_preview(
            processed_roi_img,
            (px_x, px_y),
            levels=levels,
            lut=lut
        )

    def _create_docks(self):
        self.image_list_panel = ImageListPanel(self)
        dock_left = QDockWidget("Images", self)
        dock_left.setWidget(self.image_list_panel)
        dock_left.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_left)

        self.proc_panel = ProcessingPanel(self)
        dock_right = QDockWidget("Processing", self)
        dock_right.setWidget(self.proc_panel)
        dock_right.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_right)

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        # Image list: add/remove and selection change
        self.image_list_panel.btn_add.clicked.connect(self.on_add_images_clicked)
        self.image_list_panel.btn_remove.clicked.connect(self.on_remove_selected_clicked)
        self.image_list_panel.list.currentRowChanged.connect(self.on_image_selected)

        self.proc_panel.cb_gauss.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_sigma.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_median.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_med.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_tophat.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_tophat.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_thresh.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_min_area.valueChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_otsu_bias.valueChanged.connect(self._on_spec_changed)
        self.proc_panel.cmb_thresh_mode.currentIndexChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_sauvola_win.valueChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_sauvola_k.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_detect.stateChanged.connect(self._on_spec_changed)

        self.proc_panel.btn_detect.clicked.connect(self.on_detect_roi)

    def _on_spec_changed(self):
        """
        Update the spec object from UI controls and refresh the ROI preview.
        This acts as a live preview handler.
        """
        if self._active_index is None:
            return

        self._spec.gaussian_blur  = self.proc_panel.cb_gauss.isChecked()
        self._spec.gaussian_sigma = float(self.proc_panel.sp_sigma.value())

        self._spec.median_filter  = self.proc_panel.cb_median.isChecked()
        self._spec.median_size    = int(self.proc_panel.sp_med.value())

        self._spec.white_top_hat  = self.proc_panel.cb_tophat.isChecked()
        self._spec.wth_radius_px  = int(self.proc_panel.sp_tophat.value())

        self._spec.threshold_enable = self.proc_panel.cb_thresh.isChecked()
        self._spec.threshold_mode   = "sauvola" if self.proc_panel.cmb_thresh_mode.currentIndex()==1 else "otsu"
        self._spec.min_area_px      = int(self.proc_panel.sp_min_area.value())
        self._spec.threshold_bias   = float(self.proc_panel.sp_otsu_bias.value())
        self._spec.sauvola_window   = int(self.proc_panel.sp_sauvola_win.value())
        self._spec.sauvola_k        = float(self.proc_panel.sp_sauvola_k.value())

        self._spec.detect_enable    = self.proc_panel.cb_detect.isChecked()

        self._update_roi_preview()

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        self.act_open_project = QAction("Open Project…", self)
        self.act_open_project.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open_project.triggered.connect(self.open_project)
        file_menu.addAction(self.act_open_project)

        self.act_quickload = QAction("Quick Load", self)
        self.act_quickload.setShortcut("Ctrl+D")
        self.act_quickload.triggered.connect(self.quick_load)
        file_menu.addAction(self.act_quickload)

        file_menu.addSeparator()

        # self.act_save = QAction("Save", self)
        # self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        # self.act_save.triggered.connect(self.on_save)
        # file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Save As…", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.save_as)
        file_menu.addAction(self.act_save_as)

        self.act_quicksave = QAction("Quick Save", self)
        self.act_quicksave.setShortcut("Ctrl+S")
        self.act_quicksave.triggered.connect(self.quick_save)
        file_menu.addAction(self.act_quicksave)

        file_menu.addSeparator()

        self.act_exit = QAction("Exit", self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)
        file_menu.addAction(self.act_exit)

        edit_menu = menubar.addMenu("&Edit")
        self.act_undo = QAction("Undo", self); self.act_undo.setShortcut(QKeySequence.StandardKey.Undo); self.act_undo.setEnabled(False)
        self.act_redo = QAction("Redo", self); self.act_redo.setShortcut(QKeySequence.StandardKey.Redo); self.act_redo.setEnabled(False)
        edit_menu.addAction(self.act_undo); edit_menu.addAction(self.act_redo)

        an_menu = menubar.addMenu("&Analyze")
        self.act_detect_roi = QAction("Detect (ROI)", self)
        self.act_detect_roi.setShortcut("D")
        self.act_detect_roi.triggered.connect(self.on_detect_roi)
        an_menu.addAction(self.act_detect_roi)
        self.act_preprocess = QAction("Full Image Preprocessing...", self)
        self.act_preprocess.triggered.connect(self.on_preprocess_image)
        an_menu.addAction(self.act_preprocess)

        view_menu = menubar.addMenu("&View")
        self.act_toggle_statusbar = QAction("Status Bar", self, checkable=True, checked=True)
        self.act_toggle_statusbar.triggered.connect(self.on_toggle_statusbar)
        view_menu.addAction(self.act_toggle_statusbar)

        self.act_reset_roi = QAction("Reset ROI", self)
        self.act_reset_roi.triggered.connect(self.on_add_rect_roi)
        view_menu.addAction(self.act_reset_roi)

        help_menu = menubar.addMenu("&Help")
        self.act_about = QAction("About NaParA", self); self.act_about.triggered.connect(self.on_about)
        help_menu.addAction(self.act_about)

    def _get_active_roi_rect_nm(self):
        """Return (x,y,w,h) in nm for current image ROI; None if missing.
        If polygon ROI exists, use its bounding rect (warn once)."""
        idx = self._active_index
        if idx is None:
            return None
        # Rect ROI
        rect = self.roi_manager.get_rect(idx)
        if rect is not None:
            return (rect.x(), rect.y(), rect.width(), rect.height())
        # Poly ROI -> fallback to bounding rect
        poly = self.roi_manager.get_polygon(idx)
        if poly:
            xs = [p.x() for p in poly]; ys = [p.y() for p in poly]
            x, y = min(xs), min(ys); w, h = max(xs)-x, max(ys)-y
            # Optional: QMessageBox.information(self, "...", "Polygon ROI treated as bounding box.")
            return (x, y, w, h)
        return None

    @staticmethod
    def _centroid(contour_xy: np.ndarray) -> tuple[float, float]:
        """Return (cx, cy) in pixel coords for Nx2 contour array."""
        if contour_xy.size == 0:
            return (0.0, 0.0)
        cx = float(np.mean(contour_xy[:, 0]))
        cy = float(np.mean(contour_xy[:, 1]))
        return (cx, cy)

    @staticmethod
    def _point_in_rect_px(pt: tuple[float, float], rect_nm: tuple[float, float, float, float], nm_per_px: tuple[float | None, float | None]) -> bool:
        """Check if pixel point is inside nm-rect (convert rect to px)."""
        sx, sy = nm_per_px
        x_nm, y_nm, w_nm, h_nm = rect_nm
        if not sx or not sy or sx <= 0 or sy <= 0:
            return False
        x0 = x_nm / sx; y0 = y_nm / sy
        x1 = (x_nm + w_nm) / sx; y1 = (y_nm + h_nm) / sy
        px, py = pt
        return (x0 <= px <= x1) and (y0 <= py <= y1)

    def _clear_overlays(self, image_index: int):
        """Remove existing contour items for given image."""
        items = self._overlay_items.get(image_index, [])
        for it in items:
            try:
                self.viewer.get_plot_item().removeItem(it)
            except Exception:
                pass
        self._overlay_items[image_index] = []

    def _draw_contours(self, image_index: int, contours: list[np.ndarray]):
        """Draw contours as polyline overlays in NM coordinates (viewer axes are in nm)."""
        from pyqtgraph import PlotDataItem, mkPen
        self._clear_overlays(image_index)

        # Get nm/px scaling for this image
        img = self._images[image_index]
        sx, sy = img.get_pixel_size_nm()  # returns (nm_x_per_px, nm_y_per_px)

        items = []
        for c in contours:
            if c.shape[0] < 2:
                continue
            # Convert pixel coords -> nm to match PlotItem axes
            x_nm = c[:, 0] * (sx or 1.0)
            y_nm = c[:, 1] * (sy or 1.0)
            item = PlotDataItem(x_nm, y_nm, pen=mkPen((0, 255, 0), width=2))
            self.viewer.get_plot_item().addItem(item)
            items.append(item)

        self._overlay_items[image_index] = items

    def on_preprocess_image(self):
        if self._active_index is None:
            QMessageBox.warning(self, "No Image", "Please select an image to preprocess.")
            return

        active_image_obj = self._images[self._active_index]

        dialog = PreprocessingDialog(active_image_obj.data, self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            processed_data = dialog.get_processed_image()
            if processed_data is not None:
                active_image_obj.preprocessed_data = processed_data
                self.statusBar().showMessage("Image preprocessed successfully.", 4000)
                self._update_roi_preview()
            else:
                self.statusBar().showMessage("Preprocessing was accepted, but no data was returned.", 4000)

    def on_detect_roi(self):
        if self._active_index is None:
            return
        if not self.proc_panel.cb_detect.isChecked():
            self._refresh_detections_table()
            self._update_overlay_visibility()
            return

        img = self._images[self._active_index]
        roi_rect_nm = self._get_active_roi_rect_nm()
        if roi_rect_nm is None:
            return

        sx, sy = img.get_pixel_size_nm()
        source = img.preprocessed_data if getattr(img, "preprocessed_data", None) is not None else img.data

        res = run_pipeline(
            source,
            roi_rect_nm=roi_rect_nm,
            nm_per_px=(sx, sy),
            spec=self._spec,
        )

        contours_px = res.get("contours", []) or []

        # Jeśli pipeline zwrócił kontury w nm, przelicz na px
        if res.get("contours_units") == "nm":
            fx = 1.0 / (sx or 1.0)
            fy = 1.0 / (sy or 1.0)
            conv = []
            for c in contours_px:
                conv.append(np.column_stack([c[:, 0] * fx, c[:, 1] * fy]).astype(np.float32))
            contours_px = conv

        # Zapisz i narysuj detekcje dla aktywnego obrazu
        self._apply_roi_detections(self._active_index, roi_rect_nm, contours_px)

    # def on_detect_roi(self):
    #     if self._active_index is None:
    #         return
    #     if not self.proc_panel.cb_detect.isChecked():
    #         self._clear_overlays(self._active_index)
    #         self.statusBar().showMessage("Detection disabled.", 2000)
    #         return

    #     img = self._images[self._active_index]
    #     roi_rect_nm = self._get_active_roi_rect_nm()
    #     if roi_rect_nm is None:
    #         QMessageBox.information(self, "ROI required", "Please create a ROI (View → Add/Reset Rect ROI) and try again.")
    #         return

    #     px_x, px_y = img.get_pixel_size_nm()

    #     res = run_pipeline(
    #         img.preprocessed_data if img.preprocessed_data is not None else img.data,
    #         roi_rect_nm=roi_rect_nm,
    #         nm_per_px=(px_x, px_y),
    #         spec=self._spec,
    #     )
    #     new_contours = res["contours"]  # w px

    #     # Overwrite policy: drop existing contours whose centroid ∈ ROI, then add new
    #     existing = self._contours_by_image.get(self._active_index, [])
    #     kept = []
    #     for c in existing:
    #         if not self._point_in_rect_px(self._centroid(c), roi_rect_nm, (px_x, px_y)):
    #             kept.append(c)
    #     merged = kept + new_contours
    #     self._contours_by_image[self._active_index] = merged

    #     # Draw overlays for current image
    #     self._draw_contours(self._active_index, merged)

    #     # Optional: status
    #     self.statusBar().showMessage(f"Detected {len(new_contours)} objects (total: {len(merged)}).", 5000)

    def on_add_images_clicked(self):
        """
        Open a file dialog to load multiple STP/S94 files or a single MPP file.
        STP/S94: multiple selection allowed; each path -> 1 STMImage.
        MPP: only one file at a time (UI allows multi, but we'll expand frames).
        """
        # Build filter: multiple extensions
        filt = "STM files (*.stp *.STP *.s94 *.S94 *.mpp *.MPP);;All files (*.*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Add STM files", "", filt)
        if not paths:
            return

        try:
            new_images = load_from_paths(paths)  # flattens frames for MPP
        except Exception as e:
            QMessageBox.critical(self, "Load error", f"Failed to load files:\n{e}")
            return

        if not new_images:
            QMessageBox.information(self, "No data", "No images were loaded from the selected files.")
            return

        # Extend internal list and refresh UI
        start_index = len(self._images)
        self._images.extend(new_images)
        self._update_image_list(new_items=new_images, start_index=start_index)

        # Select first newly added item to display it immediately
        if start_index < len(self._images):
            self.image_list_panel.list.setCurrentRow(start_index)

        self.statusBar().showMessage(f"Loaded {len(new_images)} image(s).", 4000)

    def _update_image_list(self, new_items, start_index: int):
        """
        Append loaded items to the QListWidget using short labels:
        - STP/S94: show only 'filename.ext'
        - MPP frames: show 'filename.ext  [frame N]'
        """
        lst = self.image_list_panel.list
        for img in new_items:
            base = os.path.basename(str(img.file_name))  # strip directories
            if getattr(img, "frame_index", None) is not None:
                label = f"{base}  [frame {img.frame_index}]"
            else:
                label = base
            lst.addItem(label)

    def on_remove_selected_clicked(self):
        row = self.image_list_panel.list.currentRow()
        if row < 0 or row >= len(self._images):
            return

        # posprzątaj nakładki i detekcje dla usuwanego, jeśli był aktywny
        if self._active_index == row:
            self.viewer.clear_overlay()

        del self._images[row]
        self.image_list_panel.list.takeItem(row)

        # przesuwamy indeksy w magazynie detekcji
        if hasattr(self, "_detections"):
            new_map = {}
            for k, v in self._detections.items():
                if k < row:
                    new_map[k] = v
                elif k > row:
                    new_map[k-1] = v
            self._detections = new_map

        # jeśli lista pusta
        if not self._images:
            self._active_index = None
            self.viewer.clear()
            self.meta_widget.set_metadata(filename="", shape=None, scale_nm_per_px=None, channel=None)
            self._refresh_detections_table()
            return

        # wybór nowego wiersza i odświeżenie
        new_row = max(0, min(row, len(self._images) - 1))
        self.image_list_panel.list.setCurrentRow(new_row)

    def on_image_selected(self, row: int):
        if row < 0 or row >= len(self._images):
            return
        self._active_index = row
        img = self._images[row]

        px_x, px_y = img.get_pixel_size_nm()
        self.viewer.set_image(
            img.data,
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=True,
            auto_levels=True
        )

        self.viewer.clear_overlay()
        if row in self._detections:
            for d in self._detections[row]:
                d.path_item = None
                d.label_item = None

        self._refresh_detections_table()
        self._update_overlay_visibility()  # odtworzy nakładki on-demand
        self._update_roi_preview()

        self.meta_widget.set_metadata(
            filename=str(img.file_name),
            shape=(img.pixels_y, img.pixels_x),
            size_nm=(img.size_nm_x, img.size_nm_y),
            scale_nm_per_px=px_x if px_x else None,
            channel=img.image_type
        )

        # pokaż tylko ROI dla bieżącego obrazu
        self.roi_manager.set_active_image(self._active_index)
        if not self.roi_manager.has_roi(self._active_index):
            self.roi_manager.add_centered_rect(self._active_index, size_nm=20.0)

        # odbuduj nakładki i tabelę dla bieżącego obrazu
        self._rebuild_overlays_for_active_image()
        self._refresh_detections_table()
        self._update_overlay_visibility()
        self._update_roi_preview()

    def _rebuild_overlays_for_active_image(self):
        self.viewer.clear_overlay()
        idx = self._active_index
        if idx is None: return
        img = self._images[idx]
        sx, sy = img.get_pixel_size_nm()
        for d in self._detections.get(idx, []):
            if d.path_item is None:
                poly_nm = np.column_stack([d.contour_px[:,0]*(sx or 1.0),
                                        d.contour_px[:,1]*(sy or 1.0)]).astype(np.float32)
                d.path_item = self.viewer.add_polyline_nm(poly_nm, name=f"det-{d.id}")
            # etykiety tworzymy on-demand w _update_overlay_visibility()

    def on_open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "NaParA Project (*.json *.napara)")
        if path:
            self.statusBar().showMessage(f"Opened project: {path}", 4000)

    def on_quick_load(self):
        self.statusBar().showMessage("Quick Load… (stub)", 3000)

    def on_save(self):
        self.statusBar().showMessage("Save… (stub)", 3000)

    def on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "NaParA Project (*.json)")
        if path:
            self.statusBar().showMessage(f"Saved project as: {path}", 4000)

    def on_quick_save(self):
        self.statusBar().showMessage("Quick Save… (stub)", 3000)

    def on_toggle_statusbar(self, checked: bool):
        self.statusBar().setVisible(checked)

    def on_about(self):
        QMessageBox.about(
            self,
            "About NaParA",
            "<b>NaParA – Nanoparticle Analyzer</b><br>"
            "PyQt6 application for ROI‑driven nanoparticle detection on STM images."
        )
    
    # ROI actions:
    def on_add_rect_roi(self):
        if self._active_index is None:
            return
        # Create centered 20 nm square in current view
        self.roi_manager.add_centered_rect(self._active_index, size_nm=20.0)

    # ROI signals (stubs for now)
    def on_roi_added(self, image_index: int):
        if image_index == self._active_index:
            self._update_roi_preview()

    def on_roi_changed(self, image_index: int):
        if image_index == self._active_index:
            self._update_roi_preview()

    def on_roi_removed(self, image_index: int):
        if image_index == self._active_index:
            self.roi_preview.clear()

    def on_roi_selected(self, image_index: int):
        if image_index == self._active_index:
            self._update_roi_preview()