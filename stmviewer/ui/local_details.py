"""Local support shown as evidence, separate from the image measurements."""

from dataclasses import replace

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHeaderView, QLabel, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from stmviewer.local_consensus import LocalDiagnostics
from stmviewer.pair_comparison import PairTrial
from stmviewer.ui.image_preview import PreviewOverlay

PATCH_COLORS = {'inlier': '#23c26b', 'outlier': '#ff9632', 'unmatched': '#a8a8a8'}
PATCH_LABELS = {'inlier': 'Zgodny', 'outlier': 'Odrzucony', 'unmatched': 'Brak dopasowania'}


def _xy(value: tuple[float, float]) -> str:
    return f'X: {value[0]:.3f} · Y: {value[1]:.3f} px'


def local_details_text(details: LocalDiagnostics) -> str:
    counts = {status: sum(p.status == status for p in details.patches) for status in PATCH_LABELS}
    final = ('Brak wyniku lokalnego — odmowa' if details.final_shift_xy is None
             else f'Wynik lokalny: {_xy(details.final_shift_xy)}')
    return (f'Start Deep: {_xy(details.deep_shift_xy)}\n{final}\n'
            f'Zgodne: {counts["inlier"]} · Odrzucone: {counts["outlier"]} · '
            f'Bez dopasowania: {counts["unmatched"]}\n{details.reason}\n'
            'Poparcie estymatora, bez niezależnej oceny jakości.')


def local_start_trial(trial: PairTrial) -> PairTrial:
    """Use the exact Deep estimate of a completed local attempt, without rerunning it."""
    details = trial.local
    if details is None:
        return trial
    return replace(trial, method='deep_matcher_translation', label='Start Deep tej próby',
                   shift_xy=details.deep_shift_xy, status=details.deep_status,
                   quality_score=details.deep_quality_score, local=None,
                   settings_text='Dokładny start tej samej próby, bez ponownego obliczania. '
                   + trial.settings_text)


def local_overlays(details: LocalDiagnostics, displayed_shift: tuple[float, float]) -> tuple[PreviewOverlay, ...]:
    overlays = []
    for index, patch in enumerate(details.patches, start=1):
        correction = (None if patch.shift_xy is None else
                      (patch.shift_xy[0] - displayed_shift[0], patch.shift_xy[1] - displayed_shift[1]))
        overlays.append(PreviewOverlay(patch.reference_rect, PATCH_COLORS[patch.status], str(index), correction))
    return tuple(overlays)


class LocalDetails(QWidget):
    """Bounded table and controls for one immutable set of local measurements."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._details: LocalDiagnostics | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stage = QComboBox(self)
        self.stage.setObjectName('pairLocalStage')
        self.stage.setAccessibleName('Etap wybranej próby lokalnego dopasowania')
        self.stage.addItems(['Wynik lokalny', 'Start Deep tej próby'])
        self.stage.setToolTip('Dokładny start i wynik tej samej próby, bez ponownego obliczania modelu.')
        self.stage.currentIndexChanged.connect(lambda _: self.changed.emit())
        layout.addWidget(self.stage)
        self.overlay = QCheckBox('Pokaż fragmenty i strzałki', self)
        self.overlay.setObjectName('pairLocalOverlay')
        self.overlay.setChecked(True)
        self.overlay.toggled.connect(lambda _: self.changed.emit())
        layout.addWidget(self.overlay)
        self.summary = QLabel(self)
        self.summary.setObjectName('pairLocalDetails')
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.summary)
        legend = QLabel('Zielony: zgodny · pomarańczowy: odrzucony · szary: brak dopasowania.\n'
                        'Prostokąty: fragmenty klatki bazowej. Strzałki: lokalne XY − '
                        'wyświetlane XY, w pikselach oryginału.\n'
                        'Wybierz wiersz, aby zobaczyć przyczynę.', self)
        legend.setWordWrap(True)
        legend.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._legend = legend
        layout.addWidget(legend)
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName('pairLocalPatches')
        self.table.setHorizontalHeaderLabels(['Nr', 'Stan', 'ΔX', 'ΔY'])
        vertical, horizontal = self.table.verticalHeader(), self.table.horizontalHeader()
        if vertical is not None:
            vertical.hide()
        if horizontal is not None:
            horizontal.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(120)
        self.table.setMaximumHeight(190)
        self.table.currentCellChanged.connect(self._show_patch)
        layout.addWidget(self.table)
        self.patch_info = QLabel(self)
        self.patch_info.setObjectName('pairLocalPatchDetails')
        self.patch_info.setWordWrap(True)
        self.patch_info.setTextFormat(Qt.TextFormat.PlainText)
        self.patch_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.patch_info)

    def set_details(self, details: LocalDiagnostics | None) -> None:
        self.setVisible(details is not None)
        if details is self._details:
            return
        self._details = details
        self.summary.setText(local_details_text(details) if details else '')
        self.patch_info.clear()
        self._resize_labels()
        self.table.setRowCount(len(details.patches) if details else 0)
        if details is None:
            return
        for row, patch in enumerate(details.patches):
            values = [str(row + 1), PATCH_LABELS[patch.status]]
            values += ['—', '—'] if patch.shift_xy is None else [f'{v:.3f}' for v in patch.shift_xy]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(patch.reason)
                self.table.setItem(row, column, item)
        if details.patches:
            self.table.setCurrentCell(0, 0)
            self._show_patch(0)

    def _show_patch(self, row: int, *_: int) -> None:
        if self._details is None or not 0 <= row < len(self._details.patches):
            self.patch_info.clear()
            return
        patch = self._details.patches[row]
        reference = ', '.join(str(v) for v in patch.reference_rect)
        moving = ('brak' if patch.moving_rect is None else
                  ', '.join(f'{v:.2f}' for v in patch.moving_rect))
        score = 'brak' if patch.score is None else f'{patch.score:.3f}'
        margin = 'brak' if patch.peak_margin is None else f'{patch.peak_margin:.3f}'
        contrast = 'brak' if patch.peak_contrast is None else f'{patch.peak_contrast:.3f}'
        self.patch_info.setText(f'Fragment {row + 1}: {patch.reason}\n'
                               f'Bazowy [x, y, szer., wys.]: {reference}\n'
                               f'Przesuwany: {moving}\nNCC: {score}; przewaga maksimum: {margin}.\n'
                               f'Kontrast maksimum: {contrast}.\n'
                               'To miary heurystyczne, nie prawdopodobieństwo poprawności.')

        self._resize_labels()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._resize_labels()

    def _resize_labels(self) -> None:
        # The sidebar scrolls; wrapped evidence must not shrink to clipped lines.
        for label in (self.summary, self._legend, self.patch_info):
            label.setMinimumHeight(max(0, label.heightForWidth(max(1, self.width()))))
