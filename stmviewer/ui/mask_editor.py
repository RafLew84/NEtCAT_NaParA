"""Session-only rectangle selections on original frames, independent of aligned."""

from dataclasses import replace

import numpy as np
from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from stmviewer.frame import ImageFrame
from stmviewer.registration_masks import FrameMask, FrameMasks, MaskRectangle
from stmviewer.ui.mask_preview import MaskPreview


class MaskEditorDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, frames: tuple[ImageFrame, ...], masks: FrameMasks, parent: QWidget | None,
                 *, index: int = 0) -> None:
        super().__init__(parent)
        if not frames or not 0 <= index < len(frames):
            raise ValueError('Edytor masek wymaga dostępnej klatki.')
        self.setObjectName('maskEditor')
        self.setWindowTitle('Maski rejestracji — oryginalne klatki')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1100, 760)
        self._frames, self._masks = frames, masks
        self._available = True
        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        self._source = QLabel(self)
        self._source.setObjectName('maskSource')
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setWordWrap(True)
        self._source.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self._source, 1)
        header.addWidget(QLabel('Klatka:', self))
        self._number = QSpinBox(self)
        self._number.setObjectName('maskFrameNumber')
        self._number.setRange(1, len(frames))
        self._number.setValue(index + 1)
        header.addWidget(self._number)
        outer.addLayout(header)
        body = QHBoxLayout()
        view = QVBoxLayout()
        self._preview = MaskPreview(self)
        self._preview.rectangle_created.connect(self._add_rectangle)
        view.addWidget(self._preview, 1)
        navigation = QHBoxLayout()
        for text, name, callback in (('−', 'maskZoomOut', self._preview.zoom_out),
                                      ('+', 'maskZoomIn', self._preview.zoom_in),
                                      ('Pokaż cały obraz', 'maskFit', self._preview.fit_image)):
            button = QPushButton(text, self)
            button.setObjectName(name)
            if name != 'maskFit':
                button.setFixedWidth(32)
            button.clicked.connect(callback)
            navigation.addWidget(button)
        navigation.addStretch()
        navigation.addWidget(QLabel('Gamma', self))
        gamma = QDoubleSpinBox(self)
        gamma.setObjectName('maskGamma')
        gamma.setRange(.1, 4)
        gamma.setSingleStep(.1)
        gamma.setValue(1)
        gamma.valueChanged.connect(self._preview.set_gamma)
        navigation.addWidget(gamma)
        pixels = QCheckBox('Proporcje pikselowe', self)
        pixels.setObjectName('maskPixelProportions')
        pixels.setChecked(True)
        self._preview.set_pixel_proportions(True)
        pixels.toggled.connect(self._preview.set_pixel_proportions)
        navigation.addWidget(pixels)
        view.addLayout(navigation)
        body.addLayout(view, 1)
        panel = QWidget(self)
        panel.setFixedWidth(280)
        controls = QVBoxLayout(panel)
        controls.addWidget(QLabel('Działanie myszy', self))
        self._mode = QComboBox(self)
        self._mode.setObjectName('maskEditMode')
        for label, mode in [('Przesuwaj', 'pan'), ('Dodaj: użyj', 'use'), ('Dodaj: pomiń', 'omit')]:
            self._mode.addItem(label, mode)
        self._mode.currentIndexChanged.connect(lambda: self._preview.set_mode(self._mode.currentData()))
        controls.addWidget(self._mode)
        overlay = QCheckBox('Pokaż maskę', self)
        overlay.setObjectName('showMaskOverlay')
        overlay.setChecked(True)
        overlay.toggled.connect(self._preview.set_overlay_visible)
        controls.addWidget(overlay)
        legend = QLabel('Zielone: używane próbki. Czerwone: pomijane.\n'
                        'Bez prostokątów „użyj” podstawą jest cały dostępny obraz. '
                        '„Pomiń” odejmuje wskazane obszary.', self)
        legend.setWordWrap(True)
        controls.addWidget(legend)
        self._summary = QLabel(self)
        self._summary.setObjectName('maskSummary')
        self._summary.setWordWrap(True)
        controls.addWidget(self._summary)
        self._list = QListWidget(self)
        self._list.setObjectName('maskRectangles')
        self._list.currentRowChanged.connect(self._select_rectangle)
        controls.addWidget(self._list, 1)
        self._remove = QPushButton('Usuń wybrany prostokąt', self)
        self._remove.setObjectName('removeMaskRectangle')
        self._remove.clicked.connect(self._remove_rectangle)
        controls.addWidget(self._remove)
        self._clear = QPushButton('Wyczyść maskę tej klatki', self)
        self._clear.setObjectName('clearFrameMask')
        self._clear.clicked.connect(self._clear_mask)
        controls.addWidget(self._clear)
        body.addWidget(panel)
        outer.addLayout(body, 1)
        self._note = QLabel('Oznaczenia są zachowywane w tej sesji programu. Korzysta z nich metoda '
                            '„Korelacja z maskami”. Obrazy original, gotowy aligned i eksport pozostają bez zmian.', self)
        self._note.setObjectName('maskScope')
        self._note.setWordWrap(True)
        outer.addWidget(self._note)
        self._number.valueChanged.connect(self._show_frame)
        self._show_frame()

    def select_frame(self, index: int) -> None:
        if not 0 <= index < len(self._frames):
            raise IndexError(index)
        self._number.setValue(index + 1)

    def set_available(self, available: bool) -> None:
        self._available = available
        self._mode.setEnabled(available)
        self._preview.set_editing_enabled(available)
        self._sync_buttons()

    def _frame(self) -> ImageFrame:
        return self._frames[self._number.value() - 1]

    def _show_frame(self) -> None:
        frame = self._frame()
        suffix = f' · MPP {frame.source_frame_index + 1}' if frame.source_frame_index is not None else ''
        self._source.setText(f'Original: {frame.source.name}{suffix}\n'
                             f'{frame.data.shape[1]} × {frame.data.shape[0]} px — oznaczenia w pikselach źródła')
        self._preview.set_original(frame, self._masks.get(frame))
        self._refresh_mask()

    def _refresh_mask(self, selected: int = -1) -> None:
        frame, mask = self._frame(), self._masks.get(self._frame())
        with QSignalBlocker(self._list):
            self._list.clear()
            for index, rectangle in enumerate(mask.rectangles, 1):
                kind = 'użyj' if rectangle.kind == 'use' else 'pomiń'
                self._list.addItem(f'{index}. {kind}: [{rectangle.x0}, {rectangle.x1}) × '
                                   f'[{rectangle.y0}, {rectangle.y1}) px')
            self._list.setCurrentRow(selected)
        self._preview.set_definition(mask)
        self._preview.set_selected(selected)
        count = int(np.count_nonzero(mask.raster(frame.data)))
        self._summary.setText(f'Używane próbki: {count} / {frame.data.size}\n'
                              f'Prostokąty tej klatki: {len(mask.rectangles)}')
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self._remove.setEnabled(self._available and self._list.currentRow() >= 0)
        self._clear.setEnabled(self._available and self._list.count() > 0)

    def _select_rectangle(self, index: int) -> None:
        self._preview.set_selected(index)
        self._sync_buttons()

    def _add_rectangle(self, rectangle: MaskRectangle) -> None:
        if not self._available:
            return
        frame = self._frame()
        mask = self._masks.get(frame)
        self._masks.set(frame, replace(mask, rectangles=(*mask.rectangles, rectangle)))
        self._refresh_mask(len(mask.rectangles))
        self.changed.emit()

    def _remove_rectangle(self) -> None:
        if not self._remove.isEnabled():
            return
        index, frame = self._list.currentRow(), self._frame()
        mask = self._masks.get(frame)
        rectangles = mask.rectangles[:index] + mask.rectangles[index + 1:]
        self._masks.set(frame, replace(mask, rectangles=rectangles))
        self._refresh_mask(min(index, len(rectangles) - 1))
        self.changed.emit()

    def _clear_mask(self) -> None:
        if self._clear.isEnabled():
            self._masks.set(self._frame(), FrameMask())
            self._refresh_mask()
            self.changed.emit()
