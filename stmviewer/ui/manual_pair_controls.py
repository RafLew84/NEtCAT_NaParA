"""Manual alignment actions arranged below the pair preview."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QHBoxLayout(self)
        starts = QVBoxLayout()
        moves = QVBoxLayout()
        finish = QVBoxLayout()
        for column in (starts, moves, finish):
            column.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addLayout(column, 1)

        self.zero = QPushButton('Ustaw ręcznie od zera', self)
        self.zero.setObjectName('manualPairZero')
        self.zero.clicked.connect(self.start_zero.emit)
        starts.addWidget(self.zero)
        self.correct = QPushButton('Popraw wybrany wynik ręcznie', self)
        self.correct.setObjectName('manualPairCorrect')
        self.correct.clicked.connect(self.start_copy.emit)
        starts.addWidget(self.correct)
        help_text = QLabel(_STEP_HELP, self)
        help_text.setWordWrap(True)
        starts.addWidget(help_text)

        self.info = QLabel('Brak rozpoczętej korekty.', self)
        self.info.setObjectName('manualPairInfo')
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        moves.addWidget(self.info)
        steps_layout = QGridLayout()
        self.steps: list[QPushButton] = []
        for title, suffix, dx, dy in [('← X −1', 'XMinus', -1, 0), ('X +1 →', 'XPlus', 1, 0),
                                      ('↑ Y −1', 'YMinus', 0, -1), ('Y +1 ↓', 'YPlus', 0, 1)]:
            control = QPushButton(title, self)
            control.setObjectName(f'manualPair{suffix}')
            control.clicked.connect(lambda checked=False, x=dx, y=dy: self.nudged.emit(x, y))
            steps_layout.addWidget(control, len(self.steps) // 2, len(self.steps) % 2)
            self.steps.append(control)
        moves.addLayout(steps_layout)

        self.apply = QPushButton('Zakończ korektę', self)
        self.apply.setObjectName('manualPairApply')
        self.apply.clicked.connect(self.applied.emit)
        finish.addWidget(self.apply)
        scope = QLabel('Ustawia wynik bieżący do porównania. Film pozostaje bez zmian.', self)
        scope.setObjectName('manualPairScope')
        scope.setWordWrap(True)
        scope.setMinimumHeight(scope.fontMetrics().lineSpacing() * 3)
        finish.addWidget(scope)
        self.reset = QPushButton('Cofnij wszystkie ruchy', self)
        self.reset.setObjectName('manualPairReset')
        self.reset.setToolTip('Przywraca przesunięcie z początku tej korekty, także gdy nie było zerowe.')
        self.reset.clicked.connect(self.reset_requested.emit)
        finish.addWidget(self.reset)
        self.discard = QPushButton('Anuluj korektę', self)
        self.discard.setObjectName('manualPairDiscard')
        self.discard.clicked.connect(self.discarded.emit)
        finish.addWidget(self.discard)

    def show_draft(self, draft: ManualPairDraft | None) -> None:
        self.setTitle('Ręczna korekta w toku' if draft is not None else 'Dopasowanie ręczne')
        if draft is None:
            self.info.setText('Brak rozpoczętej korekty.')
            return
        x, y = draft.shift_xy
        sx, sy = draft.start_xy
        dx, dy = draft.correction_xy
        self.info.setText(f'ΔX: {x:g} px · ΔY: {y:g} px\n'
                         f'Początek: ({sx:g}, {sy:g}) px\n'
                         f'Twoje ruchy: ({dx:+d}, {dy:+d}) px')

    def sync(self, *, available: bool, editing: bool, can_copy: bool) -> None:
        self.zero.setEnabled(available and not editing)
        self.correct.setEnabled(available and not editing and can_copy)
        for control in [*self.steps, self.apply, self.reset, self.discard]:
            control.setEnabled(available and editing)
