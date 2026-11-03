from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, cast

import pytest

from moltrack.analysis import (
    FirstShellGraphSettings,
    FirstShellGeometryExperimentSettings,
    FirstShellPairCorrelationEvidence,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainPartitionLabels,
    MolecularM6OrientationAnalysisSettings,
    PairCorrelationResult,
    run_first_shell_geometry_experiment,
    run_lattice_domain_calibration_campaign,
)
from moltrack.analysis.domain_analysis import (
    DomainBackendIdentity,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from moltrack.analysis.domain_analysis.backend_contract import NativeEvidenceKind
from moltrack.analysis.m6_calibration_campaign_models import (
    M6CalibrationBackend,
    M6CalibrationObjective,
)
from moltrack.persistence.m6_calibration_reference import load_m6_calibration_tables
from moltrack.persistence.m6_reference_payload import M6_REFERENCE_TABLE_FILES
from moltrack.persistence.reference_dataset import (
    ReferenceDatasetDraft,
    ReferenceDatasetSettings,
    ReferencePartitionIdentity,
    publish_reference_dataset,
    reference_json_lines_file,
)
from moltrack.persistence.reference_dataset_identity import (
    reference_partition_fingerprint,
)


def test_operator_compares_and_freezes_first_shell_geometry_on_calibration(
    tmp_path,
) -> None:
    package = _reference_package(tmp_path)
    calibration = load_m6_calibration_tables(package.package_path)
    assert not hasattr(calibration, "package")
    assert all(
        row["split"] == "calibration"
        for rows in calibration.tables.values()
        for row in rows
    )
    assert "validation-secret" not in repr(calibration.tables)
    settings = FirstShellGeometryExperimentSettings(
        graph_settings=FirstShellGraphSettings(duplicate_max_distance_nm=0.25),
        fixed_r_min_nm=0.5,
        fixed_r_max_nm=1.2,
        gr_bin_width_nm=0.5,
        gr_max_nm=3.0,
        gr_min_expected_pair_exposure=1.0,
        gr_min_contributing_frames=1,
        gr_smoothing_width=0.2,
        gr_peak_prominence=0.2,
    )
    evidence = (
        FirstShellPairCorrelationEvidence.available(
            package.version_id,
            "group-sixfold",
            "sixfold",
            _pair_correlation(settings),
        ),
        FirstShellPairCorrelationEvidence.unavailable(
            package.version_id,
            "group-trifold",
            "trifold",
            "pair_correlation_capability_unavailable",
        ),
    )

    report = run_first_shell_geometry_experiment(
        package.package_path,
        settings,
        pair_correlations=evidence,
    )
    repeated = run_first_shell_geometry_experiment(
        package.package_path,
        settings,
        pair_correlations=evidence,
    )

    assert report.dataset_version_id == package.version_id
    assert report.validation_epoch_id == package.validation_epoch_id
    assert report.validation_opened is False
    assert report.experiment_fingerprint == repeated.experiment_fingerprint
    assert {value.policy.mode for value in report.policy_results} == {
        "fixed",
        "adaptive",
    }

    fixed = report.result("fixed")
    adaptive = report.result("adaptive")
    fixed_sixfold = fixed.metric("group-sixfold", "sixfold")
    adaptive_sixfold = adaptive.metric("group-sixfold", "sixfold")
    assert fixed_sixfold.reference_edge_count == 3
    assert fixed_sixfold.predicted_edge_count == 1
    assert fixed_sixfold.precision == pytest.approx(1.0)
    assert fixed_sixfold.recall == pytest.approx(1 / 3)
    assert fixed_sixfold.f1_score == pytest.approx(0.5)
    assert adaptive_sixfold.true_positive_edge_count == 3
    assert adaptive_sixfold.precision == pytest.approx(1.0)
    assert adaptive_sixfold.recall == pytest.approx(1.0)
    assert adaptive_sixfold.f1_score == pytest.approx(1.0)

    suggested = adaptive.decision("group-sixfold", "sixfold")
    assert suggested.resolution == "adaptive_g_r"
    assert suggested.resolved_r_max_nm == pytest.approx(2.25)
    assert suggested.fallback_reason is None
    fallback = adaptive.decision("group-trifold", "trifold")
    assert fallback.resolution == "fixed_fallback"
    assert fallback.resolved_r_max_nm == pytest.approx(1.2)
    assert fallback.fallback_reason == "pair_correlation_capability_unavailable"

    selection = report.freeze("adaptive")
    assert selection.policy.mode == "adaptive"
    assert selection.dataset_version_id == package.version_id
    assert selection.geometry_fingerprint
    assert selection.geometry_fingerprint != selection.policy.policy_fingerprint
    assert selection.validation_opened is False
    with pytest.raises(ValueError, match="Unknown first-shell policy"):
        report.freeze(cast(Any, "missing"))

    foreign_evidence = (
        replace(evidence[0], dataset_version_id="foreign-version"),
        evidence[1],
    )
    with pytest.raises(ValueError, match="immutable dataset version"):
        run_first_shell_geometry_experiment(
            package.package_path,
            settings,
            pair_correlations=foreign_evidence,
        )

    mismatched_context = (
        replace(
            evidence[0],
            pair_correlation=replace(
                evidence[0].pair_correlation,
                registration_fingerprint="foreign-registration",
            ),
        ),
        evidence[1],
    )
    with pytest.raises(ValueError, match=r"g\(r\).*reference geometry"):
        run_first_shell_geometry_experiment(
            package.package_path,
            settings,
            pair_correlations=mismatched_context,
        )


def test_geometry_fingerprint_invalidates_campaign_search_and_selection(
    tmp_path,
) -> None:
    package = _reference_package(tmp_path)
    settings = FirstShellGeometryExperimentSettings(
        graph_settings=FirstShellGraphSettings(duplicate_max_distance_nm=0.25),
        fixed_r_min_nm=0.5,
        fixed_r_max_nm=1.2,
        gr_bin_width_nm=0.5,
        gr_max_nm=3.0,
        gr_min_expected_pair_exposure=1.0,
        gr_min_contributing_frames=1,
        gr_smoothing_width=0.2,
        gr_peak_prominence=0.2,
    )
    evidence = (
        FirstShellPairCorrelationEvidence.available(
            package.version_id,
            "group-sixfold", "sixfold", _pair_correlation(settings)
        ),
        FirstShellPairCorrelationEvidence.unavailable(
            package.version_id,
            "group-trifold",
            "trifold",
            "pair_correlation_capability_unavailable",
        ),
    )
    selected = run_first_shell_geometry_experiment(
        package.package_path,
        settings,
        pair_correlations=evidence,
    ).freeze("adaptive")
    changed = run_first_shell_geometry_experiment(
        package.package_path,
        replace(settings, gr_peak_prominence=0.3),
        pair_correlations=evidence,
    ).freeze("adaptive")
    sweep = LatticeDomainCalibrationSweepSettings(
        baseline_settings=replace(
            MolecularM6OrientationAnalysisSettings(),
            duplicate_max_distance_nm=0.25,
            first_shell_r_min_nm=0.5,
            first_shell_r_max_nm=1.2,
        ),
        parameter_names=("q_grow",),
        max_multivariate_variants=0,
        max_stability_candidates=1,
    )
    report = run_lattice_domain_calibration_campaign(
        package.package_path,
        sweep,
        M6CalibrationObjective(0.5, 0.5, 0.2, 0.2),
        geometry=selected,
        backends=(
            _backend(M6_ORIENTATION_COMPONENTS_BACKEND_ID),
            _backend(M3_M6_LATTICE_NETWORK_BACKEND_ID),
        ),
    )

    assert report.geometry_fingerprint == selected.geometry_fingerprint
    assert len(report.backend_results_for(selected)) == 2
    assert changed.geometry_fingerprint != selected.geometry_fingerprint
    with pytest.raises(ValueError, match="geometry fingerprint changed"):
        report.backend_results_for(changed)
    assert not hasattr(report, "backend_results")

    incompatible_sweep = replace(
        sweep,
        baseline_settings=replace(
            sweep.baseline_settings,
            duplicate_max_distance_nm=0.2,
        ),
    )
    with pytest.raises(ValueError, match="graph settings"):
        run_lattice_domain_calibration_campaign(
            package.package_path,
            incompatible_sweep,
            M6CalibrationObjective(0.5, 0.5, 0.2, 0.2),
            geometry=selected,
            backends=(
                _backend(M6_ORIENTATION_COMPONENTS_BACKEND_ID),
                _backend(M3_M6_LATTICE_NETWORK_BACKEND_ID),
            ),
        )


def _backend(backend_id: str) -> M6CalibrationBackend:
    native_kind = (
        "m6_orientation_evidence_v1"
        if backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
        else "m3_m6_lattice_evidence_v1"
    )
    identity = DomainBackendIdentity(
        backend_id=backend_id,
        result_schema_version="domain-backend-result-v1",
        algorithm_version="geometry-campaign-fixture-v1",
        settings_fingerprint="fixture-settings",
        adapter_owner="geometry-campaign-fixture",
        native_evidence_kind=cast(NativeEvidenceKind, native_kind),
        capabilities=("common_partition",),
    )

    def evaluate(group, _settings, geometry):
        assert geometry.dataset_version_id == group.dataset_version_id
        labels = group.reference_labels
        return LatticeDomainPartitionLabels(
            source_ids=labels.source_ids,
            domain_labels=tuple("predicted" for _ in labels.source_ids),
            boundary=tuple(False for _ in labels.source_ids),
            confidence=tuple(None for _ in labels.source_ids),
        )

    return M6CalibrationBackend(identity, evaluate)


def _reference_package(tmp_path):
    rows = {name: [] for name in M6_REFERENCE_TABLE_FILES}
    rows["measurements.jsonl"] = [
        {"measurement_group_id": "group-sixfold", "split": "calibration"},
        {"measurement_group_id": "group-trifold", "split": "calibration"},
        {"measurement_group_id": "validation-secret", "split": "validation"},
    ]
    frames = (
        ("group-sixfold", "calibration", "frame-six", 0, "sixfold"),
        ("group-trifold", "calibration", "frame-three", 1, "trifold"),
        ("validation-secret", "validation", "frame-secret", 2, "sixfold"),
    )
    rows["frames.jsonl"] = [
        {
            "measurement_group_id": group_id,
            "split": split,
            "physical_frame_id": frame_id,
            "working_frame_index": frame_index,
            "first_shell_symmetry_class": symmetry,
        }
        for group_id, split, frame_id, frame_index, symmetry in frames
    ]
    points = (
        ("group-sixfold", "calibration", "frame-six", "a", (0.0, 0.0)),
        ("group-sixfold", "calibration", "frame-six", "b", (1.0, 0.0)),
        ("group-sixfold", "calibration", "frame-six", "c", (0.8, 1.4)),
        ("group-trifold", "calibration", "frame-three", "d", (0.0, 0.0)),
        ("group-trifold", "calibration", "frame-three", "e", (1.0, 0.0)),
        ("group-trifold", "calibration", "frame-three", "f", (3.0, 0.0)),
        ("validation-secret", "validation", "frame-secret", "secret-a", (0.0, 0.0)),
        ("validation-secret", "validation", "frame-secret", "secret-b", (1.0, 0.0)),
    )
    rows["source_geometry.jsonl"] = [
        {
            "measurement_group_id": group_id,
            "split": split,
            "physical_frame_id": frame_id,
            "source_id": source_id,
            "point_xy_nm": list(point_xy_nm),
            "coordinate_transform_fingerprint": "calibration-v1",
            "registration_fingerprint": "registration-v1",
        }
        for group_id, split, frame_id, source_id, point_xy_nm in points
    ]
    rows["m6_assignments.jsonl"] = [
        {
            "measurement_group_id": group_id,
            "split": split,
            "physical_frame_id": frame_id,
            "source_id": source_id,
            "effective_m6_partition": "full_domain",
            "effective_domain_id": f"domain-{frame_id}",
            "effective_boundary": False,
            "review_eligibility": "eligible",
            "review_disposition": "accepted_automatic",
            "review_abstention": None,
            "review_reason_code": None,
        }
        for group_id, split, frame_id, source_id, _point in points
    ]
    edges = (
        ("group-sixfold", "calibration", "frame-six", "a", "b"),
        ("group-sixfold", "calibration", "frame-six", "a", "c"),
        ("group-sixfold", "calibration", "frame-six", "b", "c"),
        ("group-trifold", "calibration", "frame-three", "d", "e"),
        ("validation-secret", "validation", "frame-secret", "secret-a", "secret-b"),
    )
    rows["m6_first_shell_edges.jsonl"] = [
        {
            "measurement_group_id": group_id,
            "split": split,
            "physical_frame_id": frame_id,
            "source_id_a": source_id_a,
            "source_id_b": source_id_b,
            "distance_nm": math.dist(
                next(point for group, _, frame, source, point in points if (group, frame, source) == (group_id, frame_id, source_id_a)),
                next(point for group, _, frame, source, point in points if (group, frame, source) == (group_id, frame_id, source_id_b)),
            ),
        }
        for group_id, split, frame_id, source_id_a, source_id_b in edges
    ]
    return publish_reference_dataset(ReferenceDatasetDraft(
        target="m6",
        settings=ReferenceDatasetSettings(
            destination=tmp_path / "m6-geometry-reference",
            dataset_id="geometry-reference",
            publication_reason="geometry tracer",
        ),
        initial_dataset_version=1,
        payload_files=tuple(
            reference_json_lines_file(name, rows[name])
            for name in M6_REFERENCE_TABLE_FILES
        ),
        partitions=tuple(
            ReferencePartitionIdentity(
                split=split,
                measurement_group_count=(2 if split == "calibration" else 1),
                partition_fingerprint=reference_partition_fingerprint(
                    "m6",
                    split,
                    rows,
                ),
            )
            for split in ("calibration", "validation")
        ),
    ))


def _pair_correlation(
    settings: FirstShellGeometryExperimentSettings,
) -> PairCorrelationResult:
    from moltrack.analysis.first_shell_builder import build_first_shell_graph

    points = ((0.0, 0.0), (1.0, 0.0), (0.8, 1.4))
    point_ids = ("a", "b", "c")
    graph = build_first_shell_graph(
        points,
        point_ids=point_ids,
        settings=MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=settings.graph_settings.duplicate_max_distance_nm,
            first_shell_r_min_nm=settings.fixed_r_min_nm,
            first_shell_r_max_nm=settings.fixed_r_max_nm,
            geometry_absolute_tolerance_nm=(
                settings.graph_settings.geometry_absolute_tolerance_nm
            ),
            geometry_relative_tolerance=settings.graph_settings.geometry_relative_tolerance,
            gr_bin_width_nm=settings.gr_bin_width_nm,
            gr_max_nm=settings.gr_max_nm,
            gr_min_expected_pair_exposure=settings.gr_min_expected_pair_exposure,
            gr_min_contributing_frames=settings.gr_min_contributing_frames,
            gr_smoothing_method=settings.gr_smoothing_method,
            gr_smoothing_width=settings.gr_smoothing_width,
            gr_peak_prominence=settings.gr_peak_prominence,
        ),
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
    )
    g_values = (0.0, 0.0, 2.0, 0.0, 0.0, 0.5)
    exposure = (2.0, 2.0, 1.0, 2.0, 2.0, 2.0)
    observed = (0, 0, 2, 0, 0, 1)
    edges = tuple(index * 0.5 for index in range(len(g_values) + 1))
    return PairCorrelationResult(
        bin_edges_nm=edges,
        bin_centers_nm=tuple((left + right) / 2 for left, right in zip(edges, edges[1:])),
        g_r=g_values,
        observed_unordered_pair_count=observed,
        expected_pair_exposure=exposure,
        bin_status=cast(Any, ("valid",) * len(g_values)),
        contributing_frame_count=(1,) * len(g_values),
        point_count=3,
        total_unordered_pair_count=3,
        min_expected_pair_exposure=1.0,
        window_area_nm2=100.0,
        window_geometry_status="rectangular_translation_correction",
        frame_index=0,
        representative_point_ids=point_ids,
        coordinate_frame="sample_nm",
        spatial_calibration_fingerprint=graph.spatial_calibration_fingerprint,
        registration_fingerprint=graph.registration_fingerprint,
        point_coordinate_fingerprint=graph.point_coordinate_fingerprint,
        window_origin_nm=(0.0, 0.0),
    )
