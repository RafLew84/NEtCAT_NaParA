from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import cast

import pytest

from moltrack.analysis import (
    FirstShellGraphSettings,
    FirstShellGeometryExperimentSettings,
    FirstShellPairCorrelationEvidence,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainPartitionLabels,
    MolecularM6OrientationAnalysisSettings,
    freeze_m6_candidate_shortlist,
    open_m6_validation_and_publish_report,
    run_lattice_domain_calibration_campaign,
    run_first_shell_geometry_experiment,
)
from moltrack.analysis.m6_calibration_campaign_models import (
    M6CalibrationBackend,
    M6CalibrationBackendResult,
    M6CalibrationCampaignReport,
    M6CalibrationGroupPrediction,
    M6CalibrationObjective,
    M6CalibrationReferenceGroup,
)
from moltrack.analysis.first_shell_geometry_models import (
    FrozenFirstShellGeometrySelection,
)
from moltrack.analysis.m6_validation_campaign_models import (
    M6CampaignReportV2,
    M6CampaignReportV2Publication,
    M6CandidateShortlist,
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
    ReferenceDatasetPublication,
    ReferenceDatasetSettings,
    ReferencePartitionIdentity,
    publish_reference_dataset,
    reference_json_lines_file,
)
from moltrack.persistence.reference_dataset_identity import (
    reference_partition_fingerprint,
)


def test_campaign_ranks_source_aligned_partitions_with_constraints(tmp_path) -> None:
    scenario = _campaign_scenario(tmp_path, dataset_id="campaign-ranking")
    report = scenario.campaign
    assert report.dataset_version_id == scenario.package.version_id
    assert report.dataset_version_fingerprint == scenario.package.version_fingerprint
    backend_results = report.backend_results_for(scenario.geometry)
    assert {value.backend_identity.backend_id for value in backend_results} == {
        M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        M3_M6_LATTICE_NETWORK_BACKEND_ID,
    }
    for backend_result in backend_results:
        _assert_ranked_backend_result(backend_result)
    for observations in scenario.observed.values():
        assert {value[0] for value in observations} == {scenario.package.version_id}
        assert {value[1] for value in observations} == {"group-a", "group-b"}
        assert "validation-secret" not in {value[1] for value in observations}
        assert {round(value[2], 2) for value in observations} >= {
            0.45, 0.5, 0.55, 0.6,
        }


def test_shortlist_is_deterministic_and_binds_both_backends(tmp_path) -> None:
    scenario = _campaign_scenario(tmp_path, dataset_id="campaign-shortlist")
    shortlist = scenario.shortlist
    repeated = freeze_m6_candidate_shortlist(
        scenario.campaign,
        scenario.geometry,
    )
    assert shortlist.dataset_version_id == scenario.package.version_id
    assert shortlist.validation_epoch_id == scenario.package.validation_epoch_id
    assert shortlist.geometry_fingerprint == scenario.geometry.geometry_fingerprint
    assert shortlist.validation_opened is False
    assert shortlist.shortlist_fingerprint == repeated.shortlist_fingerprint
    assert {entry.backend_identity.backend_id for entry in shortlist.entries} == {
        M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        M3_M6_LATTICE_NETWORK_BACKEND_ID,
    }
    assert all(entry.candidate.eligible for entry in shortlist.entries)
    assert all(
        entry.candidate.variant.variant_id == "q_grow:high"
        for entry in shortlist.entries
    )
    assert shortlist.tie_break_rule


@pytest.mark.parametrize("validation_failure", [False, True])
def test_validation_publishes_positive_or_legal_negative_report(
    tmp_path,
    monkeypatch,
    validation_failure: bool,
) -> None:
    _configure_validation_registry(monkeypatch, tmp_path)
    scenario = _campaign_scenario(
        tmp_path,
        dataset_id=("campaign-report-failure" if validation_failure else "campaign-report"),
        validation_failure=validation_failure,
    )
    before = {key: len(values) for key, values in scenario.observed.items()}
    publication = _open_validation(scenario, tmp_path / "report")
    assert publication.report.status == (
        "validation_failed" if validation_failure else "validated"
    )
    assert publication.report.preset_modified is False
    assert publication.report.receipt.open_count == 1
    assert publication.report.receipt.shortlist_fingerprint == (
        scenario.shortlist.shortlist_fingerprint
    )
    if validation_failure:
        assert publication.report.recommended_backend_id is None
        assert publication.report.failure_reason is not None
    else:
        assert publication.report.recommended_backend_id in {
            M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            M3_M6_LATTICE_NETWORK_BACKEND_ID,
        }
    _assert_validation_metrics(publication.report, validation_failure)
    _assert_report_artifacts(publication)
    for backend_id, observations in scenario.observed.items():
        assert len(observations) == before[backend_id] + 1
        assert observations[-1][1] == "validation-secret"


def test_validation_access_is_global_one_shot_and_rejects_mismatch(
    tmp_path,
    monkeypatch,
) -> None:
    _configure_validation_registry(monkeypatch, tmp_path)
    scenario = _campaign_scenario(tmp_path, dataset_id="campaign-guard")
    _open_validation(scenario, tmp_path / "first-report-root")
    after_open = {key: len(values) for key, values in scenario.observed.items()}
    with pytest.raises(ValueError, match="already been opened"):
        _open_validation(scenario, tmp_path / "different-report-root")
    assert {key: len(values) for key, values in scenario.observed.items()} == after_open

    alternate = run_lattice_domain_calibration_campaign(
        scenario.package.package_path,
        scenario.sweep,
        replace(
            scenario.campaign.objective,
            minimum_membership_precision=0.89,
        ),
        geometry=scenario.geometry,
        backends=scenario.backends,
    )
    alternate_shortlist = freeze_m6_candidate_shortlist(
        alternate,
        scenario.geometry,
    )
    before_alternate = {
        key: len(values) for key, values in scenario.observed.items()
    }
    with pytest.raises(ValueError, match="identity mismatch"):
        open_m6_validation_and_publish_report(
            alternate,
            alternate_shortlist,
            scenario.geometry,
            backends=scenario.backends,
            destination=tmp_path / "alternate-objective-report",
        )
    assert {
        key: len(values) for key, values in scenario.observed.items()
    } == before_alternate
    _assert_pre_open_mismatches(scenario, tmp_path)


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


@dataclass(frozen=True)
class _CampaignScenario:
    package: ReferenceDatasetPublication
    observed: dict[str, list[tuple[str, str, float]]]
    backends: tuple[M6CalibrationBackend, ...]
    sweep: LatticeDomainCalibrationSweepSettings
    geometry: FrozenFirstShellGeometrySelection
    campaign: M6CalibrationCampaignReport
    shortlist: M6CandidateShortlist


def _campaign_scenario(
    tmp_path,
    *,
    dataset_id: str,
    validation_failure: bool = False,
) -> _CampaignScenario:
    package = _reference_package(tmp_path, dataset_id=dataset_id)
    observed: dict[str, list[tuple[str, str, float]]] = {
        M6_ORIENTATION_COMPONENTS_BACKEND_ID: [],
        M3_M6_LATTICE_NETWORK_BACKEND_ID: [],
    }
    backends = (
        _campaign_backend(
            M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            explicit_boundary=False,
            validation_failure=validation_failure,
            observed=observed,
        ),
        _campaign_backend(
            M3_M6_LATTICE_NETWORK_BACKEND_ID,
            explicit_boundary=True,
            validation_failure=validation_failure,
            observed=observed,
        ),
    )
    sweep = LatticeDomainCalibrationSweepSettings(
        baseline_settings=replace(
            MolecularM6OrientationAnalysisSettings(),
            q_grow=0.5,
        ),
        parameter_names=("q_grow",),
        max_multivariate_variants=0,
        max_stability_candidates=3,
    )
    geometry = _campaign_geometry(package)
    campaign = run_lattice_domain_calibration_campaign(
        package.package_path,
        sweep,
        M6CalibrationObjective(
            minimum_membership_precision=0.9,
            minimum_local_stability_ari=0.8,
            split_weight=0.2,
            merge_weight=0.3,
        ),
        geometry=geometry,
        backends=backends,
    )
    return _CampaignScenario(
        package=package,
        observed=observed,
        backends=backends,
        sweep=sweep,
        geometry=geometry,
        campaign=campaign,
        shortlist=freeze_m6_candidate_shortlist(campaign, geometry),
    )


def _campaign_backend(
    backend_id: str,
    *,
    explicit_boundary: bool,
    validation_failure: bool,
    observed: dict[str, list[tuple[str, str, float]]],
) -> M6CalibrationBackend:
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
        observed[backend_id].append((
            group.dataset_version_id,
            group.measurement_group_id,
            settings.q_grow,
        ))
        reference = group.reference_labels
        labels = []
        boundary = []
        failed_stages = []
        for source_id in reference.source_ids:
            molecule_id = source_id.rsplit("::", 1)[-1]
            if settings.q_grow < 0.5:
                labels.append("different-local-domain-id")
                boundary.append(False)
            elif validation_failure and group.measurement_group_id == (
                "validation-secret"
            ):
                labels.append(None)
                boundary.append(False)
                failed_stages.append((source_id, ("automatic_result",)))
            elif group.measurement_group_id == "group-a":
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
        for _source_id in group.excluded_source_ids:
            labels.append("must-not-enter-any-metric")
            boundary.append(False)
        return M6CalibrationGroupPrediction(
            labels=LatticeDomainPartitionLabels(
                source_ids=(*reference.source_ids, *group.excluded_source_ids),
                domain_labels=tuple(labels),
                boundary=tuple(boundary),
                confidence=tuple(None for _ in labels),
            ),
            failed_stage_ids=tuple(failed_stages),
        )

    return M6CalibrationBackend(identity, evaluate)


def _campaign_geometry(
    package: ReferenceDatasetPublication,
) -> FrozenFirstShellGeometrySelection:
    return run_first_shell_geometry_experiment(
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


def _assert_ranked_backend_result(result: M6CalibrationBackendResult) -> None:
    selected = result.selected_candidate
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
    by_id = {value.variant.variant_id: value for value in result.ranked_candidates}
    assert "local_stability_below_constraint" in by_id[
        "baseline"
    ].eligibility_failures
    assert "precision_below_constraint" in by_id["q_grow:low"].eligibility_failures
    expected_status = (
        "unavailable"
        if result.backend_identity.backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
        else "available"
    )
    assert selected.metrics.boundary_precision.status == expected_status
    assert all(
        value.boundary_precision.status == expected_status
        for value in selected.group_metrics
    )


def _open_validation(
    scenario: _CampaignScenario,
    destination,
) -> M6CampaignReportV2Publication:
    return open_m6_validation_and_publish_report(
        scenario.campaign,
        scenario.shortlist,
        scenario.geometry,
        backends=scenario.backends,
        destination=destination,
    )


def _assert_validation_metrics(
    report: M6CampaignReportV2,
    validation_failure: bool,
) -> None:
    by_backend = {
        value.backend_identity.backend_id: value
        for value in report.validation_results
    }
    assert by_backend[
        M6_ORIENTATION_COMPONENTS_BACKEND_ID
    ].metrics.boundary_precision.status == "unavailable"
    assert by_backend[
        M3_M6_LATTICE_NETWORK_BACKEND_ID
    ].metrics.boundary_precision.status == "available"
    for result in report.validation_results:
        assert result.group_metrics[0].measurement_group_id == "validation-secret"
        assert result.metrics.funnel_misses == (
            (("automatic_result", 1),) if validation_failure else ()
        )


def _assert_report_artifacts(publication: M6CampaignReportV2Publication) -> None:
    for path in (
        publication.report_json_path,
        publication.report_markdown_path,
        publication.metrics_csv_path,
        publication.receipt_path,
    ):
        assert path.is_file()
        assert path.parent == publication.output_directory
    payload = json.loads(publication.report_json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m6-campaign-report-v2"
    assert payload["preset_modified"] is False
    assert payload["validation_access_receipt"]["open_count"] == 1
    assert "validation-secret" in publication.report_markdown_path.read_text(
        encoding="utf-8"
    )
    assert "validation-secret" in publication.metrics_csv_path.read_text(
        encoding="utf-8"
    )


def _assert_pre_open_mismatches(
    scenario: _CampaignScenario,
    tmp_path,
) -> None:
    before = {key: len(values) for key, values in scenario.observed.items()}
    changed_objective = replace(
        scenario.shortlist.objective,
        minimum_membership_precision=0.91,
    )
    mismatched = (
        replace(
            scenario.shortlist,
            dataset_version_id="different-dataset-version",
        ),
        replace(scenario.shortlist, objective=changed_objective),
        replace(scenario.shortlist, tie_break_rule="changed-tie-break"),
    )
    for shortlist in mismatched:
        with pytest.raises(ValueError, match="does not match"):
            open_m6_validation_and_publish_report(
                scenario.campaign,
                shortlist,
                scenario.geometry,
                backends=scenario.backends,
                destination=tmp_path / "must-not-open-validation",
            )
    with pytest.raises(ValueError, match="geometry fingerprint changed"):
        open_m6_validation_and_publish_report(
            scenario.campaign,
            scenario.shortlist,
            replace(scenario.geometry, geometry_fingerprint="changed-geometry"),
            backends=scenario.backends,
            destination=tmp_path / "must-not-open-validation",
        )
    assert {key: len(values) for key, values in scenario.observed.items()} == before


def _configure_validation_registry(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "MOLTRACK_M6_VALIDATION_ACCESS_REGISTRY",
        str(tmp_path.parent / "m6-validation-access"),
    )


def _reference_package(tmp_path, *, dataset_id="campaign-reference"):
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
        dataset_id=dataset_id,
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
