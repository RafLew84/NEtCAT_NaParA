"""Panel A: explicit environment selection and rotation, with no target K."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from stmdomains.analysis.freud_settings import FreudSettings
from stmdomains.ui.domain_fields import DomainSettingsFields


class FreudFields(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        note = QLabel('Porównaj otoczenia · bieżąca klatka · liczba klas wynika z tolerancji.\n'
                      'Klasy to podobne układy sąsiadów, nie rozpoznane typy struktur.')
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        number = DomainSettingsFields._number
        self.tolerance = number(.01, 1., .01, ' × NN')
        self.neighbors = QSpinBox()
        self.neighbors.setRange(3, 8)
        self.radius = number(.5, 10., .1, ' × NN')
        self.rotation = QCheckBox('Dopasuj obrót lub odbicie otoczeń (wolniej)')
        self.tolerance.setToolTip('Maksymalna różnica dopasowanych wektorów. Wspólna skala NN klatki; nie prawdopodobieństwo. Klasy mogą łączyć się przez pośrednie podobieństwa.')
        self.neighbors.setToolTip('Najbliższe n centrów w zadanym zasięgu. Brak n punktów, ucięcie pola lub remis na granicy wyboru oznacza odmowę.')
        self.rotation.setToolTip('Wyłączone: orientacja wpływa na klasę. Włączone: dopasowanie 3D freud dopuszcza też odbicia lustrzane płaskich otoczeń. Domeny nadal wymagają zgodnych kierunków z pomiaru geometrii.')
        for title, widget in (('Tolerancja otoczenia', self.tolerance), ('Liczba sąsiadów', self.neighbors),
                               ('Maksymalny zasięg', self.radius)):
            form.addRow(title, widget)
            widget.valueChanged.connect(self.changed)
        form.addRow(self.rotation)
        self.rotation.toggled.connect(self.changed)
        layout.addLayout(form)
        description = QLabel('NN = mediana najbliższego sąsiada w klatce, z kalibracją X/Y.\n'
            'Bez łączenia przeciwległych brzegów obrazu. Niepełne otoczenia pozostają szare.\n\n'
            'Domeny: ta sama klasa + spójność przestrzenna + zgodna geometria. '
            'Progi domen: zakładka Geometria; bariery: Zaawansowane. '
            'Klasy mogą obejmować kilka osobnych domen.\n\n'
            'Widok Klasy pokazuje wszystkie porównane otoczenia; widok Domeny — końcowe przypisania. '
            'Kliknij molekułę, aby zobaczyć jej sąsiadów i powód odmowy.\n\n'
            'Próba: do 1000 aktywnych molekuł, limit porównania 90 s. '
            'Anulowanie zachowuje wcześniejszy wynik. Zgodność fazy sieci nie jest sprawdzana.')
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addStretch(1)
        self.load(FreudSettings())

    def settings(self) -> FreudSettings:
        return FreudSettings(self.tolerance.value(), self.neighbors.value(), self.radius.value(), self.rotation.isChecked())

    def load(self, settings: FreudSettings) -> None:
        self.tolerance.setValue(settings.tolerance)
        self.neighbors.setValue(settings.neighbor_count)
        self.radius.setValue(settings.radius_factor)
        self.rotation.setChecked(settings.registration)
