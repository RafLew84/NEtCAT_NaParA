from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    M6Preset,
    M6PresetLibrary,
    M6RunConfiguration,
)


class M6PresetSheet(QWidget):
    """Thin Presets-stage adapter over one M6PresetLibrary."""

    active_preset_changed = pyqtSignal(object)

    def __init__(
        self,
        library: M6PresetLibrary,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(library, M6PresetLibrary):
            raise TypeError("library must be an M6PresetLibrary.")
        super().__init__(parent)
        self.setObjectName("domainAnalysisSheet_presets")
        self._library = library
        self._working_configuration: M6RunConfiguration | None = None
        self._build_ui()
        self._connect_controls()
        self.render_library()

    def render_library(self, *, selected_name: str | None = None) -> None:
        snapshot = self._library.snapshot
        selected = selected_name or self.preset_combo.currentData()
        blocker = QSignalBlocker(self.preset_combo)
        self.preset_combo.clear()
        for preset in snapshot.presets:
            label = (
                f"{preset.name} (active)"
                if preset.name == snapshot.active_preset.name
                else preset.name
            )
            self.preset_combo.addItem(label, preset.name)
        index = self.preset_combo.findData(selected)
        if index < 0:
            index = self.preset_combo.findData(snapshot.active_preset.name)
        self.preset_combo.setCurrentIndex(index)
        del blocker
        self._render_selected()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.preset_combo = QComboBox(self)
        self.name_edit = QLineEdit(self)
        self.description_edit = QLineEdit(self)
        form.addRow("Saved preset", self.preset_combo)
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.new_button = QPushButton("New", self)
        self.save_button = QPushButton("Save", self)
        self.set_active_button = QPushButton("Set active", self)
        style = self.style()
        if style is None:
            raise RuntimeError("Qt application style is unavailable.")
        self.new_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.save_button.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self.set_active_button.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        )
        for button in (
            self.new_button,
            self.save_button,
            self.set_active_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("m6PresetStatus")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _connect_controls(self) -> None:
        self.preset_combo.currentIndexChanged.connect(self._render_selected)
        self.new_button.clicked.connect(self._new)
        self.save_button.clicked.connect(self._save)
        self.set_active_button.clicked.connect(self._set_active)

    def _selected_preset(self) -> M6Preset:
        name = self.preset_combo.currentData()
        return next(
            preset
            for preset in self._library.snapshot.presets
            if preset.name == name
        )

    def _render_selected(self) -> None:
        if self.preset_combo.currentIndex() < 0:
            return
        preset = self._selected_preset()
        self._working_configuration = preset.configuration
        self.name_edit.setText(preset.name)
        self.description_edit.setText(preset.description)
        self.save_button.setEnabled(False)
        self.set_active_button.setEnabled(
            preset.name != self._library.snapshot.active_preset.name
        )
        self.status_label.clear()

    def _new(self) -> None:
        self._working_configuration = self._selected_preset().configuration
        self.name_edit.clear()
        self.description_edit.clear()
        self.save_button.setEnabled(True)
        self.set_active_button.setEnabled(False)
        self.name_edit.setFocus()
        self.status_label.clear()

    def _save(self) -> None:
        configuration = self._working_configuration
        if configuration is None:
            return
        try:
            saved = self._library.save(self._library.new(
                self.name_edit.text(),
                configuration,
                description=self.description_edit.text(),
            ))
        except (TypeError, ValueError, OSError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library(selected_name=saved.name)
        self.status_label.setText(f"Saved {saved.name}.")

    def _set_active(self) -> None:
        try:
            active = self._library.set_active(self._selected_preset().name)
        except (TypeError, ValueError, OSError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library(selected_name=active.name)
        self.status_label.setText(f"Active: {active.name}.")
        self.active_preset_changed.emit(active)


__all__ = ["M6PresetSheet"]
