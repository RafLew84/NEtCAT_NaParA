"""Original AVI options and a live summary, before any file is written."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QWidget

from stmviewer.avi_export import AviPlan, prepare_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.frame import ImageFrame


class AviDialog(QDialog):
    def __init__(self, frames: tuple[ImageFrame, ...], presentation: MoviePresentation,
                 fps: int, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName('aviOptions')
        self.setWindowTitle('Zapisz AVI — original')
        self.setMinimumWidth(440)
        self._frames = frames
        self._presentation = presentation
        self.plan: AviPlan | None = None
        layout = QFormLayout(self)
        self._range = QComboBox(self)
        self._range.setObjectName('aviRange')
        self._range.addItems(['Cała seria', 'Zakres od–do'])
        layout.addRow('Klatki', self._range)
        self._start = QSpinBox(self)
        self._start.setObjectName('aviStart')
        self._start.setRange(1, len(frames))
        layout.addRow('Od (włącznie)', self._start)
        self._end = QSpinBox(self)
        self._end.setObjectName('aviEnd')
        self._end.setRange(1, len(frames))
        self._end.setValue(len(frames))
        layout.addRow('Do (włącznie)', self._end)
        self._fps = QSpinBox(self)
        self._fps.setObjectName('aviFps')
        self._fps.setRange(1, 30)
        self._fps.setValue(fps)
        layout.addRow('Tempo filmu (kl./s)', self._fps)
        self._codec = QComboBox(self)
        self._codec.setObjectName('aviCodec')
        self._codec.addItems(['MJPG', 'FFV1'])
        self._codec.setToolTip('MJPG: kompresja stratna. FFV1: dokładne piksele wyrenderowanego filmu.')
        layout.addRow('Kodek', self._codec)
        note = QLabel(f'Pełne obrazy original · gamma {presentation.gamma:g}\n'
                      'Kontrast osobno dla klatki · czarne tło braków · bez opisów', self)
        note.setWordWrap(True)
        layout.addRow(note)
        self._summary = QLabel(self)
        self._summary.setObjectName('aviSummary')
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        self._summary.setWordWrap(True)
        layout.addRow(self._summary)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                        QDialogButtonBox.StandardButton.Cancel, self)
        self._save = self._buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert self._save is not None and cancel is not None
        self._save.setText('Zapisz…')
        cancel.setText('Anuluj')
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)
        for spin in (self._start, self._end, self._fps):
            spin.valueChanged.connect(self._update_summary)
        self._range.currentIndexChanged.connect(self._update_summary)
        self._codec.currentIndexChanged.connect(self._update_summary)
        self._update_summary()

    def _update_summary(self) -> None:
        subset = self._range.currentIndex() == 1
        self._start.setEnabled(subset)
        self._end.setEnabled(subset)
        try:
            self.plan = prepare_avi(
                self._frames, start=self._start.value() if subset else 1,
                end=self._end.value() if subset else len(self._frames), fps=self._fps.value(),
                codec='FFV1' if self._codec.currentText() == 'FFV1' else 'MJPG',
                presentation=self._presentation)
            width, height = self.plan.geometry.output_size
            proportions = 'fizyczne' if self.plan.geometry.physical else 'pikselowe'
            self._summary.setText(f'{self.plan.frame_count} kl. · {width} × {height} px · '
                                  f'{self.plan.duration_s:.3f} s\nProporcje {proportions}')
        except (ValueError, OverflowError) as error:
            self.plan = None
            self._summary.setText(str(error))
        assert self._save is not None
        self._save.setEnabled(self.plan is not None)
