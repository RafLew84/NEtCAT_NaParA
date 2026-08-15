from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from moltrack.analysis import (
    FirstShellGraphSettings,
    FirstShellGeometryExperimentSettings,
    FirstShellPairCorrelationEvidence,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainPartitionLabels,
    MolecularM6OrientationAnalysisSettings,
    run_lattice_domain_calibration_campaign,
    run_first_shell_geometry_experiment,
)
from moltrack.analysis.m6_calibration_campaign_models import (
    M6CalibrationBackend,
    M6CalibrationGroupPrediction,
    M6CalibrationObjective,
    M6CalibrationReferenceGroup,
)
from moltrack.analysis.m6_calibration_metrics import (
    evaluate_m6_calibration_prediction,
)
from moltrack.analysis.domain_analysis import (
    DomainBackendIdentity,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from moltrack.analysis.domain_analysis.backend_contract import NativeEvidenceKind
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


def test_campaign_ranks_source_aligned_partitions_with_constraints(tmp_path) -> None:
    package = _reference_package(tmp_path)
    observed: dict[str, list[tuple[str, str, float]]] = {
        M6_ORIENTATION_COMPONENTS_BACKEND_ID: [],
        M3_M6_LATTICE_NETWORK_BACKEND_ID: [],
    }

    def backend(backend_id: str, *, explicit_boundary: bool) -> M6CalibrationBackend:
        native_kind = (
            "m6_orientation_evidence_v1"
            if backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
            else "m3_m6_lattice_evidence_v1"
        )
        identity = DomainBackendIdentity(
            backend_id=backend_id,
            result_schema_version="domain-backend-result-v1",
            algorithm_version="campaign-fixture-v1",
            settings_fingerprint="fixture-settings",
            adapter_owner="campaign-fixture",
            native_evidence_kind=cast(NativeEvidenceKind, native_kind),
            capabilities=(
                ("common_partition", "explicit_boundary")
                if explicit_boundary
                else ("common_partition",)
            ),
        )

        def evaluate(group, settings, geometry):
            assert geometry.dataset_version_id == group.dataset_version_id
            observed[backend_id].append(
                (
                    group.dataset_version_id,
                    group.measurement_group_id,
                    settings.q_grow,
                )
            )
            reference = group.reference_labels
            low_recall_stable = settings.q_grow >= 0.5
            labels = []
            boundary = []
            failed_stages = []
            for source_id in reference.source_ids:
                molecule_id = source_id.rsplit("::", 1)[-1]
                if not low_recall_stable:
                    labels.append("different-local-domain-id")
                    boundary.append(False)
                    continue
                if group.measurement_group_id == "group-a":
                    predicted_positive = molecule_id == "p1"
                    labels.append("predicted-a" if predicted_positive else None)
                    boundary.append(predicted_positive)
                    if molecule_id == "p2":
                        failed_stages.append(
                            (source_id, ("local_order", "first_shell"))
                        )
                else:
                    labels.append(
                        "predicted-b-left"
                        if molecule_id in {"p3", "p4"}
                        else "predicted-b-right"
                    )
                    boundary.append(molecule_id == "p3")
            for source_id in group.excluded_source_ids:
                labels.append("must-not-enter-any-metric")
                boundary.append(False)
            return M6CalibrationGroupPrediction(
                labels=LatticeDomainPartitionLabels(
                    source_ids=(
                        *reference.source_ids,
                        *group.excluded_source_ids,
                    ),
                    domain_labels=tuple(labels),
                    boundary=tuple(boundary),
                    confidence=tuple(None for _ in labels),
                ),
                failed_stage_ids=tuple(failed_stages),
            )

        return M6CalibrationBackend(identity, evaluate)

    sweep = LatticeDomainCalibrationSweepSettings(
        baseline_settings=replace(
            MolecularM6OrientationAnalysisSettings(),
            q_grow=0.5,
        ),
        parameter_names=("q_grow",),
        max_multivariate_variants=0,
        max_stability_candidates=3,
    )
    geometry = run_first_shell_geometry_experiment(
        package.package_path,
        FirstShellGeometryExperimentSettings(
            graph_settings=FirstShellGraphSettings(duplicate_max_distance_nm=0.5),
            fixed_r_min_nm=1.0,
            fixed_r_max_nm=2.6,
            gr_bin_width_nm=0.5,
            gr_max_nm=3.0,
            gr_min_expected_pair_exposure=1.0,
            gr_min_contributing_frames=1,
            gr_smoothing_width=0.2,
            gr_peak_prominence=0.2,
        ),
        pair_correlations=(
            FirstShellPairCorrelationEvidence.unavailable(
                package.version_id,
                "group-a", "trifold", "fixture_has_no_g_r"
            ),
            FirstShellPairCorrelationEvidence.unavailable(
                package.version_id,
                "group-b", "sixfold", "fixture_has_no_g_r"
            ),
        ),
    ).freeze("fixed")
    report = run_lattice_domain_calibration_campaign(
        package.package_path,
        sweep,
        M6CalibrationObjective(
            minimum_membership_precision=0.9,
            minimum_local_stability_ari=0.8,
            split_weight=0.2,
            merge_weight=0.3,
        ),
        geometry=geometry,
        backends=(
            backend(M6_ORIENTATION_COMPONENTS_BACKEND_ID, explicit_boundary=False),
            backend(M3_M6_LATTICE_NETWORK_BACKEND_ID, explicit_boundary=True),
        ),
    )

    assert report.dataset_version_id == package.version_id
    assert report.dataset_version_fingerprint == package.version_fingerprint
    backend_results = report.backend_results_for(geometry)
    assert {value.backend_identity.backend_id for value in backend_results} == {
        M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        M3_M6_LATTICE_NETWORK_BACKEND_ID,
    }
    for backend_result in backend_results:
        selected = backend_result.selected_candidate
        assert selected is not None
        assert selected.variant.variant_id == "q_grow:high"
        assert selected.eligible is True
        assert selected.metrics.membership_true_positive_count == 5
        assert selected.metrics.membership_false_positive_count == 0
        assert selected.metrics.membership_false_negative_count == 1
        assert selected.metrics.abstention_count == 1
        assert selected.metrics.macro_membership_recall == pytest.approx(0.75)
        assert selected.metrics.micro_membership_recall == pytest.approx(5 / 6)
        assert selected.metrics.macro_split_rate == pytest.approx(0.5)
        assert selected.objective_loss == pytest.approx(0.35)
        assert selected.local_stability_ari == pytest.approx(1.0)
        assert selected.metrics.funnel_misses == (("first_shell", 1),)

        by_id = {
            value.variant.variant_id: value
            for value in backend_result.ranked_candidates
        }
        assert "local_stability_below_constraint" in by_id[
            "baseline"
        ].eligibility_failures
        assert "precision_below_constraint" in by_id[
            "q_grow:low"
        ].eligibility_failures
        if backend_result.backend_identity.backend_id == (
            M6_ORIENTATION_COMPONENTS_BACKEND_ID
        ):
            assert selected.metrics.boundary_precision.status == "unavailable"
            assert selected.metrics.boundary_precision.value is None
            assert selected.metrics.boundary_precision.reason == (
                "boundary_or_disordered_is_ambiguous"
            )
            assert all(
                value.boundary_true_positive_count is None
                and value.boundary_precision.status == "unavailable"
                for value in selected.group_metrics
            )
        else:
            assert selected.metrics.boundary_precision.status == "available"
            assert selected.metrics.boundary_precision.value == pytest.approx(1.0)
            assert selected.metrics.boundary_precision.reason is None
            assert all(
                value.boundary_true_positive_count is not None
                and value.boundary_precision.status == "available"
                for value in selected.group_metrics
            )

    for backend_observations in observed.values():
        assert {value[0] for value in backend_observations} == {package.version_id}
        assert {value[1] for value in backend_observations} == {
            "group-a",
            "group-b",
        }
        assert "validation-secret" not in {value[1] for value in backend_observations}
        assert {round(value[2], 2) for value in backend_observations} >= {
            0.45,
            0.5,
            0.55,
            0.6,
        }


def test_group_metrics_keep_frame_local_ids_separate_and_exclude_abstentions() -> None:
    group = M6CalibrationReferenceGroup(
        dataset_version_id="dataset-v1",
        measurement_group_id="two-frames",
        reference_labels=LatticeDomainPartitionLabels(
            source_ids=("frame-a::a", "frame-a::b", "frame-b::a", "frame-b::b"),
            domain_labels=(
                "frame-a::manual-1",
                "frame-a::manual-1",
                "frame-b::manual-1",
                "frame-b::manual-1",
            ),
            boundary=(False, False, False, False),
            confidence=(None, None, None, None),
        ),
        reference_boundary_available=False,
        abstention_count=1,
        excluded_source_ids=("frame-a::uncertain",),
    )
    metrics = evaluate_m6_calibration_prediction(
        group,
        M6CalibrationGroupPrediction(LatticeDomainPartitionLabels(
            source_ids=(
                *group.reference_labels.source_ids,
                "frame-a::uncertain",
            ),
            domain_labels=("local-1", "local-1", "local-1", "local-1", "local-1"),
            boundary=(False, False, False, False, False),
            confidence=(None, None, None, None, None),
        )),
        explicit_boundary=False,
    )

    assert metrics.adjusted_rand_index == pytest.approx(1.0)
    assert metrics.correctly_assigned_molecule_fraction == pytest.approx(1.0)
    assert metrics.membership_false_positive_count == 0
    assert metrics.evaluated_molecule_count == 4
    assert metrics.boundary_true_positive_count is None
    assert metrics.boundary_precision.status == "unavailable"


def _reference_package(tmp_path):
    rows = {
        name: [] for name in M6_REFERENCE_TABLE_FILES
    }
    rows["measurements.jsonl"] = [
        {"measurement_group_id": "group-a", "split": "calibration"},
        {"measurement_group_id": "group-b", "split": "calibration"},
        {"measurement_group_id": "validation-secret", "split": "validation"},
    ]
    rows["m6_assignments.jsonl"] = [
        *_assignment_rows(
            "group-a",
            "calibration",
            "frame-a",
            (("p1", "manual-a", True), ("p2", "manual-a", False), ("n1", None, False)),
        ),
        *_assignment_rows(
            "group-b",
            "calibration",
            "frame-b",
            (
                ("p3", "manual-b", True),
                ("p4", "manual-b", False),
                ("p5", "manual-b", False),
                ("p6", "manual-b", False),
            ),
        ),
        *_assignment_rows(
            "validation-secret",
            "validation",
            "frame-secret",
            (("secret", "manual-secret", False),),
        ),
    ]
    rows["m6_assignments.jsonl"].append({
        "measurement_group_id": "group-a",
        "split": "calibration",
        "physical_frame_id": "frame-a",
        "source_id": "uncertain",
        "effective_m6_partition": "full_domain",
        "effective_domain_id": "automatic-only",
        "effective_boundary": False,
        "review_eligibility": "eligible",
        "review_disposition": "rejected",
        "review_abstention": "uncertain",
        "review_reason_code": "ambiguous-manual-membership",
    })
    rows["frames.jsonl"] = [
        {
            "measurement_group_id": group_id,
            "split": split,
            "physical_frame_id": frame_id,
            "working_frame_index": frame_index,
            "first_shell_symmetry_class": symmetry,
        }
        for group_id, split, frame_id, frame_index, symmetry in (
            ("group-a", "calibration", "frame-a", 0, "trifold"),
            ("group-b", "calibration", "frame-b", 1, "sixfold"),
            ("validation-secret", "validation", "frame-secret", 2, "sixfold"),
        )
    ]
    coordinates = {
        "p1": (0.0, 0.0), "p2": (1.0, 0.0), "n1": (2.0, 0.0),
        "uncertain": (3.0, 0.0), "p3": (0.0, 0.0), "p4": (1.0, 0.0),
        "p5": (2.0, 0.0), "p6": (3.0, 0.0), "secret": (0.0, 0.0),
    }
    rows["source_geometry.jsonl"] = [
        {
            "measurement_group_id": row["measurement_group_id"],
            "split": row["split"],
            "physical_frame_id": row["physical_frame_id"],
            "source_id": row["source_id"],
            "point_xy_nm": list(coordinates[row["source_id"]]),
            "coordinate_transform_fingerprint": "calibration-v1",
            "registration_fingerprint": "unregistered",
        }
        for row in rows["m6_assignments.jsonl"]
    ]
    rows["m6_first_shell_edges.jsonl"] = [
        {
            "measurement_group_id": group_id,
            "split": "calibration",
            "physical_frame_id": frame_id,
            "source_id_a": left,
            "source_id_b": right,
            "distance_nm": 1.0,
        }
        for group_id, frame_id, left, right in (
            ("group-a", "frame-a", "p1", "p2"),
            ("group-b", "frame-b", "p3", "p4"),
        )
    ]
    settings = ReferenceDatasetSettings(
        destination=tmp_path / "m6-reference",
        dataset_id="campaign-reference",
        publication_reason="campaign tracer",
    )
    return publish_reference_dataset(ReferenceDatasetDraft(
        target="m6",
        settings=settings,
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
                    "m6", split, rows
                ),
            )
            for split in ("calibration", "validation")
        ),
    ))


def _assignment_rows(group_id, split, frame_id, values):
    return [
        {
            "measurement_group_id": group_id,
            "split": split,
            "physical_frame_id": frame_id,
            "source_id": source_id,
            "effective_m6_partition": (
                "full_domain" if domain_id is not None else "outside"
            ),
            "effective_domain_id": domain_id,
            "effective_boundary": boundary,
            "review_eligibility": "eligible",
            "review_disposition": "accepted_automatic",
            "review_abstention": None,
            "review_reason_code": None,
        }
        for source_id, domain_id, boundary in values
    ]
