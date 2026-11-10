"""Class acceptance fields usable before the first analysis."""

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QDoubleSpinBox, QFormLayout, QLabel, QWidget

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings


class AcceptanceFields(QWidget):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0., 1.)
        self.margin.setDecimals(3)
        self.margin.setSingleStep(.005)
        self.margin.setToolTip("Przewaga najlepszej klasy nad drugą; niższy próg dopuszcza większą niejednoznaczność.")
        self.radius = QDoubleSpinBox()
        self.radius.setRange(.05, 10.)
        self.radius.setDecimals(2)
        self.radius.setSingleStep(.05)
        self.radius.setToolTip("Odchylenie od wzorca w przestrzeni cech; większy mnożnik łagodzi próg. To nie odległość w nm.")
        form.addRow("Minimalny margines", self.margin)
        form.addRow("Mnożnik promienia klasy", self.radius)
        self.rule = QLabel()
        self.rule.setWordWrap(True)
        form.addRow(self.rule)
        self.margin.valueChanged.connect(self.changed)
        self.radius.valueChanged.connect(self.changed)
        self.load(ClassAcceptanceSettings())
        self.set_k(5)

    def set_k(self, k: int) -> None:
        self.margin.setEnabled(k != 1)
        self.rule.setText("K1: margines nie dotyczy. Obowiązuje promień i dostępność opisu." if k == 1 else
                          "Akceptacja klasy sprawdza podobieństwo otoczeń, nie pewność domeny. Obowiązuje też porządek i geometria.")

    def settings(self) -> ClassAcceptanceSettings:
        return ClassAcceptanceSettings(self.margin.value(), self.radius.value())

    def load(self, settings: ClassAcceptanceSettings) -> None:
        with QSignalBlocker(self.margin), QSignalBlocker(self.radius):
            self.margin.setValue(settings.class_margin)
            self.radius.setValue(settings.class_radius_multiplier)
        self.changed.emit()
