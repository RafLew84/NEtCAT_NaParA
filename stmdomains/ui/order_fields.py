"""Order parameters with exact round trips for values such as the baseline 4/3."""

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QDoubleSpinBox, QFormLayout, QLabel, QSpinBox, QWidget

from stmdomains.analysis.order_settings import OrderSettings


def order_settings_description(settings: OrderSettings) -> str:
    return (f"kwantyl {settings.order_quantile:g}; minimum {settings.order_minimum_local_count} "
            f"/ efektywne {settings.order_minimum_effective_count:g}; "
            f"promień {settings.order_radius_factor:g} × d, sigma {settings.order_sigma_factor:.6g} × d")


class OrderFields(QWidget):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self._loaded = OrderSettings()
        self.quantile = self._spin(.5, .999, 3, .005)
        self.minimum_local = QSpinBox()
        self.minimum_local.setRange(3, 200)
        self.minimum_effective = self._spin(2., 200., 2, 1.)
        self.radius = self._spin(.5, 6., 3, .1)
        self.sigma = self._spin(.25, 4., 6, .1)
        self.quantile.setToolTip("Wyższy kwantyl zwykle zaostrza test. Kontrole są generowane ponownie dla wybranej konfiguracji.")
        self.minimum_local.setToolTip("Liczba centrów w promieniu, łącznie z ocenianą molekułą.")
        self.minimum_effective.setToolTip("Efektywna liczba punktów po ważeniu odległością: (suma wag)² / suma kwadratów wag.")
        self.sigma.setToolTip("Szerokość wag Gaussa. Bazowo dokładnie 4/3 odstępu; pole pokazuje zaokrąglenie.")
        for label, field in (("Kwantyl kontroli", self.quantile), ("Minimum punktów lokalnych", self.minimum_local),
                             ("Minimum punktów efektywnych", self.minimum_effective),
                             ("Promień otoczenia [× d]", self.radius), ("Sigma otoczenia [× d]", self.sigma)):
            form.addRow(label, field)
            field.valueChanged.connect(self.changed)
        note = QLabel("d = odstęp molekuł wyznaczony z klatki. Kwantyl kontroli nie jest pewnością poprawności domeny. "
                      "Metoda dopuszcza rzędy: jeden kierunek periodyczności nie potwierdza sieci 2D.")
        note.setWordWrap(True)
        form.addRow(note)
        self.load(OrderSettings())

    @staticmethod
    def _spin(lower: float, upper: float, decimals: int, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lower, upper)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        return spin

    def _pairs(self) -> tuple:
        return (("order_quantile", self.quantile), ("order_minimum_local_count", self.minimum_local),
                ("order_minimum_effective_count", self.minimum_effective),
                ("order_radius_factor", self.radius), ("order_sigma_factor", self.sigma))

    def settings(self) -> OrderSettings:
        values = {}
        for key, spin in self._pairs():
            loaded = getattr(self._loaded, key)
            decimals = spin.decimals() if isinstance(spin, QDoubleSpinBox) else 0
            values[key] = loaded if spin.value() == round(loaded, decimals) else spin.value()
        return OrderSettings(**values)

    def load(self, settings: OrderSettings) -> None:
        self._loaded = settings
        for key, spin in self._pairs():
            with QSignalBlocker(spin):
                spin.setValue(getattr(settings, key))
        self.changed.emit()
