"""Session mask ownership and a single editor shared by movie and pair views."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from stmviewer.frame import ImageFrame
from stmviewer.registration_masks import FrameMask, FrameMasks
from stmviewer.ui.mask_editor import MaskEditorDialog


class RegistrationMaskControls(QGroupBox):
    changed = pyqtSignal()
    edit_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__('Maski do rejestracji', parent)
        self.store = FrameMasks()
        self._frames: tuple[ImageFrame, ...] = ()
        self._editor: MaskEditorDialog | None = None
        self._available = True
        self._method = ''
        layout = QVBoxLayout(self)
        self.edit_button = QPushButton('Edytuj maski…', self)
        self.edit_button.setObjectName('editRegistrationMasks')
        self.edit_button.clicked.connect(self.edit_requested.emit)
        layout.addWidget(self.edit_button)
        self.use = QCheckBox('Uwzględnij oznaczenia klatek', self)
        self.use.setObjectName('registrationUseMasks')
        self.use.setChecked(True)
        layout.addWidget(self.use)
        self.info = QLabel(self)
        self.info.setObjectName('registrationMasksInfo')
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.info)
        self._sync()

    def set_frames(self, frames: tuple[ImageFrame, ...], *, reset: bool = False) -> None:
        self.close_editor()
        if reset:
            self.store.clear()
        else:
            for old in self._frames:
                if not any(old is current for current in frames):
                    self.store.remove(old)
        self._frames = frames
        self._changed()

    def snapshot(self) -> tuple[FrameMask, ...]:
        return self.store.snapshot(self._frames)

    def set_method(self, method: str) -> None:
        self._method = method
        self._sync()

    def set_available(self, available: bool) -> None:
        self._available = available
        if self._editor is not None:
            self._editor.set_available(available)
        self._sync()

    def edit(self, index: int) -> None:
        if not self._available or not self._frames:
            return
        if self._editor is None:
            self._editor = MaskEditorDialog(self._frames, self.store, self, index=index)
            self._editor.changed.connect(self._changed)
            self._editor.finished.connect(self._editor_closed)
        else:
            self._editor.select_frame(index)
        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()

    def close_editor(self) -> None:
        if self._editor is not None:
            self._editor.close()

    def _editor_closed(self) -> None:
        self._editor = None

    def _changed(self) -> None:
        self._sync()
        self.changed.emit()

    def _sync(self) -> None:
        self.edit_button.setEnabled(self._available and bool(self._frames))
        self.use.setVisible(self._method == 'masked_correlation')
        self.use.setEnabled(self._available and bool(self._frames))
        text = f'Oznaczone klatki: {self.store.marked_count} / {len(self._frames)}.'
        if self._method != 'masked_correlation':
            text += '\nMaski uwzględnia metoda „Korelacja z maskami”.'
        self.info.setText(text)
