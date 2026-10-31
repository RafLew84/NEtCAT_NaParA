"""Controls for editing one original-pixel translation in the pair view."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


from stmviewer.manual_pair import ManualPairDraft

_STEP_HELP = 'Krok: 1 px oryginału · +X w prawo, +Y w dół.'


class ManualPairControls(QGroupBox):
    start_zero = pyqtSignal()
    nudged = pyqtSignal(int, int)
    applied = pyqtSignal()
    start_copy = pyqtSignal()
    reset_requested = pyqtSignal()
    discarded = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__('Dopasowanie ręczne', parent)
        layout = QVBoxLayout(self)
        self.zero = QPushButton('Zacznij od zera', self)
        self.zero.setObjectName('manualPairZero')
        self.zero.clicked.connect(self.start_zero.emit)
        layout.addWidget(self.zero)
        self.correct = QPushButton('Koryguj wybraną próbę', self)
        self.correct.setObjectName('manualPairCorrect')
        self.correct.clicked.connect(self.start_copy.emit)
        layout.addWidget(self.correct)
        self.info = QLabel(_STEP_HELP, self)
        self.info.setObjectName('manualPairInfo')
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        steps_layout = QGridLayout()
        self.steps: list[QPushButton] = []
        for title, suffix, dx, dy in [('X−', 'XMinus', -1, 0), ('X+', 'XPlus', 1, 0),
                                      ('Y−', 'YMinus', 0, -1), ('Y+', 'YPlus', 0, 1)]:
            control = QPushButton(title, self)
            control.setObjectName(f'manualPair{suffix}')
            control.clicked.connect(lambda checked=False, x=dx, y=dy: self.nudged.emit(x, y))
            steps_layout.addWidget(control, len(self.steps) // 2, len(self.steps) % 2)
            self.steps.append(control)
        layout.addLayout(steps_layout)
        self.apply = QPushButton('Zastosuj jako B', self)
        self.apply.setObjectName('manualPairApply')
        self.apply.clicked.connect(self.applied.emit)
        layout.addWidget(self.apply)
        row = QHBoxLayout()
        self.reset = QPushButton('Przywróć początek', self)
        self.reset.setObjectName('manualPairReset')
        self.reset.clicked.connect(self.reset_requested.emit)
        row.addWidget(self.reset)
        self.discard = QPushButton('Odrzuć edycję', self)
        self.discard.setObjectName('manualPairDiscard')
        self.discard.clicked.connect(self.discarded.emit)
        row.addWidget(self.discard)
        layout.addLayout(row)

    def show_draft(self, draft: ManualPairDraft | None) -> None:
        if draft is None:
            self.info.setText(_STEP_HELP)
            return
        x, y = draft.shift_xy
        sx, sy = draft.start_xy
        dx, dy = draft.correction_xy
        self.info.setText(f'Szkic: ΔX: {x:g} px · ΔY: {y:g} px\n'
                         f'Start: ({sx:g}, {sy:g}) px; korekta: ({dx:+d}, {dy:+d}) px\n'
                         + _STEP_HELP)

    def sync(self, *, available: bool, editing: bool, can_copy: bool) -> None:
        self.zero.setEnabled(available and not editing)
        self.correct.setEnabled(available and not editing and can_copy)
        for control in [*self.steps, self.apply, self.reset, self.discard]:
            control.setEnabled(available and editing)
