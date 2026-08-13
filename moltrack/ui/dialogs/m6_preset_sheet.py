from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
import json
from pathlib import Path
from typing import Literal

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    FirstShellGeometryPolicy,
    M6Preset,
    M6PresetImportResult,
    M6PresetLibrary,
    M6PresetWorkspace,
    M6RunConfiguration,
    UnsavedM6PresetChanges,
    decode_m6_preset_file,
)

from .m6_settings_editor import M6SettingsEditor


DirtyDecision = Literal["save", "discard", "cancel"]
ConflictDecision = tuple[Literal["rename", "overwrite", "cancel"], str | None]


class M6PresetSheet(QWidget):
    """Presets-stage UI adapter over one M6PresetWorkspace."""

    active_preset_changed = pyqtSignal(object)

    def __init__(
        self,
        library: M6PresetLibrary,
        parent: QWidget | None = None,
        *,
        dirty_decision: Callable[[], DirtyDecision] | None = None,
        import_conflict_decision: Callable[[str], ConflictDecision] | None = None,
        save_as_name: Callable[[str], str | None] | None = None,
    ) -> None:
        if not isinstance(library, M6PresetLibrary):
            raise TypeError("library must be an M6PresetLibrary.")
        super().__init__(parent)
        self.setObjectName("domainAnalysisSheet_presets")
        self._library = library
        self._workspace = M6PresetWorkspace(library)
        self._dirty_decision = dirty_decision or self._ask_dirty_decision
        self._import_conflict_decision = (
            import_conflict_decision or self._ask_import_conflict
        )
        self._save_as_name = save_as_name or self._ask_save_as_name
        self._rendering = False
        self._build_ui()
        self._connect_controls()
        self.render_library()

    def render_library(self, *, selected_name: str | None = None) -> None:
        snapshot = self._library.snapshot
        selected = selected_name or self._workspace.working_copy.source_name
        combo_blocker = QSignalBlocker(self.preset_combo)
        backend_blocker = QSignalBlocker(self.backend_combo)
        self.preset_combo.clear()
        for preset in snapshot.presets:
            label = preset.name
            if preset.name == snapshot.active_preset.name:
                label = f"{label} (active)"
            if preset.built_in:
                label = f"{label} [built-in]"
            self.preset_combo.addItem(label, preset.name)
        if self._workspace.working_copy.source_name is None:
            working_name = self._workspace.working_copy.name or "New preset"
            self.preset_combo.addItem(f"{working_name} [working copy]", None)
        self.backend_combo.clear()
        identities = {
            preset.configuration.backend_id: preset.configuration.backend_identity
            for preset in snapshot.presets
        }
        for backend_id in sorted(identities):
            self.backend_combo.addItem(backend_id, backend_id)
        index = self.preset_combo.findData(selected)
        if index < 0:
            index = self.preset_combo.findData(snapshot.active_preset.name)
        self.preset_combo.setCurrentIndex(index)
        del combo_blocker, backend_blocker
        self._render_working_copy()

    def import_payload(self, payload: object) -> M6PresetImportResult | None:
        try:
            imported, legacy = decode_m6_preset_file(payload)
            conflict: Literal["rename", "overwrite", "cancel"] = "cancel"
            rename_to: str | None = None
            has_conflict = not legacy and _has_preset(
                self._library, imported.name
            )
            if has_conflict:
                conflict, rename_to = self._import_conflict_decision(imported.name)
            if legacy or not has_conflict or conflict != "cancel":
                if not self._resolve_dirty_before_action():
                    return None
            result = self._workspace.import_payload(
                payload,
                conflict=conflict,
                rename_to=rename_to,
            )
        except (OSError, TypeError, ValueError, UnsavedM6PresetChanges) as error:
            self.status_label.setText(str(error))
            return None
        if result.action != "cancelled":
            self.render_library(
                selected_name=None if result.preset is None else result.preset.name
            )
        self.status_label.setText(_import_status(result))
        return result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.preset_combo = QComboBox(self)
        self.name_edit = QLineEdit(self)
        self.description_edit = QLineEdit(self)
        self.backend_combo = QComboBox(self)
        form.addRow("Saved preset", self.preset_combo)
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Backend", self.backend_combo)
        layout.addLayout(form)

        self.settings_editor = M6SettingsEditor(self)
        layout.addWidget(self.settings_editor)
        self.diff_table = QTableWidget(0, 3, self)
        self.diff_table.setObjectName("m6PresetDiff")
        self.diff_table.setHorizontalHeaderLabels(("Parameter", "Saved", "Working"))
        self.diff_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.diff_table.setMinimumHeight(120)
        layout.addWidget(self.diff_table)

        first_actions = QHBoxLayout()
        self.new_button = _button("New", QStyle.StandardPixmap.SP_FileIcon, self)
        self.duplicate_button = _button(
            "Duplicate", QStyle.StandardPixmap.SP_FileDialogNewFolder, self
        )
        self.rename_button = _button(
            "Rename", QStyle.StandardPixmap.SP_FileDialogDetailedView, self
        )
        self.delete_button = _button(
            "Delete", QStyle.StandardPixmap.SP_TrashIcon, self
        )
        self.import_button = _button(
            "Import JSON", QStyle.StandardPixmap.SP_DialogOpenButton, self
        )
        for button in (
            self.new_button,
            self.duplicate_button,
            self.rename_button,
            self.delete_button,
            self.import_button,
        ):
            first_actions.addWidget(button)
        first_actions.addStretch(1)
        layout.addLayout(first_actions)

        second_actions = QHBoxLayout()
        self.save_button = _button(
            "Save", QStyle.StandardPixmap.SP_DialogSaveButton, self
        )
        self.save_as_button = _button(
            "Save As", QStyle.StandardPixmap.SP_DialogSaveButton, self
        )
        self.set_active_button = _button(
            "Set active", QStyle.StandardPixmap.SP_DialogApplyButton, self
        )
        second_actions.addWidget(self.save_button)
        second_actions.addWidget(self.save_as_button)
        second_actions.addWidget(self.set_active_button)
        second_actions.addStretch(1)
        layout.addLayout(second_actions)

        self.dirty_label = QLabel(self)
        self.dirty_label.setObjectName("m6PresetDirtyStatus")
        self.status_label = QLabel(self)
        self.status_label.setObjectName("m6PresetStatus")
        layout.addWidget(self.dirty_label)
        layout.addWidget(self.status_label)

    def _connect_controls(self) -> None:
        self.preset_combo.currentIndexChanged.connect(self._select_preset)
        self.name_edit.textChanged.connect(self._editing_changed)
        self.description_edit.textChanged.connect(self._editing_changed)
        self.backend_combo.currentIndexChanged.connect(self._editing_changed)
        self.settings_editor.settings_changed.connect(self._editing_changed)
        self.new_button.clicked.connect(self._new)
        self.duplicate_button.clicked.connect(self._duplicate)
        self.rename_button.clicked.connect(self._rename)
        self.delete_button.clicked.connect(self._delete)
        self.import_button.clicked.connect(self._import_file)
        self.save_button.clicked.connect(self._save)
        self.save_as_button.clicked.connect(self._save_as)
        self.set_active_button.clicked.connect(self._set_active)

    def _select_preset(self) -> None:
        if self._rendering or self.preset_combo.currentIndex() < 0:
            return
        target = self.preset_combo.currentData()
        if not isinstance(target, str):
            return
        try:
            if self._workspace.dirty:
                decision = self._dirty_decision()
                if decision == "cancel":
                    self._restore_combo_selection()
                    return
                if decision == "save":
                    if self._save_working_copy() is None:
                        self._restore_combo_selection()
                        return
                elif decision != "discard":
                    raise ValueError(f"Unsupported dirty decision: {decision!r}.")
                self._workspace.resolve_and_checkout(target, decision="discard")
            else:
                self._workspace.checkout(target)
        except (OSError, TypeError, ValueError, UnsavedM6PresetChanges) as error:
            self.status_label.setText(str(error))
            self._restore_combo_selection()
            return
        self._render_working_copy()

    def _editing_changed(self) -> None:
        if self._rendering:
            return
        try:
            self._sync_working_copy()
        except (TypeError, ValueError) as error:
            self.dirty_label.setText("Invalid working copy")
            self.status_label.setText(str(error))
            self.save_button.setEnabled(False)
            self.save_as_button.setEnabled(False)
            return
        self.status_label.clear()
        self._render_state()

    def _sync_working_copy(self) -> None:
        self._workspace.update(
            name=self.name_edit.text(),
            description=self.description_edit.text(),
            configuration=self._configuration_from_editor(),
        )

    def _configuration_from_editor(self) -> M6RunConfiguration:
        settings = self.settings_editor.settings()
        backend_id = self.backend_combo.currentData()
        if not isinstance(backend_id, str):
            raise ValueError("Select an M6 backend.")
        current = self._workspace.working_copy.configuration
        identity = current.backend_identity
        if identity.backend_id != backend_id:
            identity = next(
                preset.configuration.backend_identity
                for preset in self._library.snapshot.presets
                if preset.configuration.backend_id == backend_id
            )
        identity = replace(
            identity,
            settings_fingerprint=m6_settings_fingerprint(settings),
        )
        current_policy = current.first_shell_geometry
        policy = FirstShellGeometryPolicy(
            mode="fixed",
            fixed_r_min_nm=settings.first_shell_r_min_nm,
            fixed_r_max_nm=settings.first_shell_r_max_nm,
            algorithm_version=current_policy.algorithm_version,
        )
        return M6RunConfiguration(
            backend_identity=identity,
            settings=settings,
            first_shell_geometry=policy,
        )

    def _new(self) -> None:
        if not self._resolve_dirty_before_action():
            return
        try:
            self._workspace.new_from_current()
        except (TypeError, ValueError, UnsavedM6PresetChanges) as error:
            self.status_label.setText(str(error))
            return
        self.render_library()
        self.name_edit.setFocus()

    def _duplicate(self) -> None:
        source = self._workspace.working_copy.source_name
        if source is None:
            return
        name, accepted = QInputDialog.getText(
            self, "Duplicate M6 preset", "Name", text=f"{source} copy"
        )
        if not accepted:
            return
        if not self._resolve_dirty_before_action():
            return
        try:
            saved = self._workspace.duplicate(source, name)
            self._workspace.checkout(saved.name)
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library(selected_name=saved.name)

    def _rename(self) -> None:
        source = self._workspace.working_copy.source_name
        if source is None:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename M6 preset", "Name", text=source
        )
        if not accepted:
            return
        if not self._resolve_dirty_before_action():
            return
        try:
            saved = self._workspace.rename(source, name)
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library(selected_name=saved.name)

    def _delete(self) -> None:
        source = self._workspace.working_copy.source_name
        if source is None:
            return
        if QMessageBox.question(
            self,
            "Delete M6 preset",
            f"Delete {source}?",
        ) != QMessageBox.StandardButton.Yes:
            return
        if not self._resolve_dirty_before_action():
            return
        try:
            self._workspace.delete(source)
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library()

    def _import_file(self) -> None:
        filename, _filter = QFileDialog.getOpenFileName(
            self, "Import M6 preset", "", "JSON files (*.json)"
        )
        if not filename:
            return
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.status_label.setText(str(error))
            return
        self.import_payload(payload)

    def _save(self) -> None:
        try:
            saved = self._save_working_copy()
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return
        if saved is None:
            return
        self.render_library(selected_name=saved.name)
        self.status_label.setText(f"Saved {saved.name}.")

    def _save_as(self) -> None:
        try:
            self._sync_working_copy()
            saved = self._workspace.save_as(self.name_edit.text())
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library(selected_name=saved.name)
        self.status_label.setText(f"Saved {saved.name}.")

    def _save_working_copy(self) -> M6Preset | None:
        self._sync_working_copy()
        if self._workspace.working_copy.requires_save_as:
            name = self.name_edit.text()
            if not name.strip() or _has_preset(self._library, name):
                proposed = f"{self._workspace.working_copy.name} copy".strip()
                selected_name = self._save_as_name(proposed)
                if selected_name is None:
                    return None
                name = selected_name
            return self._workspace.save_as(name)
        return self._workspace.save()

    def _set_active(self) -> None:
        if self._workspace.dirty:
            self.status_label.setText("Save or discard changes before activation.")
            return
        source = self._workspace.working_copy.source_name
        if source is None:
            return
        try:
            active = self._library.set_active(source)
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return
        self.render_library(selected_name=active.name)
        self.status_label.setText(f"Active: {active.name}.")
        self.active_preset_changed.emit(active)

    def _resolve_dirty_before_action(self) -> bool:
        if not self._workspace.dirty:
            return True
        decision = self._dirty_decision()
        if decision == "cancel":
            return False
        try:
            if decision == "save":
                if self._save_working_copy() is None:
                    return False
            elif decision == "discard":
                source = self._workspace.working_copy.source_name
                if source is None:
                    active = self._library.snapshot.active_preset
                    self._workspace = M6PresetWorkspace(self._library)
                    if active.name != self._workspace.working_copy.source_name:
                        self._workspace.checkout(active.name)
                else:
                    self._workspace.resolve_and_checkout(source, decision="discard")
            else:
                raise ValueError(f"Unsupported dirty decision: {decision!r}.")
        except (OSError, TypeError, ValueError) as error:
            self.status_label.setText(str(error))
            return False
        self.render_library()
        return True

    def _render_working_copy(self) -> None:
        copy = self._workspace.working_copy
        self._rendering = True
        self.name_edit.setText(copy.name)
        self.description_edit.setText(copy.description)
        if self.backend_combo.findData(copy.configuration.backend_id) < 0:
            self.backend_combo.addItem(
                copy.configuration.backend_id, copy.configuration.backend_id
            )
        self.backend_combo.setCurrentIndex(
            self.backend_combo.findData(copy.configuration.backend_id)
        )
        self.settings_editor.set_settings(copy.configuration.settings)
        self._rendering = False
        self.status_label.clear()
        self._render_state()

    def _render_state(self) -> None:
        copy = self._workspace.working_copy
        source = None
        if copy.source_name is not None:
            source = self._library.preset(copy.source_name)
        dirty = self._workspace.dirty
        self.dirty_label.setText("Unsaved changes" if dirty else "Saved")
        self.save_button.setEnabled(dirty)
        self.save_as_button.setEnabled(bool(copy.name.strip()))
        self.rename_button.setEnabled(source is not None and not source.built_in)
        self.delete_button.setEnabled(
            source is not None
            and not source.built_in
            and source.name != self._library.snapshot.active_preset.name
        )
        self.set_active_button.setEnabled(
            not dirty
            and source is not None
            and source.name != self._library.snapshot.active_preset.name
        )
        differences = self._workspace.differences
        self.diff_table.setRowCount(len(differences))
        for row, difference in enumerate(differences):
            values = (
                difference.path,
                _display_value(difference.saved_value),
                _display_value(difference.working_value),
            )
            for column, value in enumerate(values):
                self.diff_table.setItem(row, column, QTableWidgetItem(value))
        self.diff_table.resizeColumnsToContents()

    def _restore_combo_selection(self) -> None:
        source = self._workspace.working_copy.source_name
        blocker = QSignalBlocker(self.preset_combo)
        self.preset_combo.setCurrentIndex(self.preset_combo.findData(source))
        del blocker

    def _ask_dirty_decision(self) -> DirtyDecision:
        choice = QMessageBox.warning(
            self,
            "Unsaved M6 preset changes",
            "Save changes before switching presets?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            return "save"
        if choice == QMessageBox.StandardButton.Discard:
            return "discard"
        return "cancel"

    def _ask_import_conflict(self, name: str) -> ConflictDecision:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("M6 preset conflict")
        dialog.setText(f"A preset named {name} already exists.")
        rename_button = dialog.addButton("Rename", QMessageBox.ButtonRole.ActionRole)
        overwrite_button = dialog.addButton(
            "Overwrite", QMessageBox.ButtonRole.DestructiveRole
        )
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        if dialog.clickedButton() is overwrite_button:
            return "overwrite", None
        if dialog.clickedButton() is rename_button:
            new_name, accepted = QInputDialog.getText(
                self, "Rename imported preset", "Name", text=f"{name} imported"
            )
            return ("rename", new_name) if accepted else ("cancel", None)
        return "cancel", None

    def _ask_save_as_name(self, proposed: str) -> str | None:
        name, accepted = QInputDialog.getText(
            self, "Save M6 preset as", "Name", text=proposed
        )
        return name if accepted else None


def _button(label: str, icon: QStyle.StandardPixmap, parent: QWidget) -> QPushButton:
    button = QPushButton(label, parent)
    style = button.style()
    if style is None:
        raise RuntimeError("Qt application style is unavailable.")
    button.setIcon(style.standardIcon(icon))
    return button


def _has_preset(library: M6PresetLibrary, name: str) -> bool:
    try:
        library.preset(name)
    except ValueError:
        return False
    return True


def _display_value(value: object) -> str:
    if isinstance(value, Mapping):
        return json.dumps(value, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def _import_status(result: M6PresetImportResult) -> str:
    if result.action == "working_copy":
        return "Legacy preset opened as a working copy. Use Save As."
    if result.action == "cancelled":
        return "Import cancelled."
    if result.preset is None:
        return "Import completed."
    return f"Imported {result.preset.name}."


__all__ = ["M6PresetSheet"]
