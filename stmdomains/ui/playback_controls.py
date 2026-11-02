"""Small, explicit controls for playback tempo and preview-only gamma."""

from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QWidget


class PlaybackControls(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.play = QPushButton("▶ Odtwórz")
        self.restart = QPushButton("↤ Od początku")
        row.addWidget(self.play)
        row.addWidget(self.restart)
        row.addWidget(QLabel("Maks. tempo:"))
        self.rate = QComboBox()
        for rate in (1, 2, 5, 10, 20):
            self.rate.addItem(f"{rate} kl./s", rate)
        self.rate.setCurrentIndex(2)
        self.rate.setToolTip("Tempo przeglądania, nie czas pomiaru. Wolne przygotowanie spowalnia odtwarzanie.")
        row.addWidget(self.rate)
        row.addStretch()
        row.addWidget(QLabel("Gamma:"))
        self.gamma = QDoubleSpinBox()
        self.gamma.setObjectName("gamma")
        self.gamma.setRange(0.2, 5.0)
        self.gamma.setSingleStep(0.1)
        self.gamma.setDecimals(2)
        self.gamma.setValue(1.0)
        self.gamma.setKeyboardTracking(False)
        self.gamma.setToolTip("Większa gamma rozjaśnia podgląd. Miniatury zawsze mają gamma 1.")
        row.addWidget(self.gamma)
        self.reset_gamma = QPushButton("Gamma 1")
        self.reset_gamma.clicked.connect(lambda: self.gamma.setValue(1.0))
        row.addWidget(self.reset_gamma)
        for control in (self.play, self.restart, self.rate, self.gamma, self.reset_gamma):
            control.setEnabled(False)
