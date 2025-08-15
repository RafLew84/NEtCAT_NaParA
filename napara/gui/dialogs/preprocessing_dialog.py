
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QFormLayout,
    QPushButton, QCheckBox, QDoubleSpinBox, QMessageBox, QProgressDialog,
    QWidget, QRadioButton, QSpinBox, QApplication, QScrollArea, QComboBox,
    QLineEdit, QListWidget, QListWidgetItem, QToolBar, QFileDialog,
    QStyle

)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction
import pyqtgraph as pg
import numpy as np
from typing import Optional
from napara.processing.pipeline import run_heavy_preprocessing
from napara.processing.pipeline_spec import HeavyPreprocSpec
from napara.processing.pipeline import DEFAULT_ORDER

import json, datetime, os

PRESET_SCHEMA = "napara.preprocessing.v1"

class PreprocessingDialog(QDialog):
    """
    Dialog do przeprowadzania ciężkich, jednorazowych operacji na całym obrazie,
    takich jak destriping, dekonwolucja i zaawansowane odszumianie.
    """
    def __init__(self, original_image: np.ndarray, parent=None):
        super().__init__(parent)
        self.original_image = original_image
        self.processed_image = None  # Tutaj zapiszemy finalny wynik

        self._build_ui()
        self._connect_signals()
        
        self.viewer_original.setImage(self.original_image)
        self.setWindowTitle("Full Image Preprocessing")
        self.setMinimumSize(1100, 700)

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setSizeGripEnabled(True)
        self.showMaximized()
    
    def _fit_order_list_height(self):
        lst = self.lst_order
        n = lst.count()
        if n == 0:
            lst.setMaximumHeight(1)
            return
        row_h = lst.sizeHintForRow(0)
        spacing = lst.spacing()
        frame = 2 * lst.frameWidth()
        h = n * row_h + (n - 1) * spacing + frame
        lst.setMinimumHeight(h)
        lst.setMaximumHeight(h)

    def _build_ui(self):
        # --- Główne layouty ---
        root_layout = QVBoxLayout(self)

        # pasek u góry
        top_btn_layout = QHBoxLayout()
        top_btn_layout.addStretch(1)
        self.btn_process = QPushButton("Process", self)
        top_btn_layout.addWidget(self.btn_process)
        root_layout.addLayout(top_btn_layout)

        # TOOLBAR
        tb = QToolBar("Presets", self)
        tb.setIconSize(QSize(18,18))
        act_load = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Load preset…", self)
        act_save = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save preset…", self)
        act_reset = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Reset to defaults", self)
        tb.addAction(act_load); tb.addAction(act_save); tb.addSeparator(); tb.addAction(act_reset)
        root_layout.addWidget(tb)

        act_load.triggered.connect(self._on_preset_load)
        act_save.triggered.connect(self._on_preset_save)
        act_reset.triggered.connect(self._on_preset_reset)

        # --- główny splitter poziomy ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- dwa podglądy obrazów ---
        self.viewer_original = pg.ImageView(self)
        self.viewer_processed = pg.ImageView(self)
        for viewer in [self.viewer_original, self.viewer_processed]:
            viewer.ui.histogram.hide()
            viewer.ui.roiBtn.hide()
            viewer.ui.menuBtn.hide()
            viewer.getView().setAspectLocked(True)
        main_splitter.addWidget(self.viewer_original)
        main_splitter.addWidget(self.viewer_processed)

        # --- panel "Order of operations" po PRAWEJ od obrazów ---
        order_grp = QGroupBox("Order of operations", self)
        order_v = QVBoxLayout(order_grp)
        self.lst_order = QListWidget(order_grp)
        self.lst_order.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        for key, label in [
            ("median", "Median"),
            ("level", "Leveling"),
            ("destripe", "Destriping"),
            ("lowess", "LOWESS line trend"),
            ("destripe_ransac", "RANSAC baseline"),
            ("hough_streak", "Hough streak removal"),
            ("deconv", "Deconvolution"),
            ("wavelet", "Wavelet denoise"),
            ("nlm", "Non-Local Means"),
            ("pm", "Perona–Malik"),
            ("dtv", "Directional TV"),
            ("bm3d", "BM3D"),
            ("morphrec_bright", "Morph. recon (bright)"),
            ("morphrec_dark", "Morph. recon (dark)"),
        ]:
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.lst_order.addItem(it)
        self.lst_order.setSpacing(2)
        self.lst_order.setUniformItemSizes(True)

        self._fit_order_list_height()
        self.lst_order.model().rowsInserted.connect(lambda *_: self._fit_order_list_height())
        self.lst_order.model().rowsRemoved.connect(lambda *_: self._fit_order_list_height())
        self.lst_order.model().rowsMoved.connect(lambda *_: self._fit_order_list_height())
        order_v.addWidget(self.lst_order)

        order_container = QWidget(self)
        oc_l = QVBoxLayout(order_container)
        oc_l.setContentsMargins(0, 0, 0, 0)
        oc_l.addWidget(order_grp)
        oc_l.addStretch(1)
        order_container.setMinimumWidth(260)
        main_splitter.addWidget(order_container)

        # --- panel parametrów po prawej (scroll) ---
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        params_widget = QWidget(self)
        params_layout = QVBoxLayout(params_widget)
        scroll.setWidget(params_widget)
        scroll.setMinimumWidth(320)
        main_splitter.addWidget(scroll)

        # proporcje
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        main_splitter.setStretchFactor(3, 0)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setSizes([500, 500, 260, 360])

        # ---------- GRUPY PARAMETRÓW ----------

        # 1) Median
        grp_median = QGroupBox("1. Median filter")
        form_median = QFormLayout(grp_median)
        self.cb_median = QCheckBox("Enable")
        self.sp_median_size = QSpinBox(); self.sp_median_size.setRange(3, 99); self.sp_median_size.setSingleStep(2); self.sp_median_size.setValue(3)
        form_median.addRow(self.cb_median)
        form_median.addRow("Kernel (px):", self.sp_median_size)
        params_layout.addWidget(grp_median)

        # 1b) Leveling
        grp_level = QGroupBox("1b. Plane/Polynomial leveling")
        form_level = QFormLayout(grp_level)
        self.cb_level = QCheckBox("Enable"); self.cb_level.setChecked(True)
        self.cmb_level_deg = QComboBox(); self.cmb_level_deg.addItems(["0: constant", "1: plane", "2: quadratic"])
        form_level.addRow(self.cb_level)
        form_level.addRow("Degree:", self.cmb_level_deg)
        params_layout.addWidget(grp_level)

        # 2) Destriping (median rows/cols – uproszczony przełącznik)
        grp_destripe = QGroupBox("2. Scan-line correction")
        form_destripe = QFormLayout(grp_destripe)
        self.cb_destripe = QCheckBox("Enable"); self.cb_destripe.setChecked(True)
        form_destripe.addRow(self.cb_destripe)
        params_layout.addWidget(grp_destripe)

        # 2b) RANSAC line baseline
        grp_ransac = QGroupBox("2b. RANSAC line baseline")
        form_ransac = QFormLayout(grp_ransac)
        self.cb_ransac = QCheckBox("Enable")
        self.cmb_r_axis = QComboBox(); self.cmb_r_axis.addItems(["Rows (horizontal)", "Cols (vertical)"])
        self.sp_r_poly = QSpinBox(); self.sp_r_poly.setRange(0, 3); self.sp_r_poly.setValue(1)
        self.sp_r_resid = QDoubleSpinBox(); self.sp_r_resid.setRange(0.1, 50.0); self.sp_r_resid.setSingleStep(0.1); self.sp_r_resid.setValue(3.0)
        self.sp_r_trials = QSpinBox(); self.sp_r_trials.setRange(10, 5000); self.sp_r_trials.setValue(200)
        form_ransac.addRow(self.cb_ransac)
        form_ransac.addRow("Axis:", self.cmb_r_axis)
        form_ransac.addRow("Poly degree:", self.sp_r_poly)
        form_ransac.addRow("Residual:", self.sp_r_resid)
        form_ransac.addRow("Trials:", self.sp_r_trials)
        params_layout.addWidget(grp_ransac)

        # 2c) Remove horizontal lines + inpaint
        grp_hlines = QGroupBox("2c. Remove horizontal lines + inpaint")
        form_hl = QFormLayout(grp_hlines)
        self.cb_hl_enable = QCheckBox("Enable"); self.cb_hl_enable.setChecked(True)
        self.sp_hl_Lmin = QSpinBox(); self.sp_hl_Lmin.setRange(1, 5000); self.sp_hl_Lmin.setValue(25)
        self.sp_hl_Lse  = QSpinBox(); self.sp_hl_Lse.setRange(3, 1001); self.sp_hl_Lse.setSingleStep(2); self.sp_hl_Lse.setValue(61)
        self.sp_hl_Wse  = QSpinBox(); self.sp_hl_Wse.setRange(1, 21); self.sp_hl_Wse.setValue(1)
        self.sp_hl_Wmax = QSpinBox(); self.sp_hl_Wmax.setRange(1, 50); self.sp_hl_Wmax.setValue(2)
        self.le_hl_angles = QLineEdit(); self.le_hl_angles.setText("-1.5,0,1.5")
        form_hl.addRow(self.cb_hl_enable)
        form_hl.addRow("Min length (px):", self.sp_hl_Lmin)
        form_hl.addRow("SE length (px):", self.sp_hl_Lse)
        form_hl.addRow("SE width (px):", self.sp_hl_Wse)
        form_hl.addRow("Max width keep (px):", self.sp_hl_Wmax)
        form_hl.addRow("Angles (deg, csv):", self.le_hl_angles)
        params_layout.addWidget(grp_hlines)

        # 2d) LOWESS
        grp_lowess = QGroupBox("2d. LOWESS per-line")
        form_lowess = QFormLayout(grp_lowess)
        self.cb_lowess = QCheckBox("Enable")
        self.cmb_l_axis = QComboBox(); self.cmb_l_axis.addItems(["Rows (horizontal)", "Cols (vertical)"])
        self.sp_l_frac = QDoubleSpinBox(); self.sp_l_frac.setRange(0.01, 0.99); self.sp_l_frac.setSingleStep(0.01); self.sp_l_frac.setValue(0.10)
        self.sp_l_it = QSpinBox(); self.sp_l_it.setRange(0, 10); self.sp_l_it.setValue(1)
        self.sp_l_delta = QDoubleSpinBox(); self.sp_l_delta.setRange(0.0, 1000.0); self.sp_l_delta.setSingleStep(0.5); self.sp_l_delta.setValue(0.0)
        form_lowess.addRow(self.cb_lowess)
        form_lowess.addRow("Axis:", self.cmb_l_axis)
        form_lowess.addRow("frac:", self.sp_l_frac)
        form_lowess.addRow("robust iters:", self.sp_l_it)
        form_lowess.addRow("delta:", self.sp_l_delta)
        params_layout.addWidget(grp_lowess)

        # 2e) Hough streak removal
        grp_hough = QGroupBox("2e. Hough-guided streak removal")
        form_hough = QFormLayout(grp_hough)
        self.cb_hough_enable = QCheckBox("Enable")
        self.sp_h_canny = QDoubleSpinBox(); self.sp_h_canny.setRange(0.1, 10.0); self.sp_h_canny.setSingleStep(0.1); self.sp_h_canny.setValue(1.0)
        self.sp_h_angle = QDoubleSpinBox(); self.sp_h_angle.setRange(-180.0, 180.0); self.sp_h_angle.setDecimals(1); self.sp_h_angle.setValue(0.0)
        self.sp_h_tol   = QDoubleSpinBox(); self.sp_h_tol.setRange(0.1, 45.0); self.sp_h_tol.setSingleStep(0.1); self.sp_h_tol.setValue(5.0)
        self.sp_h_thr   = QSpinBox(); self.sp_h_thr.setRange(1, 2000); self.sp_h_thr.setValue(10)
        self.sp_h_len   = QSpinBox(); self.sp_h_len.setRange(5, 5000); self.sp_h_len.setValue(30)
        self.sp_h_gap   = QSpinBox(); self.sp_h_gap.setRange(0, 100); self.sp_h_gap.setValue(5)
        self.sp_h_w     = QSpinBox(); self.sp_h_w.setRange(1, 25); self.sp_h_w.setValue(3)
        form_hough.addRow(self.cb_hough_enable)
        form_hough.addRow("Canny sigma:", self.sp_h_canny)
        form_hough.addRow("Angle center (deg):", self.sp_h_angle)
        form_hough.addRow("Angle tolerance (deg):", self.sp_h_tol)
        form_hough.addRow("Threshold:", self.sp_h_thr)
        form_hough.addRow("Min line length (px):", self.sp_h_len)
        form_hough.addRow("Max line gap (px):", self.sp_h_gap)
        form_hough.addRow("Mask width (px):", self.sp_h_w)
        params_layout.addWidget(grp_hough)

        # 3) Deconvolution
        grp_deconv = QGroupBox("3. Deconvolution")
        deconv_layout = QVBoxLayout(grp_deconv)
        self.rb_deconv_none = QRadioButton("None"); self.rb_deconv_none.setChecked(True)
        self.rb_deconv_rl = QRadioButton("Richardson–Lucy")
        self.rb_deconv_wiener = QRadioButton("Unsupervised Wiener")
        deconv_layout.addWidget(self.rb_deconv_none)
        deconv_layout.addWidget(self.rb_deconv_rl)
        deconv_layout.addWidget(self.rb_deconv_wiener)
        # parametry RL
        self.params_rl = QWidget()
        form_rl = QFormLayout(self.params_rl)
        self.sp_rl_iter = QSpinBox(); self.sp_rl_iter.setRange(1, 100); self.sp_rl_iter.setValue(15)
        self.sp_psf_sx = QDoubleSpinBox(); self.sp_psf_sx.setRange(0.1, 10.0); self.sp_psf_sx.setSingleStep(0.1); self.sp_psf_sx.setValue(2.0)
        self.sp_psf_sy = QDoubleSpinBox(); self.sp_psf_sy.setRange(0.1, 10.0); self.sp_psf_sy.setSingleStep(0.1); self.sp_psf_sy.setValue(0.5)
        form_rl.addRow("Iterations:", self.sp_rl_iter)
        form_rl.addRow("PSF σx:", self.sp_psf_sx)
        form_rl.addRow("PSF σy:", self.sp_psf_sy)
        self.params_rl.setVisible(False)
        deconv_layout.addWidget(self.params_rl)
        params_layout.addWidget(grp_deconv)

        # 3.5) Wavelet
        grp_wv = QGroupBox("3.5 Wavelet denoise")
        form_wv = QFormLayout(grp_wv)
        self.cb_wv_enable = QCheckBox("Enable")
        self.cmb_wv_method = QComboBox(); self.cmb_wv_method.addItems(["BayesShrink", "VisuShrink"])
        self.cmb_wv_mode = QComboBox(); self.cmb_wv_mode.addItems(["soft", "hard"])
        self.cmb_wv_name = QComboBox(); self.cmb_wv_name.addItems(["db2", "db3", "sym4", "coif2"])
        self.sp_wv_level = QSpinBox(); self.sp_wv_level.setRange(0, 10); self.sp_wv_level.setValue(0)
        self.cb_wv_rescale = QCheckBox("Rescale sigma"); self.cb_wv_rescale.setChecked(True)
        form_wv.addRow(self.cb_wv_enable)
        form_wv.addRow("Method:", self.cmb_wv_method)
        form_wv.addRow("Mode:", self.cmb_wv_mode)
        form_wv.addRow("Wavelet:", self.cmb_wv_name)
        form_wv.addRow("Levels (0=auto):", self.sp_wv_level)
        form_wv.addRow(self.cb_wv_rescale)
        params_layout.addWidget(grp_wv)

        # 3.6) NLM
        grp_nlm = QGroupBox("3.6 Non-Local Means")
        form_nlm = QFormLayout(grp_nlm)
        self.cb_nlm_enable = QCheckBox("Enable")
        self.cb_nlm_auto = QCheckBox("Auto sigma"); self.cb_nlm_auto.setChecked(True)
        self.sp_nlm_h = QDoubleSpinBox(); self.sp_nlm_h.setRange(0.0, 1.0); self.sp_nlm_h.setSingleStep(0.01); self.sp_nlm_h.setValue(0.1)
        self.sp_nlm_hfac = QDoubleSpinBox(); self.sp_nlm_hfac.setRange(0.1, 5.0); self.sp_nlm_hfac.setSingleStep(0.1); self.sp_nlm_hfac.setValue(1.0)
        self.sp_nlm_ps = QSpinBox(); self.sp_nlm_ps.setRange(1, 31); self.sp_nlm_ps.setSingleStep(2); self.sp_nlm_ps.setValue(7)
        self.sp_nlm_pd = QSpinBox(); self.sp_nlm_pd.setRange(1, 63); self.sp_nlm_pd.setValue(15)
        self.cb_nlm_fast = QCheckBox("Fast mode"); self.cb_nlm_fast.setChecked(True)
        form_nlm.addRow(self.cb_nlm_enable)
        form_nlm.addRow("Auto sigma:", self.cb_nlm_auto)
        form_nlm.addRow("h:", self.sp_nlm_h)
        form_nlm.addRow("h factor:", self.sp_nlm_hfac)
        form_nlm.addRow("Patch size:", self.sp_nlm_ps)
        form_nlm.addRow("Patch distance:", self.sp_nlm_pd)
        form_nlm.addRow(self.cb_nlm_fast)
        params_layout.addWidget(grp_nlm)

        # 3.7) Perona–Malik
        grp_pm = QGroupBox("3.7 Perona–Malik")
        form_pm = QFormLayout(grp_pm)
        self.cb_pm_enable = QCheckBox("Enable")
        self.sp_pm_iter = QSpinBox(); self.sp_pm_iter.setRange(1, 500); self.sp_pm_iter.setValue(10)
        self.sp_pm_kappa = QDoubleSpinBox(); self.sp_pm_kappa.setRange(0.1, 200.0); self.sp_pm_kappa.setSingleStep(0.1); self.sp_pm_kappa.setValue(20.0)
        self.sp_pm_gamma = QDoubleSpinBox(); self.sp_pm_gamma.setRange(0.01, 0.25); self.sp_pm_gamma.setSingleStep(0.01); self.sp_pm_gamma.setValue(0.15)
        self.cmb_pm_opt = QComboBox(); self.cmb_pm_opt.addItems(["option 1", "option 2"])
        form_pm.addRow(self.cb_pm_enable)
        form_pm.addRow("Iterations:", self.sp_pm_iter)
        form_pm.addRow("kappa:", self.sp_pm_kappa)
        form_pm.addRow("gamma:", self.sp_pm_gamma)
        form_pm.addRow("Scheme:", self.cmb_pm_opt)
        params_layout.addWidget(grp_pm)

        # 3.8) Directional TV
        grp_dtv = QGroupBox("3.8 Directional TV")
        form_dtv = QFormLayout(grp_dtv)
        self.cb_dtv_enable = QCheckBox("Enable")
        self.sp_dtv_angle = QDoubleSpinBox(); self.sp_dtv_angle.setRange(-180.0, 180.0); self.sp_dtv_angle.setDecimals(1); self.sp_dtv_angle.setValue(0.0)
        self.sp_dtv_lalong = QDoubleSpinBox(); self.sp_dtv_lalong.setRange(0.0, 5.0); self.sp_dtv_lalong.setSingleStep(0.01); self.sp_dtv_lalong.setValue(0.2)
        self.sp_dtv_lacross = QDoubleSpinBox(); self.sp_dtv_lacross.setRange(0.0, 5.0); self.sp_dtv_lacross.setSingleStep(0.01); self.sp_dtv_lacross.setValue(0.05)
        self.sp_dtv_iter = QSpinBox(); self.sp_dtv_iter.setRange(1, 5000); self.sp_dtv_iter.setValue(50)
        form_dtv.addRow(self.cb_dtv_enable)
        form_dtv.addRow("Angle (deg):", self.sp_dtv_angle)
        form_dtv.addRow("λ along:", self.sp_dtv_lalong)
        form_dtv.addRow("λ across:", self.sp_dtv_lacross)
        form_dtv.addRow("Iterations:", self.sp_dtv_iter)
        params_layout.addWidget(grp_dtv)

        # 4) BM3D
        grp_bm3d = QGroupBox("4. BM3D denoise")
        form_bm3d = QFormLayout(grp_bm3d)
        self.cb_bm3d = QCheckBox("Enable")
        self.sp_bm3d_sigma = QDoubleSpinBox(); self.sp_bm3d_sigma.setRange(0.1, 5.0); self.sp_bm3d_sigma.setSingleStep(0.1); self.sp_bm3d_sigma.setValue(1.0)
        form_bm3d.addRow(self.cb_bm3d)
        form_bm3d.addRow("Sigma factor:", self.sp_bm3d_sigma)
        params_layout.addWidget(grp_bm3d)

        # 5) Morphological reconstruction – bright
        grp_mr_bright = QGroupBox("5. Morph. reconstruction (bright)")
        form_mr_bright = QFormLayout(grp_mr_bright)
        self.cb_mr_bright = QCheckBox("Enable")
        self.sp_mr_b_len = QSpinBox(); self.sp_mr_b_len.setRange(3, 1001); self.sp_mr_b_len.setSingleStep(2); self.sp_mr_b_len.setValue(31)
        self.sp_mr_b_w = QSpinBox(); self.sp_mr_b_w.setRange(1, 21); self.sp_mr_b_w.setValue(1)
        self.sp_mr_b_ang = QDoubleSpinBox(); self.sp_mr_b_ang.setRange(-180.0, 180.0); self.sp_mr_b_ang.setDecimals(1); self.sp_mr_b_ang.setValue(0.0)
        form_mr_bright.addRow(self.cb_mr_bright)
        form_mr_bright.addRow("SE length (px):", self.sp_mr_b_len)
        form_mr_bright.addRow("SE width (px):", self.sp_mr_b_w)
        form_mr_bright.addRow("Direction (deg):", self.sp_mr_b_ang)
        params_layout.addWidget(grp_mr_bright)

        # 5b) Morphological reconstruction – dark
        grp_mr_dark = QGroupBox("5b. Morph. reconstruction (dark)")
        form_mr_dark = QFormLayout(grp_mr_dark)
        self.cb_mr_dark = QCheckBox("Enable")
        self.sp_mr_d_len = QSpinBox(); self.sp_mr_d_len.setRange(3, 1001); self.sp_mr_d_len.setSingleStep(2); self.sp_mr_d_len.setValue(31)
        self.sp_mr_d_w = QSpinBox(); self.sp_mr_d_w.setRange(1, 21); self.sp_mr_d_w.setValue(1)
        self.sp_mr_d_ang = QDoubleSpinBox(); self.sp_mr_d_ang.setRange(-180.0, 180.0); self.sp_mr_d_ang.setDecimals(1); self.sp_mr_d_ang.setValue(0.0)
        form_mr_dark.addRow(self.cb_mr_dark)
        form_mr_dark.addRow("SE length (px):", self.sp_mr_d_len)
        form_mr_dark.addRow("SE width (px):", self.sp_mr_d_w)
        form_mr_dark.addRow("Direction (deg):", self.sp_mr_d_ang)
        params_layout.addWidget(grp_mr_dark)

        # Protection
        grp_protect = QGroupBox("Protection: keep large/thick objects")
        form_protect = QFormLayout(grp_protect)
        self.sp_protect_area = QSpinBox(); self.sp_protect_area.setRange(0, 100000); self.sp_protect_area.setValue(0)
        self.sp_protect_minor = QSpinBox(); self.sp_protect_minor.setRange(0, 5000); self.sp_protect_minor.setValue(0)
        form_protect.addRow("Min area (px²):", self.sp_protect_area)
        form_protect.addRow("Min thickness (px):", self.sp_protect_minor)
        params_layout.addWidget(grp_protect)

        params_layout.addStretch(1)

        # --- przyciski OK/Cancel ---
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("OK", self); self.btn_ok.setEnabled(False)
        self.btn_cancel = QPushButton("Cancel", self)
        btn_box.addStretch(1)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_ok)

        # --- złożenie całości ---
        root_layout.addWidget(main_splitter, 1)
        root_layout.addLayout(btn_box)

    def _connect_signals(self):
        """Łączy sygnały UI z odpowiednimi metodami (slotami)."""
        self.btn_process.clicked.connect(self._on_process_clicked)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Logika pokazywania/ukrywania paneli z parametrami dekonwolucji
        self.rb_deconv_rl.toggled.connect(self.params_rl.setVisible)
        self.rb_deconv_wiener.toggled.connect(self.params_rl.setVisible)

    def _on_process_clicked(self):
        """Zbiera parametry z UI, uruchamia ciężkie przetwarzanie i aktualizuje podgląd."""

        angles_txt = self.le_hl_angles.text().strip()
        try:
            hl_angles = tuple(float(a) for a in angles_txt.split(",") if a.strip() != "")
        except Exception:
            hl_angles = (0.0,)
        spec = {
            'median_filter': self.cb_median.isChecked(),
            'median_size': self.sp_median_size.value(),
            'destripe': self.cb_destripe.isChecked(),
            'destripe_ransac': self.cb_ransac.isChecked(),
            'ransac_axis': 'rows' if self.cmb_r_axis.currentIndex() == 0 else 'cols',
            'ransac_poly_deg': self.sp_r_poly.value(),
            'ransac_residual': self.sp_r_resid.value(),
            'ransac_trials': self.sp_r_trials.value(),
            'deconv_mode': 'none',
            'rl_iter': self.sp_rl_iter.value(),
            'psf_sigma_x': self.sp_psf_sx.value(),
            'psf_sigma_y': self.sp_psf_sy.value(),
            'denoise_bm3d': self.cb_bm3d.isChecked(),
            'bm3d_sigma_factor': self.sp_bm3d_sigma.value(),
            'morphrec_bright_enable': self.cb_mr_bright.isChecked(),
            'morphrec_bright_len_px': self.sp_mr_b_len.value(),
            'morphrec_bright_w_px':   self.sp_mr_b_w.value(),  
            'morphrec_bright_angle':  self.sp_mr_b_ang.value(),
            'morphrec_dark_enable':   self.cb_mr_dark.isChecked(),
            'morphrec_dark_len_px':   self.sp_mr_d_len.value(),
            'morphrec_dark_w_px':     self.sp_mr_d_w.value(),  
            'morphrec_dark_angle':    self.sp_mr_d_ang.value(),
            'morphrec_protect_min_area_px': self.sp_protect_area.value(),
            'morphrec_protect_min_minor_px': self.sp_protect_minor.value(),
            'remove_hlines': self.cb_hl_enable.isChecked(),
            'hl_Lmin': self.sp_hl_Lmin.value(),
            'hl_Lse': self.sp_hl_Lse.value(),
            'hl_Wse': self.sp_hl_Wse.value(),
            'hl_Wmax_keep': self.sp_hl_Wmax.value(),
            'hl_angles': hl_angles,
            'wavelet_enable': self.cb_wv_enable.isChecked(),
            'wavelet_method': self.cmb_wv_method.currentText(),
            'wavelet_mode': self.cmb_wv_mode.currentText(),
            'wavelet_name': self.cmb_wv_name.currentText(),
            'wavelet_level': self.sp_wv_level.value(),
            'wavelet_rescale_sigma': self.cb_wv_rescale.isChecked(),
            'nlm_enable': self.cb_nlm_enable.isChecked(),
            'nlm_auto_sigma': self.cb_nlm_auto.isChecked(),
            'nlm_h': self.sp_nlm_h.value(),
            'nlm_h_factor': self.sp_nlm_hfac.value(),
            'nlm_patch_size': self.sp_nlm_ps.value(),
            'nlm_patch_distance': self.sp_nlm_pd.value(),
            'nlm_fast': self.cb_nlm_fast.isChecked(),
            'pm_enable': self.cb_pm_enable.isChecked(),
            'pm_n_iter': self.sp_pm_iter.value(),
            'pm_kappa': self.sp_pm_kappa.value(),
            'pm_gamma': self.sp_pm_gamma.value(),
            'pm_option': 1 if self.cmb_pm_opt.currentIndex() == 0 else 2,
            'dtv_enable': self.cb_dtv_enable.isChecked(),
            'dtv_angle': self.sp_dtv_angle.value(),
            'dtv_lam_along': self.sp_dtv_lalong.value(),
            'dtv_lam_across': self.sp_dtv_lacross.value(),
            'dtv_n_iter': self.sp_dtv_iter.value(),
            'destripe_lowess': self.cb_lowess.isChecked(),
            'lowess_axis': 'rows' if self.cmb_l_axis.currentIndex() == 0 else 'cols',
            'lowess_frac': self.sp_l_frac.value(),
            'lowess_it': self.sp_l_it.value(),
            'lowess_delta': self.sp_l_delta.value(),
            'hough_streak_enable': self.cb_hough_enable.isChecked(),
            'hough_canny_sigma': self.sp_h_canny.value(),
            'hough_angle_center': self.sp_h_angle.value(),
            'hough_angle_tol': self.sp_h_tol.value(),
            'hough_threshold': self.sp_h_thr.value(),
            'hough_line_length': self.sp_h_len.value(),
            'hough_line_gap': self.sp_h_gap.value(),
            'hough_mask_width': self.sp_h_w.value(),
            'level_enable': self.cb_level.isChecked(),
            'level_degree': self.cmb_level_deg.currentIndex(),  # 0/1/2
        }
        if self.rb_deconv_rl.isChecked():
            spec['deconv_mode'] = 'richardson_lucy'
        elif self.rb_deconv_wiener.isChecked():
            spec['deconv_mode'] = 'wiener'

        spec['order'] = [self.lst_order.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.lst_order.count())]
        
        if hasattr(self, "lst_order") and self.lst_order is not None:
            spec["order"] = [
                self.lst_order.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.lst_order.count())
            ]

        # try:
        #     spec_model = HeavyPreprocSpec(**spec).validate()
        # except Exception as e:
        #     QMessageBox.critical(self, "Spec error", f"Invalid parameters: {e}")

        progress = QProgressDialog("Processing image... This may take a moment.", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        try:
            # PRZEKAZUJEMY DICT, BO ZAWIERA 'order'
            self.processed_image = run_heavy_preprocessing(self.original_image, spec)
            self.viewer_processed.setImage(self.processed_image, autoRange=True, autoLevels=True)
            self.btn_ok.setEnabled(True)
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Preprocessing failed: {e}")
        finally:
            progress.close()

    def get_processed_image(self) -> Optional[np.ndarray]:
        """Zwraca przetworzony obraz po zamknięciu dialogu przyciskiem OK."""
        return self.processed_image
    
    def _spec_from_ui(self) -> dict:
        """Zbierz parametry z UI + kolejność z listy."""
        spec = {}
        # kolejność
        spec["order"] = [self.lst_order.item(i).data(Qt.ItemDataRole.UserRole)
                        for i in range(self.lst_order.count())]
        # przykładowe parametry (uzupełnij analogicznie pozostałe)
        spec["median_filter"] = self.cb_median.isChecked()
        spec["median_size"] = int(self.sp_median_size.value())

        spec["level_enable"] = self.cb_level.isChecked()
        spec["level_degree"] = self.cmb_level_deg.currentIndex()  # 0,1,2

        spec["destripe"] = self.cb_destripe.isChecked()

        spec["destripe_ransac"] = self.cb_ransac.isChecked()
        spec["ransac_axis"] = "rows" if self.cmb_r_axis.currentIndex() == 0 else "cols"
        spec["ransac_poly_deg"] = int(self.sp_r_poly.value())
        spec["ransac_residual"] = float(self.sp_r_resid.value())
        spec["ransac_trials"] = int(self.sp_r_trials.value())

        spec["hough_streak_enable"] = self.cb_hough_enable.isChecked()
        spec["hough_canny_sigma"] = float(self.sp_h_canny.value())
        spec["hough_angle_center"] = float(self.sp_h_angle.value())
        spec["hough_angle_tol"] = float(self.sp_h_tol.value())
        spec["hough_threshold"] = int(self.sp_h_thr.value())
        spec["hough_line_length"] = int(self.sp_h_len.value())
        spec["hough_line_gap"] = int(self.sp_h_gap.value())
        spec["hough_mask_width"] = int(self.sp_h_w.value())

        spec["deconv_mode"] = (
            "none" if self.rb_deconv_none.isChecked()
            else "richardson_lucy" if self.rb_deconv_rl.isChecked()
            else "wiener"
        )
        spec["rl_iter"] = int(self.sp_rl_iter.value())
        spec["psf_sigma_x"] = float(self.sp_psf_sx.value())
        spec["psf_sigma_y"] = float(self.sp_psf_sy.value())

        spec["wavelet_enable"] = self.cb_wv_enable.isChecked()
        spec["wavelet_method"] = self.cmb_wv_method.currentText()
        spec["wavelet_mode"] = self.cmb_wv_mode.currentText()
        spec["wavelet_name"] = self.cmb_wv_name.currentText()
        spec["wavelet_level"] = int(self.sp_wv_level.value())
        spec["wavelet_rescale_sigma"] = self.cb_wv_rescale.isChecked()

        spec["nlm_enable"] = self.cb_nlm_enable.isChecked()
        spec["nlm_auto_sigma"] = self.cb_nlm_auto.isChecked()
        spec["nlm_h"] = float(self.sp_nlm_h.value())
        spec["nlm_h_factor"] = float(self.sp_nlm_hfac.value())
        spec["nlm_patch_size"] = int(self.sp_nlm_ps.value())
        spec["nlm_patch_distance"] = int(self.sp_nlm_pd.value())
        spec["nlm_fast"] = self.cb_nlm_fast.isChecked()

        spec["pm_enable"] = self.cb_pm_enable.isChecked()
        spec["pm_n_iter"] = int(self.sp_pm_iter.value())
        spec["pm_kappa"] = float(self.sp_pm_kappa.value())
        spec["pm_gamma"] = float(self.sp_pm_gamma.value())
        spec["pm_option"] = int(self.cmb_pm_opt.currentIndex()) + 1  # 1/2

        spec["dtv_enable"] = self.cb_dtv_enable.isChecked()
        spec["dtv_angle"] = float(self.sp_dtv_angle.value())
        spec["dtv_lam_along"] = float(self.sp_dtv_lalong.value())
        spec["dtv_lam_across"] = float(self.sp_dtv_lacross.value())
        spec["dtv_n_iter"] = int(self.sp_dtv_iter.value())

        spec["denoise_bm3d"] = self.cb_bm3d.isChecked()
        spec["bm3d_sigma_factor"] = float(self.sp_bm3d_sigma.value())

        spec["morphrec_bright_enable"] = self.cb_mr_bright.isChecked()
        spec["morphrec_bright_len_px"] = int(self.sp_mr_b_len.value())
        spec["morphrec_bright_w_px"] = int(self.sp_mr_b_w.value())
        spec["morphrec_bright_angle"] = float(self.sp_mr_b_ang.value())

        spec["morphrec_dark_enable"] = self.cb_mr_dark.isChecked()
        spec["morphrec_dark_len_px"] = int(self.sp_mr_d_len.value())
        spec["morphrec_dark_w_px"] = int(self.sp_mr_d_w.value())
        spec["morphrec_dark_angle"] = float(self.sp_mr_d_ang.value())

        spec["morphrec_protect_min_area_px"] = int(self.sp_protect_area.value())
        spec["morphrec_protect_min_minor_px"] = int(self.sp_protect_minor.value())

        return spec

    def _apply_spec_to_ui(self, spec: dict):
        """Zastosuj preset do UI. Nieznane klucze pomiń."""
        # kolejność
        if "order" in spec:
            self._set_order_list(spec["order"])
        # przykładowe mapowania (uzupełnij analogicznie, jak w _spec_from_ui)
        self.cb_median.setChecked(bool(spec.get("median_filter", self.cb_median.isChecked())))
        self.sp_median_size.setValue(int(spec.get("median_size", self.sp_median_size.value())))

        self.cb_level.setChecked(bool(spec.get("level_enable", self.cb_level.isChecked())))
        self.cmb_level_deg.setCurrentIndex(int(spec.get("level_degree", self.cmb_level_deg.currentIndex())))

        self.cb_destripe.setChecked(bool(spec.get("destripe", self.cb_destripe.isChecked())))

        self.cb_ransac.setChecked(bool(spec.get("destripe_ransac", self.cb_ransac.isChecked())))
        self.cmb_r_axis.setCurrentIndex(0 if spec.get("ransac_axis","rows")=="rows" else 1)
        self.sp_r_poly.setValue(int(spec.get("ransac_poly_deg", self.sp_r_poly.value())))
        self.sp_r_resid.setValue(float(spec.get("ransac_residual", self.sp_r_resid.value())))
        self.sp_r_trials.setValue(int(spec.get("ransac_trials", self.sp_r_trials.value())))

        self.cb_hough_enable.setChecked(bool(spec.get("hough_streak_enable", self.cb_hough_enable.isChecked())))
        self.sp_h_canny.setValue(float(spec.get("hough_canny_sigma", self.sp_h_canny.value())))
        self.sp_h_angle.setValue(float(spec.get("hough_angle_center", self.sp_h_angle.value())))
        self.sp_h_tol.setValue(float(spec.get("hough_angle_tol", self.sp_h_tol.value())))
        self.sp_h_thr.setValue(int(spec.get("hough_threshold", self.sp_h_thr.value())))
        self.sp_h_len.setValue(int(spec.get("hough_line_length", self.sp_h_len.value())))
        self.sp_h_gap.setValue(int(spec.get("hough_line_gap", self.sp_h_gap.value())))
        self.sp_h_w.setValue(int(spec.get("hough_mask_width", self.sp_h_w.value())))

        mode = spec.get("deconv_mode", None)
        if mode:
            self.rb_deconv_none.setChecked(mode=="none")
            self.rb_deconv_rl.setChecked(mode=="richardson_lucy")
            self.rb_deconv_wiener.setChecked(mode=="wiener")
        self.sp_rl_iter.setValue(int(spec.get("rl_iter", self.sp_rl_iter.value())))
        self.sp_psf_sx.setValue(float(spec.get("psf_sigma_x", self.sp_psf_sx.value())))
        self.sp_psf_sy.setValue(float(spec.get("psf_sigma_y", self.sp_psf_sy.value())))

        self.cb_wv_enable.setChecked(bool(spec.get("wavelet_enable", self.cb_wv_enable.isChecked())))
        self.cmb_wv_method.setCurrentText(spec.get("wavelet_method", self.cmb_wv_method.currentText()))
        self.cmb_wv_mode.setCurrentText(spec.get("wavelet_mode", self.cmb_wv_mode.currentText()))
        self.cmb_wv_name.setCurrentText(spec.get("wavelet_name", self.cmb_wv_name.currentText()))
        self.sp_wv_level.setValue(int(spec.get("wavelet_level", self.sp_wv_level.value())))
        self.cb_wv_rescale.setChecked(bool(spec.get("wavelet_rescale_sigma", self.cb_wv_rescale.isChecked())))

        self.cb_nlm_enable.setChecked(bool(spec.get("nlm_enable", self.cb_nlm_enable.isChecked())))
        self.cb_nlm_auto.setChecked(bool(spec.get("nlm_auto_sigma", self.cb_nlm_auto.isChecked())))
        self.sp_nlm_h.setValue(float(spec.get("nlm_h", self.sp_nlm_h.value())))
        self.sp_nlm_hfac.setValue(float(spec.get("nlm_h_factor", self.sp_nlm_hfac.value())))
        self.sp_nlm_ps.setValue(int(spec.get("nlm_patch_size", self.sp_nlm_ps.value())))
        self.sp_nlm_pd.setValue(int(spec.get("nlm_patch_distance", self.sp_nlm_pd.value())))
        self.cb_nlm_fast.setChecked(bool(spec.get("nlm_fast", self.cb_nlm_fast.isChecked())))

        self.cb_pm_enable.setChecked(bool(spec.get("pm_enable", self.cb_pm_enable.isChecked())))
        self.sp_pm_iter.setValue(int(spec.get("pm_n_iter", self.sp_pm_iter.value())))
        self.sp_pm_kappa.setValue(float(spec.get("pm_kappa", self.sp_pm_kappa.value())))
        self.sp_pm_gamma.setValue(float(spec.get("pm_gamma", self.sp_pm_gamma.value())))
        self.cmb_pm_opt.setCurrentIndex(int(spec.get("pm_option", 1)) - 1)

        self.cb_dtv_enable.setChecked(bool(spec.get("dtv_enable", self.cb_dtv_enable.isChecked())))
        self.sp_dtv_angle.setValue(float(spec.get("dtv_angle", self.sp_dtv_angle.value())))
        self.sp_dtv_lalong.setValue(float(spec.get("dtv_lam_along", self.sp_dtv_lalong.value())))
        self.sp_dtv_lacross.setValue(float(spec.get("dtv_lam_across", self.sp_dtv_lacross.value())))
        self.sp_dtv_iter.setValue(int(spec.get("dtv_n_iter", self.sp_dtv_iter.value())))

        self.cb_bm3d.setChecked(bool(spec.get("denoise_bm3d", self.cb_bm3d.isChecked())))
        self.sp_bm3d_sigma.setValue(float(spec.get("bm3d_sigma_factor", self.sp_bm3d_sigma.value())))

        self.cb_mr_bright.setChecked(bool(spec.get("morphrec_bright_enable", self.cb_mr_bright.isChecked())))
        self.sp_mr_b_len.setValue(int(spec.get("morphrec_bright_len_px", self.sp_mr_b_len.value())))
        self.sp_mr_b_w.setValue(int(spec.get("morphrec_bright_w_px", self.sp_mr_b_w.value())))
        self.sp_mr_b_ang.setValue(float(spec.get("morphrec_bright_angle", self.sp_mr_b_ang.value())))

        self.cb_mr_dark.setChecked(bool(spec.get("morphrec_dark_enable", self.cb_mr_dark.isChecked())))
        self.sp_mr_d_len.setValue(int(spec.get("morphrec_dark_len_px", self.sp_mr_d_len.value())))
        self.sp_mr_d_w.setValue(int(spec.get("morphrec_dark_w_px", self.sp_mr_d_w.value())))
        self.sp_mr_d_ang.setValue(float(spec.get("morphrec_dark_angle", self.sp_mr_d_ang.value())))

    def _set_order_list(self, order_keys: list[str]):
        """Ustaw ListView wg listy kluczy. Braki/dodatki obsłuż bezpiecznie."""
        # etykiety
        LABELS = {
            "median":"Median","level":"Leveling","destripe":"Destriping","lowess":"LOWESS",
            "destripe_ransac":"RANSAC baseline","hough_streak":"Hough streak removal",
            "deconv":"Deconvolution","wavelet":"Wavelet denoise","nlm":"Non-Local Means",
            "pm":"Perona–Malik","dtv":"Directional TV","bm3d":"BM3D",
            "morphrec_bright":"Morph. recon (bright)","morphrec_dark":"Morph. recon (dark)",
        }
        # dostępne kroki
        from napara.processing.pipeline import STEP_REGISTRY, DEFAULT_ORDER
        valid = [k for k in order_keys if k in STEP_REGISTRY]
        # dodaj brakujące na końcu wg DEFAULT_ORDER
        for k in DEFAULT_ORDER:
            if k not in valid and k in STEP_REGISTRY:
                valid.append(k)
        self.lst_order.clear()
        from PyQt6.QtWidgets import QListWidgetItem
        for k in valid:
            it = QListWidgetItem(LABELS.get(k, k))
            it.setData(Qt.ItemDataRole.UserRole, k)
            self.lst_order.addItem(it)
    
    def _on_preset_save(self):
        spec = self._spec_from_ui()
        preset = {
            "schema": PRESET_SCHEMA,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "order": spec.get("order", []),
            "params": {k:v for k,v in spec.items() if k != "order"},
        }
        path, _ = QFileDialog.getSaveFileName(self, "Save preset", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(preset, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot save preset:\n{e}")

    def _on_preset_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load preset", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                preset = json.load(f)
            if preset.get("schema") != PRESET_SCHEMA:
                # prosta tolerancja wersji: akceptuj v1* prefix
                if not str(preset.get("schema","")).startswith("napara.preprocessing.v1"):
                    raise ValueError("Unsupported preset schema")
            order = preset.get("order", [])
            params = preset.get("params", {})
            self._set_order_list(order)
            self._apply_spec_to_ui({**params, "order": order})
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot load preset:\n{e}")

    def _on_preset_reset(self):
        # przywróć domyślne UI i kolejność
        from napara.processing.pipeline import DEFAULT_ORDER
        self._set_order_list(DEFAULT_ORDER)
        # opcjonalnie: wyczyść/ustaw domyślne wartości kontrolek
        # (tu pozostaw aktualne; jeśli chcesz twardy reset, ustaw sensowne domyślne wartości)