"""Advanced controls describe the existing method and its recalculation boundary."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout, QWidget

from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.descriptor_settings import DescriptorSettings


class ParameterNumber(QDoubleSpinBox):
    """Preserve exact saved fractions when their rounded display wasn't edited."""

    def __init__(self, low: float, high: float, step: float, suffix: str = '') -> None:
        super().__init__()
        self.setDecimals(6)
        self.setRange(low, high)
        self.setSingleStep(step)
        self.setSuffix(suffix)
        self.setKeyboardTracking(False)
        self._loaded = self.value()

    def load_value(self, value: float) -> None:
        self._loaded = value
        self.setValue(value)

    def exact_value(self) -> float:
        return self._loaded if self.value() == round(self._loaded, self.decimals()) else self.value()


def integer(low: int, high: int) -> QSpinBox:
    field = QSpinBox()
    field.setRange(low, high)
    field.setKeyboardTracking(False)
    return field


def note(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class DescriptorFields(QGroupBox):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__('Opis otoczenia i dopasowanie klas')
        self._loading = False
        form = QFormLayout(self)
        self.sigma = ParameterNumber(.25, 3, .05, ' × rozstaw')
        self.radial_bins, self.angle_bins, self.pca = integer(4, 32), integer(8, 72), integer(1, 64)
        self.pair_min = ParameterNumber(.1, 3.9, .05, ' × rozstaw')
        self.pair_max = ParameterNumber(.2, 4, .05, ' × rozstaw')
        for label, control in (('Sigma opisu', self.sigma), ('Przedziały odległości', self.radial_bins),
                               ('Przedziały kąta (0–180°)', self.angle_bins), ('Minimum odległości par', self.pair_min),
                               ('Maksimum odległości par', self.pair_max), ('Maksimum składowych PCA', self.pca)):
            form.addRow(label, control)
            control.valueChanged.connect(self._changed)
        form.addRow(note('Zmiana opisu wymaga nowych cech i dopasowania: wybierz „Dopasuj nowe klasy”. '
                         'Rozstaw jest medianą odległości najbliższych molekuł po usunięciu duplikatów. '
                         'PCA użyje najwyżej wybranej liczby składowych i liczby próbek minus 1; '
                         'jednakowe opisy pozostają bez projekcji. Histogram ma maks. 2048 pól.'))
        self.load(DescriptorSettings())

    def _changed(self) -> None:
        if not self._loading:
            self.changed.emit()

    def settings(self) -> DescriptorSettings:
        return DescriptorSettings(self.radial_bins.value(), self.angle_bins.value(), self.sigma.exact_value(),
                                  (self.pair_min.exact_value(), self.pair_max.exact_value()), self.pca.value())

    def load(self, settings: DescriptorSettings) -> None:
        self._loading = True
        self.sigma.load_value(settings.descriptor_sigma_factor)
        self.radial_bins.setValue(settings.descriptor_radial_bins)
        self.angle_bins.setValue(settings.descriptor_angle_bins)
        self.pca.setValue(settings.pca_max_components)
        self.pair_min.load_value(settings.descriptor_pair_distance_range[0])
        self.pair_max.load_value(settings.descriptor_pair_distance_range[1])
        self._loading = False
        self.changed.emit()


class BarrierFields(QGroupBox):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__('Bariery obrazu')
        self._loading = False
        form = QFormLayout(self)
        self.low, self.high = ParameterNumber(0, 99.9, 1), ParameterNumber(0, 100, 1)
        self.span = ParameterNumber(.1, 100, .1, ' × rozstaw')
        self.gap = ParameterNumber(0, 3, .1, ' × rozstaw')
        self.tilt = ParameterNumber(1, 85, 1, '° od poziomu')
        self.dilation = ParameterNumber(0, 2, .02, ' × rozstaw')
        self.span.setToolTip('Minimalny zasięg fragmentu w osi X; co najmniej 3 piksele.')
        self.gap.setToolTip('Maksymalna długość krótkiego połączenia wspartego gradientem. 0 wyłącza łączenie przerw.')
        self.tilt.setToolTip('Nachylenie wykrywanych fragmentów względem poziomu. Krótkie łączniki wsparte gradientem mogą być bardziej strome.')
        self.dilation.setToolTip('Poszerzenie maski: 0 bez poszerzania, dodatnia wartość co najmniej 1 piksel.')
        for label, control in (('Dolny percentyl gradientu', self.low), ('Górny percentyl gradientu', self.high),
                               ('Minimalna długość fragmentu X', self.span), ('Dopuszczalna przerwa', self.gap),
                               ('Maksymalne nachylenie', self.tilt), ('Poszerzenie maski', self.dilation)):
            form.addRow(label, control)
            control.valueChanged.connect(self._changed)
        form.addRow(note('Detektor szuka prawie poziomych granic, które jaśnieją w dół obrazu oryginalnego '
                         '(rosnący numer wiersza). Percentyle dotyczą siły gradientu na tej klatce. '
                         'To kandydaci barier kontrastu, bez potwierdzenia tarasów fizycznych. '
                         'Nachylenie dotyczy granicy obrazu, nie kąta molekuły. '
                         'Aby zachować model po zmianie barier, wybierz „Użyj istniejących klas” i Analizuj.'))
        self.load(BarrierSettings())

    def _changed(self) -> None:
        if not self._loading:
            self.changed.emit()

    def settings(self) -> BarrierSettings:
        return BarrierSettings(*(field.exact_value() for field in (self.low, self.high, self.span, self.gap, self.tilt, self.dilation)))

    def load(self, settings: BarrierSettings) -> None:
        self._loading = True
        for control, value in zip((self.low, self.high, self.span, self.gap, self.tilt, self.dilation),
                                  (settings.low_percentile, settings.high_percentile, settings.minimum_span_factor,
                                   settings.maximum_gap_factor, settings.maximum_tilt_degrees, settings.dilation_factor)):
            control.load_value(value)
        self._loading = False
        self.changed.emit()


class AdvancedFields(QWidget):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.descriptor, self.barriers = DescriptorFields(), BarrierFields()
        layout.addWidget(self.descriptor)
        layout.addWidget(self.barriers)
        self.show_barriers = QCheckBox('Pokaż bariery wyświetlanego wyniku (pomarańczowe)')
        self.show_barriers.setToolTip('Pokazuje maskę używaną do tworzenia domen. Edycja parametrów nie zmienia jej przed analizą.')
        self.barrier_status = note('Brak obliczonej maski barier.')
        layout.addWidget(self.show_barriers)
        layout.addWidget(self.barrier_status)
        self.descriptor.changed.connect(self.changed)
        self.barriers.changed.connect(self.changed)
