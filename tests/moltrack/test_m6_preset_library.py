from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    FirstShellGeometryPolicy,
    FirstShellGeometrySelectionRecord,
    M6OrientationComponentsEvidence,
    M6Preset,
    M6PresetLibrary,
    M6RunConfiguration,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisSessionState,
    DomainBackendIdentity,
    M6CanonicalFrame,
    M6FrameComputation,
    M6FrameGeometry,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from moltrack.persistence.domain_analysis_session import (
    domain_analysis_state_from_payload,
    domain_analysis_state_to_payload,
)


_NOW = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)


def _configuration(*, q_seed: float = 0.65) -> M6RunConfiguration:
    settings = replace(TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET, q_seed=q_seed)
    identity = DomainBackendIdentity(
        backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        result_schema_version="domain-backend-result-v1",
        algorithm_version="moltrack-m6-orientation-v1",
        settings_fingerprint=m6_settings_fingerprint(settings),
        adapter_owner="preset-test-adapter",
        native_evidence_kind="m6_orientation_evidence_v1",
        capabilities=("common_partition",),
    )
    return M6RunConfiguration(
        backend_identity=identity,
        settings=settings,
        first_shell_geometry=FirstShellGeometryPolicy.fixed(
            r_min_nm=settings.first_shell_r_min_nm,
            r_max_nm=settings.first_shell_r_max_nm,
        ),
    )


def _built_in() -> M6Preset:
    return M6Preset(
        name="TTMAPP M6",
        description="Shipped default",
        configuration=_configuration(),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )


def test_library_saves_and_restores_exactly_one_active_preset(tmp_path) -> None:
    path = tmp_path / "m6-presets.json"
    library = M6PresetLibrary(
        path,
        built_in_presets=(_built_in(),),
        clock=lambda: _NOW,
    )
    draft = library.new(
        "Sensitive M6",
        _configuration(q_seed=0.72),
        description="Operator choice",
    )

    saved = library.save(draft)
    assert library.snapshot.active_preset.name == "TTMAPP M6"

    library.set_active(saved.name)
    restored = M6PresetLibrary(
        path,
        built_in_presets=(_built_in(),),
        clock=lambda: _NOW,
    )

    assert restored.snapshot.active_preset == saved
    assert tuple(value.name for value in restored.snapshot.presets) == (
        "Sensitive M6",
        "TTMAPP M6",
    )
    assert restored.active_run_configuration() == saved.configuration
    assert saved.configuration.configuration_fingerprint != (
        _built_in().configuration.configuration_fingerprint
    )


class _ConfigurableAdapter:
    def __init__(
        self,
        configuration: M6RunConfiguration,
        observed: list[M6RunConfiguration],
    ) -> None:
        self.configuration = configuration
        self.backend_identity = configuration.backend_identity
        self._observed = observed

    def for_run(self, configuration: M6RunConfiguration) -> _ConfigurableAdapter:
        return _ConfigurableAdapter(configuration, self._observed)

    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        self._observed.append(self.configuration)
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=(),
            small_ordered_islands=(),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            backend_identity=self.backend_identity,
            native_evidence=M6OrientationComponentsEvidence((), ()),
        )


def test_run_uses_frozen_configuration_after_library_activation_changes(
    tmp_path,
) -> None:
    first = _built_in()
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(first,),
        clock=lambda: _NOW,
    )
    second = library.save(library.new("Sensitive M6", _configuration(q_seed=0.72)))
    frozen = library.active_run_configuration()
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id=frozen.backend_id,
        m6_configuration=frozen,
    )
    library.set_active(second.name)
    observed: list[M6RunConfiguration] = []
    adapter = _ConfigurableAdapter(first.configuration, observed)
    module = DomainAnalysisModule(
        {M6_ORIENTATION_COMPONENTS_BACKEND_ID: adapter},
        {},
    )

    result = module.run(_series(), request)

    assert observed == [frozen]
    assert result.run_status == "completed"
    assert result.m6_gate is not None
    assert result.m6_gate.frames[0].backend_identity == frozen.backend_identity
    assert request.m6_configuration is frozen
    assert library.active_run_configuration() == second.configuration

    state = DomainAnalysisSessionState(
        draft=request,
        draft_physical_frame_ids=("frame-0",),
        published_result=DomainAnalysisPublication(request, result),
    )
    restored = domain_analysis_state_from_payload(
        domain_analysis_state_to_payload(state)
    )

    assert restored.draft is not None
    assert restored.draft.m6_configuration == frozen
    assert restored.published_result is not None
    assert restored.published_result.request.m6_configuration == frozen


def test_configurable_backend_rejects_run_without_frozen_configuration() -> None:
    configuration = _configuration()
    module = DomainAnalysisModule(
        {
            M6_ORIENTATION_COMPONENTS_BACKEND_ID: _ConfigurableAdapter(
                configuration,
                [],
            )
        },
        {},
    )
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    )

    with pytest.raises(ValueError, match="frozen M6 configuration"):
        module.run(_series(), request)


def test_configuration_fingerprint_isolates_m6_cache() -> None:
    first = _configuration()
    revised_policy = FirstShellGeometryPolicy(
        mode="fixed",
        fixed_r_min_nm=first.settings.first_shell_r_min_nm,
        fixed_r_max_nm=first.settings.first_shell_r_max_nm,
        algorithm_version="fixed-physical-range-v2",
    )
    second = M6RunConfiguration(
        backend_identity=first.backend_identity,
        settings=first.settings,
        first_shell_geometry=revised_policy,
    )
    observed: list[M6RunConfiguration] = []
    module = DomainAnalysisModule(
        {
            M6_ORIENTATION_COMPONENTS_BACKEND_ID: _ConfigurableAdapter(
                first,
                observed,
            )
        },
        {},
    )

    for configuration in (first, second):
        module.run(
            _series(),
            DomainAnalysisRequest(
                frame_range=range(1),
                backend_id=configuration.backend_id,
                m6_configuration=configuration,
            ),
        )

    assert observed == [first, second]


def test_adaptive_first_shell_policy_is_an_executable_frozen_configuration() -> None:
    fixed = _configuration()
    adaptive = FirstShellGeometryPolicy(
        mode="adaptive",
        fixed_r_min_nm=fixed.settings.first_shell_r_min_nm,
        fixed_r_max_nm=fixed.settings.first_shell_r_max_nm,
        algorithm_version="adaptive-first-shell-v1",
        adaptive_parameters=(("smoothing_window", 5),),
    )

    configuration = M6RunConfiguration(
        backend_identity=fixed.backend_identity,
        settings=fixed.settings,
        first_shell_geometry=adaptive,
    )

    assert configuration.first_shell_geometry == adaptive
    assert configuration.configuration_fingerprint != fixed.configuration_fingerprint


def test_library_explicitly_saves_adaptive_geometry_selection_as_active(
    tmp_path,
) -> None:
    fixed = _configuration()
    adaptive = FirstShellGeometryPolicy(
        mode="adaptive",
        fixed_r_min_nm=fixed.settings.first_shell_r_min_nm,
        fixed_r_max_nm=fixed.settings.first_shell_r_max_nm,
        algorithm_version="adaptive-first-shell-v1",
        adaptive_parameters=(("smoothing_window", 5),),
    )
    record = FirstShellGeometrySelectionRecord(
        dataset_version_id="dataset-v1",
        dataset_version_fingerprint="dataset-fingerprint",
        validation_epoch_id="validation-epoch",
        experiment_fingerprint="experiment-fingerprint",
        geometry_fingerprint="geometry-fingerprint",
        policy_fingerprint=adaptive.policy_fingerprint,
        policy_result_fingerprint="policy-result-fingerprint",
        evidence_fingerprints=(("group-a", "sixfold", "evidence-fingerprint"),),
    )
    configuration = M6RunConfiguration(
        backend_identity=fixed.backend_identity,
        settings=fixed.settings,
        first_shell_geometry=adaptive,
        first_shell_geometry_selection=record,
    )
    path = tmp_path / "m6-presets.json"
    library = M6PresetLibrary(
        path,
        built_in_presets=(_built_in(),),
        clock=lambda: _NOW,
    )

    saved = library.save_as_active(
        "Adaptive Calibration geometry",
        configuration,
        description="Explicit operator Save As",
    )
    restored = M6PresetLibrary(
        path,
        built_in_presets=(_built_in(),),
        clock=lambda: _NOW,
    )

    assert library.snapshot.active_preset == saved
    assert restored.snapshot.active_preset.configuration == configuration
    assert (
        restored.active_run_configuration().first_shell_geometry_selection
        == record
    )


def _series() -> DomainAnalysisSeries:
    return DomainAnalysisSeries((DomainAnalysisFrame(
        frame_index=0,
        source_view="raw",
        geometry=M6FrameGeometry(
            physical_frame_id="frame-0",
            raw_shape=(4, 4),
            expanded_shape=(4, 4),
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            pixel_size_nm=(1.0, 1.0),
            scan_angle_deg=0.0,
            registration_fingerprint="unregistered",
        ),
        annotations=(),
    ),))
