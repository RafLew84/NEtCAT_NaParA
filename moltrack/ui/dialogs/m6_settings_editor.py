from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from moltrack.analysis.m6_settings import MolecularM6OrientationAnalysisSettings


_FIXED_FIELDS = {
    "symmetry_m",
    "bond_weighting",
    "duplicate_policy",
    "duplicate_chain_policy",
    "geometry_collision_policy",
    "delaunay_degeneracy_policy",
}


class M6SettingsEditor(QScrollArea):
    """Typed, scrollable editor for every field in the M6 settings contract."""

    settings_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumHeight(260)
        panel = QWidget(self)
        form = QFormLayout(panel)
        self._controls: dict[str, QWidget] = {}
        self._baseline_values: dict[str, object] = {}
        self._modified_fields: set[str] = set()
        defaults = MolecularM6OrientationAnalysisSettings()
        for setting in fields(defaults):
            name = setting.name
            control = _control_for(getattr(defaults, name), panel)
            control.setObjectName(f"m6Setting_{name}")
            control.setEnabled(name not in _FIXED_FIELDS)
            _connect_changed(
                control,
                lambda _value=None, field_name=name: self._mark_changed(field_name),
            )
            self._controls[name] = control
            form.addRow(name.replace("_", " "), control)
        self.setWidget(panel)
        self.set_settings(defaults)

    def set_settings(self, settings: MolecularM6OrientationAnalysisSettings) -> None:
        if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        for name, value in settings.to_dict().items():
            control = self._controls[name]
            blocker = QSignalBlocker(control)
            _set_control_value(control, value)
            del blocker
        self._baseline_values = dict(settings.to_dict())
        self._modified_fields.clear()

    def settings(self) -> MolecularM6OrientationAnalysisSettings:
        values = {
            name: (
                _control_value(control)
                if name in self._modified_fields
                else self._baseline_values[name]
            )
            for name, control in self._controls.items()
        }
        return MolecularM6OrientationAnalysisSettings.from_dict(values)

    def control(self, name: str) -> QWidget:
        return self._controls[name]

    def _mark_changed(self, field_name: str) -> None:
        self._modified_fields.add(field_name)
        self.settings_changed.emit()


def _control_for(value: object, parent: QWidget) -> QWidget:
    if isinstance(value, bool):
        return QCheckBox(parent)
    if isinstance(value, int):
        integer_control = QSpinBox(parent)
        integer_control.setRange(-1_000_000_000, 1_000_000_000)
        return integer_control
    if isinstance(value, float):
        float_control = QDoubleSpinBox(parent)
        float_control.setDecimals(12)
        float_control.setRange(-1.0e12, 1.0e12)
        float_control.setSingleStep(0.01)
        return float_control
    return QLineEdit(parent)


def _connect_changed(control: QWidget, callback) -> None:
    if isinstance(control, QCheckBox):
        control.toggled.connect(callback)
    elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
        control.valueChanged.connect(callback)
    elif isinstance(control, QLineEdit):
        control.textChanged.connect(callback)


def _set_control_value(control: QWidget, value: object) -> None:
    if isinstance(control, QCheckBox):
        control.setChecked(bool(value))
    elif isinstance(control, QSpinBox):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("Integer M6 setting must be an int.")
        control.setValue(value)
    elif isinstance(control, QDoubleSpinBox):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Floating-point M6 setting must be numeric.")
        control.setValue(float(value))
    elif isinstance(control, QLineEdit):
        control.setText(str(value))


def _control_value(control: QWidget) -> object:
    if isinstance(control, QCheckBox):
        return control.isChecked()
    if isinstance(control, QSpinBox):
        return control.value()
    if isinstance(control, QDoubleSpinBox):
        return control.value()
    if isinstance(control, QLineEdit):
        return control.text()
    raise TypeError(f"Unsupported M6 settings control: {type(control).__name__}.")


__all__ = ["M6SettingsEditor"]
