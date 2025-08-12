
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QFormLayout,
    QPushButton, QCheckBox, QDoubleSpinBox, QMessageBox, QProgressDialog,
    QWidget, QRadioButton, QSpinBox, QApplication, QScrollArea, QComboBox,
    QLineEdit
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np
from typing import Optional
from napara.processing.pipeline import run_heavy_preprocessing

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

    def _build_ui(self):
        # --- Główne Layouty ---
        root_layout = QVBoxLayout(self)

        top_btn_layout = QHBoxLayout()
        top_btn_layout.addStretch(1)  # pcha przycisk w prawo
        self.btn_process = QPushButton("Process", self)
        top_btn_layout.addWidget(self.btn_process)
        root_layout.addLayout(top_btn_layout)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Panele z obrazami ---
        self.viewer_original = pg.ImageView(self)
        self.viewer_processed = pg.ImageView(self)
        # Ukrywamy zbędne elementy UI w przeglądarkach
        for viewer in [self.viewer_original, self.viewer_processed]:
            viewer.ui.histogram.hide()
            viewer.ui.roiBtn.hide()
            viewer.ui.menuBtn.hide()
            viewer.getView().setAspectLocked(True)

        main_splitter.addWidget(self.viewer_original)
        main_splitter.addWidget(self.viewer_processed)

        # --- Panel z parametrami po prawej ---
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        params_widget = QWidget(self)
        params_layout = QVBoxLayout(params_widget)
        scroll.setWidget(params_widget)
        scroll.setMinimumWidth(280)
        main_splitter.setSizes([450, 450, 320])

        main_splitter.addWidget(scroll)
        
        # Krok 1: Filtr Medianowy
        grp_median = QGroupBox("1. Optional: Median Filter (Pre-cleaning)")
        form_median = QFormLayout(grp_median)
        self.cb_median = QCheckBox("Enable")
        self.sp_median_size = QSpinBox()
        self.sp_median_size.setRange(3, 15)
        self.sp_median_size.setSingleStep(2) # Krok co 2, aby zachować nieparzystość
        self.sp_median_size.setValue(3)
        form_median.addRow(self.cb_median)
        form_median.addRow("Kernel Size (px):", self.sp_median_size)
        params_layout.addWidget(grp_median)

        # Krok 2: Destriping
        grp_destripe = QGroupBox("2. Scan-line Correction (Destriping)")
        form_destripe = QFormLayout(grp_destripe)
        self.cb_destripe = QCheckBox("Enable", grp_destripe)
        self.cb_destripe.setChecked(True)
        form_destripe.addRow(self.cb_destripe)
        params_layout.addWidget(grp_destripe)

        # 2b: RANSAC line baseline (robust per-line fitting)
        grp_ransac = QGroupBox("2b. RANSAC line baseline (robust per-line fitting)")
        form_ransac = QFormLayout(grp_ransac)
        self.cb_ransac = QCheckBox("Enable", grp_ransac)
        self.cmb_r_axis = QComboBox(); self.cmb_r_axis.addItems(["Rows (horizontal lines)", "Cols (vertical lines)"])
        self.sp_r_poly = QSpinBox(); self.sp_r_poly.setRange(0, 3); self.sp_r_poly.setValue(1)
        self.sp_r_resid = QDoubleSpinBox(); self.sp_r_resid.setRange(0.1, 50.0); self.sp_r_resid.setSingleStep(0.1); self.sp_r_resid.setValue(3.0)
        self.sp_r_trials = QSpinBox(); self.sp_r_trials.setRange(10, 2000); self.sp_r_trials.setValue(200)
        form_ransac.addRow(self.cb_ransac)
        form_ransac.addRow("Axis:", self.cmb_r_axis)
        form_ransac.addRow("Poly degree:", self.sp_r_poly)
        form_ransac.addRow("Residual thresh.:", self.sp_r_resid)
        form_ransac.addRow("Max trials:", self.sp_r_trials)
        params_layout.addWidget(grp_ransac)

        # 2c: Usuwanie linii poziomych + inpainting
        grp_hlines = QGroupBox("2c. Remove horizontal lines (selective) + Inpaint")
        form_hl = QFormLayout(grp_hlines)
        self.cb_hl_enable = QCheckBox("Enable", grp_hlines); self.cb_hl_enable.setChecked(True)

        self.sp_hl_Lmin = QSpinBox(); self.sp_hl_Lmin.setRange(1, 2000); self.sp_hl_Lmin.setValue(25)
        self.sp_hl_Lse  = QSpinBox(); self.sp_hl_Lse.setRange(3, 1001); self.sp_hl_Lse.setSingleStep(2); self.sp_hl_Lse.setValue(61)
        self.sp_hl_Wse  = QSpinBox(); self.sp_hl_Wse.setRange(1, 21); self.sp_hl_Wse.setValue(1)
        self.sp_hl_Wmax = QSpinBox(); self.sp_hl_Wmax.setRange(1, 50); self.sp_hl_Wmax.setValue(2)
        self.le_hl_angles = QLineEdit(); self.le_hl_angles.setText("-1.5,0,1.5")

        form_hl.addRow(self.cb_hl_enable)
        form_hl.addRow("Min length Lmin (px):", self.sp_hl_Lmin)
        form_hl.addRow("SE length Lse (px):",   self.sp_hl_Lse)
        form_hl.addRow("SE width Wse (px):",    self.sp_hl_Wse)
        form_hl.addRow("Max thickness (px):",   self.sp_hl_Wmax)
        form_hl.addRow("Angles (deg):",         self.le_hl_angles)

        params_layout.addWidget(grp_hlines)

        # Krok 3: Dekonwolucja
        grp_deconv = QGroupBox("3. Shape Recovery (Deconvolution)")
        deconv_layout = QVBoxLayout(grp_deconv)
        self.rb_deconv_none = QRadioButton("None")
        self.rb_deconv_rl = QRadioButton("Richardson-Lucy (manual PSF)")
        self.rb_deconv_wiener = QRadioButton("Unsupervised Wiener")
        self.rb_deconv_none.setChecked(True)
        deconv_layout.addWidget(self.rb_deconv_none)
        deconv_layout.addWidget(self.rb_deconv_rl)
        deconv_layout.addWidget(self.rb_deconv_wiener)
        
        # Kontenery na parametry, które będziemy pokazywać/ukrywać
        self.params_rl = QWidget()
        form_rl = QFormLayout(self.params_rl)
        self.sp_rl_iter = QSpinBox(); self.sp_rl_iter.setRange(1, 100); self.sp_rl_iter.setValue(15)
        self.sp_psf_sx = QDoubleSpinBox(); self.sp_psf_sx.setRange(0.1, 10.0); self.sp_psf_sx.setValue(2.0); self.sp_psf_sx.setSingleStep(0.1)
        self.sp_psf_sy = QDoubleSpinBox(); self.sp_psf_sy.setRange(0.1, 10.0); self.sp_psf_sy.setValue(0.5); self.sp_psf_sy.setSingleStep(0.1)
        form_rl.addRow("Iterations:", self.sp_rl_iter)
        form_rl.addRow("PSF Sigma X:", self.sp_psf_sx)
        form_rl.addRow("PSF Sigma Y:", self.sp_psf_sy)
        self.params_rl.setVisible(False)

        deconv_layout.addWidget(self.params_rl)
        params_layout.addWidget(grp_deconv)

        # Krok 4: Odszumianie BM3D
        grp_bm3d = QGroupBox("4. Denoising (BM3D)")
        form_bm3d = QFormLayout(grp_bm3d)
        self.cb_bm3d = QCheckBox("Enable", grp_bm3d)
        self.cb_bm3d.setChecked(True)
        self.sp_bm3d_sigma = QDoubleSpinBox(grp_bm3d)
        self.sp_bm3d_sigma.setRange(0.01, 10.0)
        self.sp_bm3d_sigma.setValue(1.0)
        self.sp_bm3d_sigma.setToolTip("Noise sigma estimation factor (1.0 = automatic from MAD)")
        form_bm3d.addRow(self.cb_bm3d)
        form_bm3d.addRow("Sigma Factor:", self.sp_bm3d_sigma)
        params_layout.addWidget(grp_bm3d)

        grp_wv = QGroupBox("4b. Wavelet Shrinkage")
        form_wv = QFormLayout(grp_wv)
        self.cb_wv_enable = QCheckBox("Enable")
        self.cmb_wv_method = QComboBox(); self.cmb_wv_method.addItems(["BayesShrink", "VisuShrink"])
        self.cmb_wv_mode = QComboBox(); self.cmb_wv_mode.addItems(["soft", "hard"])
        self.cmb_wv_name = QComboBox(); self.cmb_wv_name.addItems(["db2", "db1", "db3", "sym4", "coif1"])
        self.sp_wv_level = QSpinBox(); self.sp_wv_level.setRange(0, 10); self.sp_wv_level.setValue(0)  # 0=auto
        self.cb_wv_rescale = QCheckBox(); self.cb_wv_rescale.setChecked(True)
        form_wv.addRow(self.cb_wv_enable)
        form_wv.addRow("Method:", self.cmb_wv_method)
        form_wv.addRow("Mode:", self.cmb_wv_mode)
        form_wv.addRow("Wavelet:", self.cmb_wv_name)
        form_wv.addRow("Levels (0=auto):", self.sp_wv_level)
        form_wv.addRow("Rescale sigma:", self.cb_wv_rescale)
        params_layout.addWidget(grp_wv)

        # 4c: Non-Local Means (NLM)
        grp_nlm = QGroupBox("4c. Non-Local Means (NLM)")
        form_nlm = QFormLayout(grp_nlm)

        self.cb_nlm_enable = QCheckBox("Enable"); self.cb_nlm_enable.setChecked(False)
        self.cb_nlm_auto = QCheckBox("Auto sigma (estimate)"); self.cb_nlm_auto.setChecked(True)

        self.sp_nlm_h = QDoubleSpinBox(); self.sp_nlm_h.setRange(0.001, 5.0); self.sp_nlm_h.setSingleStep(0.01); self.sp_nlm_h.setValue(0.1)
        self.sp_nlm_hfac = QDoubleSpinBox(); self.sp_nlm_hfac.setRange(0.1, 5.0); self.sp_nlm_hfac.setSingleStep(0.1); self.sp_nlm_hfac.setValue(1.0)

        self.sp_nlm_ps = QSpinBox(); self.sp_nlm_ps.setRange(3, 21); self.sp_nlm_ps.setSingleStep(2); self.sp_nlm_ps.setValue(7)      # nieparzyste
        self.sp_nlm_pd = QSpinBox(); self.sp_nlm_pd.setRange(1, 31); self.sp_nlm_pd.setValue(15)
        self.cb_nlm_fast = QCheckBox("Fast mode"); self.cb_nlm_fast.setChecked(True)

        form_nlm.addRow(self.cb_nlm_enable)
        form_nlm.addRow(self.cb_nlm_auto)
        form_nlm.addRow("h (gdy auto=off):", self.sp_nlm_h)
        form_nlm.addRow("h factor (gdy auto=on):", self.sp_nlm_hfac)
        form_nlm.addRow("Patch size (px):", self.sp_nlm_ps)
        form_nlm.addRow("Patch distance (px):", self.sp_nlm_pd)
        form_nlm.addRow(self.cb_nlm_fast)

        params_layout.addWidget(grp_nlm)

        # 5A: Morph. by Reconstruction – Bright lines (Opening)
        grp_mr_bright = QGroupBox("5A. Morph. Reconstruction – remove BRIGHT lines (Opening)")
        form_mr_bright = QFormLayout(grp_mr_bright)
        self.cb_mr_bright = QCheckBox("Enable")
        self.sp_mr_b_len = QSpinBox(); self.sp_mr_b_len.setRange(3, 401); self.sp_mr_b_len.setSingleStep(2); self.sp_mr_b_len.setValue(31)
        self.sp_mr_b_w   = QSpinBox(); self.sp_mr_b_w.setRange(1, 21);  self.sp_mr_b_w.setValue(1)   # NEW: thickness
        self.sp_mr_b_ang = QDoubleSpinBox(); self.sp_mr_b_ang.setRange(-180.0, 180.0); self.sp_mr_b_ang.setDecimals(1); self.sp_mr_b_ang.setValue(0.0)
        form_mr_bright.addRow(self.cb_mr_bright)
        form_mr_bright.addRow("SE Length (px):", self.sp_mr_b_len)
        form_mr_bright.addRow("SE Width (px):",  self.sp_mr_b_w)   # NEW
        form_mr_bright.addRow("Direction (deg):", self.sp_mr_b_ang)
        params_layout.addWidget(grp_mr_bright)

        # 5B: Morph. by Reconstruction – Dark lines (Closing)
        grp_mr_dark = QGroupBox("5B. Morph. Reconstruction – remove DARK lines (Closing)")
        form_mr_dark = QFormLayout(grp_mr_dark)
        self.cb_mr_dark = QCheckBox("Enable")
        self.sp_mr_d_len = QSpinBox(); self.sp_mr_d_len.setRange(3, 401); self.sp_mr_d_len.setSingleStep(2); self.sp_mr_d_len.setValue(31)
        self.sp_mr_d_w   = QSpinBox(); self.sp_mr_d_w.setRange(1, 21);  self.sp_mr_d_w.setValue(1)   # NEW: thickness
        self.sp_mr_d_ang = QDoubleSpinBox(); self.sp_mr_d_ang.setRange(-180.0, 180.0); self.sp_mr_d_ang.setDecimals(1); self.sp_mr_d_ang.setValue(0.0)
        form_mr_dark.addRow(self.cb_mr_dark)
        form_mr_dark.addRow("SE Length (px):", self.sp_mr_d_len)
        form_mr_dark.addRow("SE Width (px):",  self.sp_mr_d_w)    # NEW
        form_mr_dark.addRow("Direction (deg):", self.sp_mr_d_ang)
        params_layout.addWidget(grp_mr_dark)

        grp_protect = QGroupBox("Protection: keep large/thick objects")
        form_protect = QFormLayout(grp_protect)
        self.sp_protect_area = QSpinBox(); self.sp_protect_area.setRange(0, 10_000); self.sp_protect_area.setValue(0)
        self.sp_protect_minor = QSpinBox(); self.sp_protect_minor.setRange(0, 1000); self.sp_protect_minor.setValue(0)
        form_protect.addRow("Min area to keep (px²):", self.sp_protect_area)
        form_protect.addRow("Min thickness to keep (px):", self.sp_protect_minor)
        params_layout.addWidget(grp_protect)

        params_layout.addStretch()

        # --- Przyciski ---
        # self.btn_process = QPushButton("Process", self)
        
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("OK", self)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_ok.setEnabled(False) # Dostępny dopiero po przetworzeniu
        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_ok)
        
        # params_layout.addWidget(self.btn_process)
        
        # --- Składanie UI ---
        root_layout.addWidget(main_splitter, 1)
        root_layout.addLayout(btn_box)
        # main_splitter.addWidget(params_widget)
        main_splitter.setSizes([450, 450, 200])

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
        }
        if self.rb_deconv_rl.isChecked():
            spec['deconv_mode'] = 'richardson_lucy'
        elif self.rb_deconv_wiener.isChecked():
            spec['deconv_mode'] = 'wiener'
        
        progress = QProgressDialog("Processing image... This may take a moment.", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            self.processed_image = run_heavy_preprocessing(self.original_image, spec)
            self.viewer_processed.setImage(self.processed_image, autoRange=True, autoLevels=True)
            self.btn_ok.setEnabled(True)
            QApplication.processEvents() # Wymuszenie odświeżenia UI
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Preprocessing failed: {e}")
        finally:
            progress.close()

    def get_processed_image(self) -> Optional[np.ndarray]:
        """Zwraca przetworzony obraz po zamknięciu dialogu przyciskiem OK."""
        return self.processed_image