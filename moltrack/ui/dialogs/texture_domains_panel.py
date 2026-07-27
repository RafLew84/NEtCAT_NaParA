from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY,
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    MolecularFrameRange,
    TextureDomainAnalysisSettings,
    TextureDomainSessionState,
    TextureDomainViewSettings,
)


@dataclass(frozen=True)
class TextureDomainAnalysisRequest:
    frame_range: MolecularFrameRange
    source_view: str
    settings: TextureDomainAnalysisSettings

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be MolecularFrameRange.")
        if self.source_view not in ("raw", "expanded_aligned"):
            raise ValueError("Unsupported texture-domain source view.")
        if not isinstance(self.settings, TextureDomainAnalysisSettings):
            raise TypeError("settings must be TextureDomainAnalysisSettings.")


class TextureDomainsPanel(QScrollArea):
    analysis_requested = pyqtSignal(object)
    cancel_requested = pyqtSignal()
    view_settings_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._frame_count: int | None = None
        self._source_view = "raw"
        self._state: TextureDomainSessionState | None = None
        self._running = False
        self.setWidgetResizable(True)

        content = QWidget(self)
        layout = QVBoxLayout(content)

        analysis_group = QGroupBox("Local texture classification", content)
        form = QFormLayout(analysis_group)
        self.preset_combo = QComboBox(analysis_group)
        self.preset_combo.addItem(
            "TTMAPP local texture v1 (experimental)",
            TTMAPP_TEXTURE_DOMAIN_PRESET,
        )
        self.preset_combo.setToolTip(
            TTMAPP_TEXTURE_DOMAIN_PRESET.calibration_note
        )
        form.addRow("Preset", self.preset_combo)

        self.source_view_label = QLabel("raw", analysis_group)
        form.addRow("Source view", self.source_view_label)

        range_row = QHBoxLayout()
        self.start_frame = QSpinBox(analysis_group)
        self.end_frame = QSpinBox(analysis_group)
        range_row.addWidget(self.start_frame)
        range_row.addWidget(QLabel("to", analysis_group))
        range_row.addWidget(self.end_frame)
        form.addRow("Frames", range_row)

        action_row = QHBoxLayout()
        self.run_button = QPushButton("Analyze Range", analysis_group)
        self.cancel_button = QPushButton("Cancel", analysis_group)
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.run_button)
        action_row.addWidget(self.cancel_button)
        form.addRow("", action_row)
        layout.addWidget(analysis_group)

        overlay_group = QGroupBox("Overlay", content)
        overlay_layout = QFormLayout(overlay_group)
        self.show_overlay_checkbox = QCheckBox("Show texture domains", overlay_group)
        self.show_overlay_checkbox.setChecked(True)
        overlay_layout.addRow("", self.show_overlay_checkbox)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, overlay_group)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(80)
        overlay_layout.addRow("Opacity", self.opacity_slider)
        self.show_unknown_checkbox = QCheckBox("Show unclassified", overlay_group)
        overlay_layout.addRow("", self.show_unknown_checkbox)
        layout.addWidget(overlay_group)

        self.status_label = QLabel("Not computed", content)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.current_frame_label = QLabel("Current frame: no result", content)
        self.current_frame_label.setWordWrap(True)
        layout.addWidget(self.current_frame_label)

        self.results_table = QTableWidget(0, 6, content)
        self.results_table.setHorizontalHeaderLabels(
            ("Frame", "A", "B", "C", "Unknown", "Domains")
        )
        self.results_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        layout.addStretch(1)
        self.setWidget(content)

        self.start_frame.valueChanged.connect(self._on_range_changed)
        self.end_frame.valueChanged.connect(self._on_range_changed)
        self.run_button.clicked.connect(self._request_analysis)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.show_overlay_checkbox.toggled.connect(self._emit_view_settings)
        self.opacity_slider.valueChanged.connect(self._emit_view_settings)
        self.show_unknown_checkbox.toggled.connect(self._emit_view_settings)

    def configure(
        self,
        *,
        frame_count: int,
        source_view: str,
        active_frame_index: int,
    ) -> None:
        frame_count = int(frame_count)
        active_frame_index = int(active_frame_index)
        if frame_count <= 0 or not 0 <= active_frame_index < frame_count:
            raise ValueError("Texture-domain frame context is invalid.")
        if source_view not in ("raw", "expanded_aligned"):
            raise ValueError("Unsupported texture-domain source view.")
        first_configuration = self._frame_count is None
        self._frame_count = frame_count
        self._source_view = source_view
        self.source_view_label.setText(source_view.replace("_", " "))
        for spin_box in (self.start_frame, self.end_frame):
            spin_box.setRange(1, frame_count)
        if first_configuration:
            start = active_frame_index + 1
            self.start_frame.setValue(start)
            self.end_frame.setValue(min(frame_count, start + 5))
        self._refresh_run_enabled()

    def settings(self) -> TextureDomainAnalysisSettings:
        value = self.preset_combo.currentData()
        if not isinstance(value, TextureDomainAnalysisSettings):
            raise RuntimeError("Texture-domain preset is unavailable.")
        return value

    def analysis_request(self) -> TextureDomainAnalysisRequest:
        if self._frame_count is None:
            raise RuntimeError("Texture-domain frame context is not configured.")
        return TextureDomainAnalysisRequest(
            frame_range=MolecularFrameRange(
                "texture domains",
                self.start_frame.value() - 1,
                self.end_frame.value() - 1,
            ),
            source_view=self._source_view,
            settings=self.settings(),
        )

    def view_settings(self) -> TextureDomainViewSettings:
        return TextureDomainViewSettings(
            show_overlay=self.show_overlay_checkbox.isChecked(),
            opacity_percent=self.opacity_slider.value(),
            show_unknown=self.show_unknown_checkbox.isChecked(),
        )

    def set_view_settings(self, settings: TextureDomainViewSettings) -> None:
        if not isinstance(settings, TextureDomainViewSettings):
            raise TypeError("settings must be TextureDomainViewSettings.")
        blockers = (
            QSignalBlocker(self.show_overlay_checkbox),
            QSignalBlocker(self.opacity_slider),
            QSignalBlocker(self.show_unknown_checkbox),
        )
        try:
            self.show_overlay_checkbox.setChecked(settings.show_overlay)
            self.opacity_slider.setValue(settings.opacity_percent)
            self.show_unknown_checkbox.setChecked(settings.show_unknown)
        finally:
            del blockers

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        self.run_button.setEnabled(
            not self._running and self._has_valid_range()
        )
        self.cancel_button.setEnabled(self._running)
        for widget in (
            self.preset_combo,
            self.start_frame,
            self.end_frame,
        ):
            widget.setEnabled(not self._running)
        if self._running:
            self.status_label.setText("Analyzing texture domains...")

    def set_progress(
        self,
        completed_count: int,
        total_count: int,
        frame_index: int,
    ) -> None:
        self.status_label.setText(
            f"Frame {int(frame_index) + 1}: "
            f"{int(completed_count)}/{int(total_count)}"
        )

    def set_error(self, message: str) -> None:
        self.status_label.setText(str(message))

    def set_session_state(
        self,
        state: TextureDomainSessionState | None,
    ) -> None:
        if state is not None and not isinstance(state, TextureDomainSessionState):
            raise TypeError("state must be TextureDomainSessionState or None.")
        self._state = state
        if state is None:
            self.results_table.setRowCount(0)
            self.status_label.setText("Not computed")
            self.current_frame_label.setText("Current frame: no result")
            return
        self.set_view_settings(state.view_settings)
        self.start_frame.setValue(state.range_start_frame + 1)
        self.end_frame.setValue(state.range_end_frame + 1)
        self._populate_results_table(state)
        self.status_label.setText(
            f"Computed {len(state.frame_results)} frame(s)"
            if state.computed
            else "Not computed"
        )

    def set_current_frame(self, frame_index: int) -> None:
        result = (
            None if self._state is None else self._state.frame_result(frame_index)
        )
        if result is None:
            self.current_frame_label.setText(
                f"Frame {int(frame_index) + 1}: no result"
            )
            return
        counts = Counter(value.class_key for value in result.points)
        labels = {
            value.key: value.short_label for value in self._state.settings.classes
        }
        parts = [
            f"{labels[key]}: {counts[key]}"
            for key in labels
        ]
        parts.append(
            f"Unknown: {counts[TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY]}"
        )
        self.current_frame_label.setText(
            f"Frame {result.frame_index + 1} | "
            + " | ".join(parts)
            + f" | domains: {len(result.components)}"
        )

    def _request_analysis(self) -> None:
        if self._running or not self._has_valid_range():
            return
        self.analysis_requested.emit(self.analysis_request())

    def _on_range_changed(self) -> None:
        self._refresh_run_enabled()

    def _has_valid_range(self) -> bool:
        return (
            self._frame_count is not None
            and self.start_frame.value() <= self.end_frame.value()
        )

    def _refresh_run_enabled(self) -> None:
        self.run_button.setEnabled(
            not self._running and self._has_valid_range()
        )

    def _emit_view_settings(self) -> None:
        self.view_settings_changed.emit(self.view_settings())

    def _populate_results_table(
        self,
        state: TextureDomainSessionState,
    ) -> None:
        class_definitions = state.settings.classes
        self.results_table.setColumnCount(len(class_definitions) + 3)
        self.results_table.setHorizontalHeaderLabels(
            (
                "Frame",
                *(value.short_label for value in class_definitions),
                "Unknown",
                "Domains",
            )
        )
        self.results_table.setRowCount(len(state.frame_results))
        class_keys = tuple(value.key for value in class_definitions)
        for row, result in enumerate(state.frame_results):
            counts = Counter(value.class_key for value in result.points)
            values = (
                result.frame_index + 1,
                *(counts[key] for key in class_keys),
                counts[TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY],
                len(result.components),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_table.setItem(row, column, item)
