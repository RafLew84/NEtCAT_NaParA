from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QDoubleSpinBox, QPushButton

class ProcessingPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        grp_filters = QGroupBox("Filters / Preprocessing", self)
        form = QFormLayout(grp_filters)

        self.cb_gauss = QCheckBox("Gaussian blur", grp_filters)
        self.sp_sigma = QDoubleSpinBox(grp_filters); self.sp_sigma.setRange(0.0, 50.0); self.sp_sigma.setValue(1.0)
        form.addRow(self.cb_gauss, self.sp_sigma)

        self.cb_median = QCheckBox("Median filter", grp_filters)
        self.sp_med = QDoubleSpinBox(grp_filters); self.sp_med.setRange(1.0, 99.0); self.sp_med.setValue(3.0)
        form.addRow(self.cb_median, self.sp_med)

        self.cb_tophat = QCheckBox("White top-hat", grp_filters)
        self.sp_tophat = QDoubleSpinBox(grp_filters); self.sp_tophat.setRange(1.0, 99.0); self.sp_tophat.setValue(5.0)
        form.addRow(self.cb_tophat, self.sp_tophat)

        layout.addWidget(grp_filters)

        self.btn_detect = QPushButton("Detect", self)
        layout.addWidget(self.btn_detect)

        layout.addStretch(1)
