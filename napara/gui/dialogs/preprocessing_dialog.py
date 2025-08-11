
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QFormLayout,
    QPushButton, QCheckBox, QDoubleSpinBox, QMessageBox, QProgressDialog,
    QWidget, QRadioButton, QSpinBox, QApplication
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

    def _build_ui(self):
        # --- Główne Layouty ---
        root_layout = QVBoxLayout(self)
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
        params_widget = QWidget(self)
        params_layout = QVBoxLayout(params_widget)
        
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

        params_layout.addStretch()

        # --- Przyciski ---
        self.btn_process = QPushButton("Process", self)
        
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("OK", self)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_ok.setEnabled(False) # Dostępny dopiero po przetworzeniu
        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_ok)
        
        params_layout.addWidget(self.btn_process)
        
        # --- Składanie UI ---
        root_layout.addWidget(main_splitter, 1)
        root_layout.addLayout(btn_box)
        main_splitter.addWidget(params_widget)
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
        spec = {
            'median_filter': self.cb_median.isChecked(),
            'median_size': self.sp_median_size.value(),
            'destripe': self.cb_destripe.isChecked(),
            'deconv_mode': 'none',
            'rl_iter': self.sp_rl_iter.value(),
            'psf_sigma_x': self.sp_psf_sx.value(),
            'psf_sigma_y': self.sp_psf_sy.value(),
            'denoise_bm3d': self.cb_bm3d.isChecked(),
            'bm3d_sigma_factor': self.sp_bm3d_sigma.value()
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