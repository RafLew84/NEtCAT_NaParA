"""Readable current and recorded feature parameters, without changing a result."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from stmviewer.feature_provenance import recorded_profile
from stmviewer.method_parameters import PARAMETER_METHODS, AkazeParameters, FeatureParameters
from stmviewer.registration import RegistrationResult
from stmviewer.ui.method_parameters import MethodParameterControls


def parameter_summary(parameters: FeatureParameters) -> str:
    if isinstance(parameters, AkazeParameters):
        text = f'próg detektora {parameters.threshold:g}'
    else:
        text = (f'próg SuperPoint {parameters.detection_threshold:g}; NMS {parameters.nms_radius}; '
                f'punkty ≤ {parameters.max_keypoints}; próg LightGlue {parameters.filter_threshold:g}; '
                f'pełne obliczenia: {"tak" if parameters.full_computation else "nie"}')
    contrast = parameters.contrast
    text += f'; tolerancja {parameters.radius:g} px original; '
    if contrast.mode == 'percentiles':
        text += f'percentyle {contrast.lower:g}–{contrast.upper:g}'
    elif contrast.mode == 'clahe':
        text += f'CLAHE {contrast.clip_limit:g}, siatka {contrast.grid_x}×{contrast.grid_y}'
    else:
        text += 'min–max'
    return text


class ParameterStatus(QLabel):
    def __init__(self, controls: MethodParameterControls, name: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName(name)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._controls = controls
        self._method = ''
        self._provenance: tuple[tuple[str, str], ...] | None = None
        controls.changed.connect(self._refresh)

    def set_context(self, method: str, provenance: tuple[tuple[str, str], ...] | None = None) -> None:
        aliases = {label: key for key, label in PARAMETER_METHODS.items()}
        self._method, self._provenance = aliases.get(method, method), provenance
        self._refresh()

    def _refresh(self) -> None:
        if self._method not in PARAMETER_METHODS:
            self.clear()
            self.hide()
            return
        current = self._controls.profiles.get(self._method)
        label = PARAMETER_METHODS[self._method]
        if self._provenance is None:
            text = f'Parametry {label}: {parameter_summary(current)}.'
        else:
            used = recorded_profile(self._method, self._provenance)
            text = f'Parametry wyniku {label}: {parameter_summary(used)}.'
            if used != current:
                text += ('\nBieżące ustawienia różnią się od użytych w wyniku. '
                         f'Następne obliczenie: {parameter_summary(current)}. '
                         'Dotychczasowy wynik pozostaje zachowany.')
        self.setText(text)
        self.show()


def movie_parameter_context(result: RegistrationResult, index: int
                            ) -> tuple[str, tuple[tuple[str, str], ...] | None]:
    if result.graph_application is not None:
        config = result.graph_application.graph.config
        return config.method, config.backend_settings
    diagnostics = result.correspondence_diagnostics
    detail = diagnostics[index] if diagnostics else None
    if detail is None:
        detail = next((item for item in diagnostics if item is not None), None)
    return result.method, detail.model_provenance if detail is not None else None
