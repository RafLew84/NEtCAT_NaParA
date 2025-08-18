from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, 
                             QDoubleSpinBox, QPushButton, QSpinBox, QComboBox)

class ProcessingPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        grp_filters = QGroupBox("Filters / Preprocessing", self)
        form = QFormLayout(grp_filters)

        # Gaussian
        self.cb_gauss = QCheckBox("Gaussian blur", grp_filters); self.cb_gauss.setChecked(False)
        self.sp_sigma = QDoubleSpinBox(grp_filters); self.sp_sigma.setRange(0.0, 50.0); self.sp_sigma.setValue(1.0)
        form.addRow(self.cb_gauss, self.sp_sigma)

        # Median
        self.cb_median = QCheckBox("Median filter", grp_filters); self.cb_median.setChecked(False)
        self.sp_med = QSpinBox(grp_filters); self.sp_med.setRange(1, 99); self.sp_med.setSingleStep(2); self.sp_med.setValue(3)
        form.addRow(self.cb_median, self.sp_med)

        # White Top-Hat
        self.cb_tophat = QCheckBox("White top-hat", grp_filters); self.cb_tophat.setChecked(False)
        self.sp_tophat = QSpinBox(grp_filters); self.sp_tophat.setRange(1, 99); self.sp_tophat.setValue(5)
        form.addRow(self.cb_tophat, self.sp_tophat)

        self.cb_thresh = QCheckBox("Threshold (Otsu/Sauvola)", grp_filters); self.cb_thresh.setChecked(False)
        self.sp_min_area = QSpinBox(grp_filters); self.sp_min_area.setRange(0, 100000); self.sp_min_area.setValue(20)
        form.addRow(self.cb_thresh, self.sp_min_area)

        self.sp_otsu_bias = QDoubleSpinBox(grp_filters)
        self.sp_otsu_bias.setRange(-0.5, 0.5); self.sp_otsu_bias.setSingleStep(0.01); self.sp_otsu_bias.setValue(0.0)
        form.addRow("Bias:", self.sp_otsu_bias)

        self.cmb_thresh_mode = QComboBox(grp_filters)
        self.cmb_thresh_mode.addItems(["Otsu", "Sauvola"])
        form.addRow("Mode:", self.cmb_thresh_mode)

        self.sp_sauvola_win = QSpinBox(grp_filters); self.sp_sauvola_win.setRange(7, 999); self.sp_sauvola_win.setSingleStep(2); self.sp_sauvola_win.setValue(21)
        self.sp_sauvola_k = QDoubleSpinBox(grp_filters); self.sp_sauvola_k.setRange(-1.0, 1.0); self.sp_sauvola_k.setSingleStep(0.05); self.sp_sauvola_k.setValue(0.2)
        form.addRow("Sauvola window:", self.sp_sauvola_win)
        form.addRow("Sauvola k:", self.sp_sauvola_k)

        def _update_thresh_mode():
            is_sau = self.cmb_thresh_mode.currentIndex() == 1
            self.sp_sauvola_win.setEnabled(is_sau)
            self.sp_sauvola_k.setEnabled(is_sau)
        self.cmb_thresh_mode.currentIndexChanged.connect(lambda _: _update_thresh_mode())
        _update_thresh_mode()

        # Kontury/obiekty – globalny przełącznik detekcji w ROI
        self.cb_detect = QCheckBox("Detect contours/objects", grp_filters); self.cb_detect.setChecked(False)
        form.addRow(self.cb_detect)

        layout.addWidget(grp_filters)

        self.btn_detect = QPushButton("Detect", self)
        layout.addWidget(self.btn_detect)

        layout.addStretch(1)