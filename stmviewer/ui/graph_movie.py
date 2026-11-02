"""Lazy candidate playback with one viewport shared by graph and baseline."""
from PyQt6.QtCore import QSignalBlocker, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from stmviewer.frame import ImageFrame
from stmviewer.graph_preview import GraphMoviePreview, XY
from stmviewer.graph_types import GraphTrial
from stmviewer.graph_methods import graph_method_label
from stmviewer.registration import RegistrationResult
from stmviewer.session_state import ViewTransform
from stmviewer.ui.image_preview import ImagePreview


class GraphMovieWidget(QWidget):
    variant_changed = pyqtSignal(str)

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QWidget) -> None:
        super().__init__(parent)
        self._frames = frames
        self._renderer: GraphMoviePreview | None = None
        self._render_failed = False
        self._aspect = 1.0
        self._trial: GraphTrial | None = None
        self._variants: dict[str, tuple[XY, ...]] = {}
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._advance)
        layout = QVBoxLayout(self)
        self._variant = QComboBox(self)
        self._variant.setObjectName('graphVariant')
        self._variant.setAccessibleName('Wariant filmu do porównania')
        layout.addWidget(self._variant)
        self._source = QLabel(self)
        self._source.setObjectName('graphFrameSource')
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setWordWrap(True)
        self._source.setMinimumHeight(4 * self._source.fontMetrics().lineSpacing())
        layout.addWidget(self._source)
        self._preview = ImagePreview(self)
        self._preview.setObjectName('graphPreview')
        layout.addWidget(self._preview, 1)
        navigation = QHBoxLayout()
        self._previous = QPushButton('Poprzednia', self)
        self._previous.setObjectName('graphPrevious')
        self._previous.clicked.connect(lambda: self._number.setValue(self._number.value() - 1))
        navigation.addWidget(self._previous)
        self._play = QPushButton('Play', self)
        self._play.setObjectName('graphPlay')
        self._play.clicked.connect(self._toggle_play)
        navigation.addWidget(self._play)
        self._next = QPushButton('Następna', self)
        self._next.setObjectName('graphNext')
        self._next.clicked.connect(lambda: self._number.setValue(self._number.value() + 1))
        navigation.addWidget(self._next)
        self._number = QSpinBox(self)
        self._number.setObjectName('graphFrame')
        self._number.setRange(1, len(frames))
        self._number.setSuffix(f' / {len(frames)}')
        self._number.valueChanged.connect(self._selected_frame)
        navigation.addWidget(self._number)
        self._fps = QSpinBox(self)
        self._fps.setObjectName('graphFps')
        self._fps.setRange(1, 30)
        self._fps.setValue(5)
        self._fps.setSuffix(' kl./s')
        self._fps.valueChanged.connect(self._set_interval)
        navigation.addWidget(self._fps)
        self._loop = QCheckBox('Pętla', self)
        self._loop.setObjectName('graphLoop')
        navigation.addWidget(self._loop)
        layout.addLayout(navigation)
        view = QHBoxLayout()
        for label, name, slot in (('−', 'graphZoomOut', self._preview.zoom_out),
                                  ('+', 'graphZoomIn', self._preview.zoom_in),
                                  ('Dopasuj', 'graphFit', self._preview.fit_image)):
            button = QPushButton(label, self)
            button.setObjectName(name)
            button.clicked.connect(slot)
            view.addWidget(button)
        view.addWidget(QLabel('Gamma', self))
        self._gamma = QDoubleSpinBox(self)
        self._gamma.setObjectName('graphGamma')
        self._gamma.setRange(.1, 4)
        self._gamma.setSingleStep(.1)
        self._gamma.setValue(1)
        self._gamma.valueChanged.connect(self._render)
        view.addWidget(self._gamma)
        self._pixels = QCheckBox('Proporcje pikselowe', self)
        self._pixels.setObjectName('graphPixels')
        self._pixels.toggled.connect(self._render)
        view.addWidget(self._pixels)
        layout.addLayout(view)
        self._status = QLabel(self)
        self._status.setObjectName('graphMovieStatus')
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._status)
        self._variant.currentIndexChanged.connect(self._selected_variant)
        self._set_interval()
        self._sync()

    def set_graph(self, trial: GraphTrial | None, registration: RegistrationResult | None) -> None:
        self.pause()
        same_graph = trial is not None and self._trial is not None and trial.revision == self._trial.revision
        previous_renderer, previous_aspect = self._renderer, self._aspect
        self._trial = trial
        selected = self._variant.currentData()
        variants: dict[str, tuple[XY, ...]] = {}
        choices: list[tuple[str, str]] = []
        if trial is not None and trial.positions is not None:
            variants['graph'] = trial.positions
            choices.append((f'Kandydat grafu — {graph_method_label(trial.config.method)} · LS', 'graph'))
        if trial is not None and trial.chain_positions is not None:
            variants['chain'] = trial.chain_positions
            choices.append((f'Łańcuch — {graph_method_label(trial.config.method)} · suma sąsiednich pomiarów', 'chain'))
        if registration is not None and len(registration.frames) == len(self._frames):
            # An active result may retain an anchor belonging to an already deleted
            # frame. A constant change of origin makes the comparison meaningful.
            x0, y0 = registration.frames[0].shift_xy
            variants['active'] = tuple((f.shift_xy[0] - x0, f.shift_xy[1] - y0)
                                       for f in registration.frames)
            choices.append((f'Aktywny aligned — {registration.method} · {registration.revision[:8]} '
                            f'· korekty: {len(registration.corrections)}', 'active'))
            previous = registration.predecessor
            if previous is not None and len(previous.final_positions) == len(self._frames):
                x0, y0 = previous.final_positions[0]
                variants['predecessor'] = tuple((x - x0, y - y0) for x, y in previous.final_positions)
                choices.append((f'Zachowany wynik — {previous.method} · {previous.revision[:8]} '
                                f'· korekty: {len(previous.corrections)}', 'predecessor'))
        if trial is not None:
            for index, robust in enumerate(trial.robust_trials):
                if robust.positions is not None:
                    key = f'huber:{robust.revision}'
                    variants[key] = robust.positions
                    choices.append((f'Huber {index + 1} — {graph_method_label(trial.config.method)} · próg {robust.config.threshold_px:g} px', key))
        self._variants = variants
        with QSignalBlocker(self._variant):
            self._variant.clear()
            for label, key in choices:
                self._variant.addItem(label, key)
            selected_index = self._variant.findData(selected)
            if selected_index >= 0:
                self._variant.setCurrentIndex(selected_index)
        self._renderer = None
        self._render_failed = False
        if variants:
            try:
                self._renderer = GraphMoviePreview(self._frames, variants)
            except (ValueError, MemoryError, OverflowError) as error:
                self._status.setText(f'Nie można przygotować podglądu: {error}')
        else:
            self._status.setText('Brak pełnych XY do podglądu. Obejrzyj relacje i komponenty grafu.')
        if self._renderer is None:
            self._preview.clear_frame()
        else:
            self._render()
            if same_graph and previous_renderer is not None and not self._render_failed:
                self._preserve_geometry(previous_renderer, previous_aspect)
            elif not same_graph:
                self._preview.fit_image()
        self._sync()

    def _preserve_geometry(self, previous: GraphMoviePreview, previous_aspect: float) -> None:
        """Keep the first-frame origin and source-pixel scale as the canvas grows."""
        current = self._renderer
        if current is None or (current.canvas_shape == previous.canvas_shape
                               and current.origin_xy == previous.origin_xy):
            return
        states = self._preview.navigation_states()
        state = states['original']
        width, height = self._preview.width(), self._preview.height()
        old_h, old_w = previous.canvas_shape
        new_h, new_w = current.canvas_shape
        fitted = min(width, height * previous_aspect)
        scale_x = fitted * state.zoom / old_w
        scale_y = fitted * state.zoom / previous_aspect / old_h
        old_x, old_y = previous.origin_xy
        new_x, new_y = current.origin_xy
        zoom = scale_x * new_w / min(width, height * self._aspect)
        pan_x = state.pan_xy[0] + ((old_x - old_w / 2) - (new_x - new_w / 2)) * scale_x
        pan_y = state.pan_xy[1] + ((old_y - old_h / 2) - (new_y - new_h / 2)) * scale_y
        states['original'] = ViewTransform(zoom, (pan_x, pan_y))
        self._preview.restore_navigation(states)

    def select_variant(self, key: str) -> None:
        index = self._variant.findData(key)
        if index >= 0:
            self._variant.setCurrentIndex(index)

    def _selected_variant(self) -> None:
        self._selected_frame()
        self.variant_changed.emit(str(self._variant.currentData()))

    def pause(self) -> None:
        self._timer.stop()
        self._play.setText('Play')

    def _set_interval(self) -> None:
        self._timer.setInterval(round(1000 / self._fps.value()))

    def _selected_frame(self) -> None:
        self.pause()
        self._render()
        self._sync()

    def _toggle_play(self) -> None:
        if self._timer.isActive():
            self.pause()
        elif self._renderer is not None:
            if self._number.value() == len(self._frames):
                self._number.setValue(1)
            if self._render_failed:
                return
            self._play.setText('Pause')
            self._timer.start()

    def _advance(self) -> None:
        index = self._number.value() + 1
        if index > len(self._frames):
            if self._loop.isChecked():
                index = 1
            else:
                self.pause()
                return
        with QSignalBlocker(self._number):
            self._number.setValue(index)
        self._render()
        self._sync()
        if index == len(self._frames) and not self._loop.isChecked():
            self.pause()

    def _sync(self) -> None:
        available = self._renderer is not None
        self._variant.setEnabled(available)
        self._number.setEnabled(available)
        self._play.setEnabled(available and not self._render_failed and len(self._frames) > 1)
        self._previous.setEnabled(available and self._number.value() > 1)
        self._next.setEnabled(available and self._number.value() < len(self._frames))

    def _render(self) -> None:
        if self._renderer is None:
            return
        index = self._number.value() - 1
        frame = self._frames[index]
        source_index = f' · MPP {frame.source_frame_index + 1}' if frame.source_frame_index is not None else ''
        text = f'Klatka {index + 1}: {frame.source}{source_index}'
        variant = str(self._variant.currentData())
        if self._trial is not None:
            positions = self._variants.get(variant)
            if positions is not None:
                x, y = positions[index]
                text += f'\nX: {x:.3f} px · Y: {y:.3f} px · kotwica: klatka 1'
                if variant.startswith('huber:') and self._trial.positions is not None:
                    lx, ly = self._trial.positions[index]
                    text += f'\nHuber − LS: X {x - lx:+.3f} px · Y {y - ly:+.3f} px'
        self._source.setText(text)
        try:
            raster = self._renderer.render(index, variant, gamma=self._gamma.value(),
                                            pixel_proportions=self._pixels.isChecked())
            height, width, _ = raster.rgba.shape
            image = QImage(raster.rgba.tobytes(), width, height, raster.rgba.strides[0],
                           QImage.Format.Format_RGBA8888).copy()
            self._preview.set_image(image, aspect=raster.aspect)
            self._aspect = raster.aspect
            self._render_failed = False
            self._status.setText('Wspólny obszar i kontrast oryginalnej klatki dla wszystkich wariantów. '
                                  'Eksport używa aktywnego aligned. Wybór wariantu porównania nie zmienia filmu.')
        except (ImportError, OSError, ValueError, MemoryError, OverflowError) as error:
            self.pause()
            self._render_failed = True
            self._preview.clear_frame()
            self._status.setText(f'Nie można wyświetlić klatki: {error}')
        self._sync()
