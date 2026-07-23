"""Bounded calibration of the final per-frame M3/M6 domain partition."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import hashlib
import json
from pathlib import Path

from .lattice_domain_calibration_models import (
    LATTICE_DOMAIN_CALIBRATION_ALGORITHM_VERSION,
    LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS,
    TTMAPP_FIRST_SHELL_R_MAX_NM,
    TTMAPP_FIRST_SHELL_R_MIN_NM,
    LatticeDomainCalibrationAggregateMetrics,
    LatticeDomainCalibrationFirstShellValidation,
    LatticeDomainCalibrationPrediction,
    LatticeDomainCalibrationProgress,
    LatticeDomainCalibrationQualityImpact,
    LatticeDomainCalibrationReferenceDataset,
    LatticeDomainCalibrationReferenceFrame,
    LatticeDomainCalibrationReport,
    LatticeDomainCalibrationSkippedVariant,
    LatticeDomainCalibrationStableRange,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainCalibrationVariant,
    LatticeDomainCalibrationVariantResult,
)
from .lattice_domain_calibration_search import (
    build_initial_variants as _build_initial_variants,
    build_multivariate_variants as _build_multivariate_variants,
    build_stability_variants as _build_stability_variants,
    rank_variants as _rank_variants,
    stability_ranges_around_best as _stability_ranges_around_best,
)
from .lattice_domain_edge_models import (
    LATTICE_DOMAIN_EDGE_COMPATIBILITY_ALGORITHM_VERSION,
)
from .lattice_domain_models import LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION
from .lattice_domain_seed_growth_models import (
    LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION,
)
from .lattice_domain_validation import (
    LatticeDomainPartitionLabels,
    LatticeDomainValidationReport,
    evaluate_lattice_domain_partition,
    lattice_domain_partition_labels_from_analysis,
)
from .local_symmetry_evidence_models import (
    LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION,
)
from .m6_domain_type_lifecycle import M6DomainTypeAnalysisSource
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .molecular_m6_analysis import analyze_molecular_m6_orientation


LatticeDomainCalibrationEvaluator = Callable[
    [LatticeDomainCalibrationReferenceFrame, MolecularM6OrientationAnalysisSettings],
    LatticeDomainPartitionLabels | LatticeDomainCalibrationPrediction,
]
LatticeDomainCalibrationProgressCallback = Callable[
    [LatticeDomainCalibrationProgress],
    None,
]
LatticeDomainCalibrationCancelCallback = Callable[[], bool]


class LatticeDomainCalibrationCanceled(RuntimeError):
    """Raised cooperatively between frame evaluations."""


def build_lattice_domain_calibration_initial_variants(
    sweep: LatticeDomainCalibrationSweepSettings,
) -> tuple[LatticeDomainCalibrationVariant, ...]:
    variants, _skipped = _build_initial_variants(sweep)
    return variants


def run_lattice_domain_calibration(
    reference: LatticeDomainCalibrationReferenceDataset,
    sweep: LatticeDomainCalibrationSweepSettings,
    *,
    evaluator: LatticeDomainCalibrationEvaluator,
    progress_callback: LatticeDomainCalibrationProgressCallback | None = None,
    cancel_callback: LatticeDomainCalibrationCancelCallback | None = None,
) -> LatticeDomainCalibrationReport:
    """Select on calibration frames, prove local stability, then open holdout."""

    if not isinstance(reference, LatticeDomainCalibrationReferenceDataset):
        raise TypeError("reference must be a calibration reference dataset.")
    if not reference.reviewed:
        raise ValueError("Calibration reference must be manually reviewed first.")
    if not isinstance(sweep, LatticeDomainCalibrationSweepSettings):
        raise TypeError("sweep must be lattice-domain calibration settings.")
    if not callable(evaluator):
        raise TypeError("evaluator must be callable.")
    _validate_complete_quality_controls(reference)

    initial_variants, initial_skipped = _build_initial_variants(sweep)
    skipped = list(initial_skipped)
    variant_results: list[LatticeDomainCalibrationVariantResult] = []
    diagnostic_cache_result: LatticeDomainCalibrationVariantResult | None = None
    diagnostic_prediction_cache: dict[
        int,
        LatticeDomainCalibrationPrediction,
    ] | None = None
    completed = 0
    initial_total = len(initial_variants) * len(reference.calibration_frames)

    for variant in initial_variants:
        result, variant_predictions, completed = _evaluate_variant(
            variant,
            reference.calibration_frames,
            evaluator=evaluator,
            phase="one_at_a_time",
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            completed_evaluations=completed,
            total_evaluations=initial_total,
        )
        variant_results.append(result)
        if (
            diagnostic_cache_result is None
            or _rank_variants((diagnostic_cache_result, result))[0] is result
        ):
            diagnostic_cache_result = result
            diagnostic_prediction_cache = variant_predictions
    del variant_predictions
    one_at_a_time_results = tuple(variant_results)

    exploration_limit = (
        0
        if sweep.max_multivariate_variants == 0
        else max(1, (2 * sweep.max_multivariate_variants + 2) // 3)
    )
    multivariate, multivariate_skipped = _build_multivariate_variants(
        sweep,
        one_at_a_time_results,
        max_variants=exploration_limit,
        variant_id_prefix="explore",
    )
    skipped.extend(multivariate_skipped)
    total_with_multivariate = (
        initial_total + len(multivariate) * len(reference.calibration_frames)
    )
    for variant in multivariate:
        result, variant_predictions, completed = _evaluate_variant(
            variant,
            reference.calibration_frames,
            evaluator=evaluator,
            phase="multivariate",
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            completed_evaluations=completed,
            total_evaluations=total_with_multivariate,
        )
        variant_results.append(result)
        if (
            diagnostic_cache_result is None
            or _rank_variants((diagnostic_cache_result, result))[0] is result
        ):
            diagnostic_cache_result = result
            diagnostic_prediction_cache = variant_predictions
    if multivariate:
        del variant_predictions

    ranked_candidates = _rank_variants(tuple(variant_results))
    diagnostic_best = ranked_candidates[0]
    assert diagnostic_cache_result is diagnostic_best
    assert diagnostic_prediction_cache is not None
    selected_best: LatticeDomainCalibrationVariantResult | None = None
    stable_ranges: tuple[LatticeDomainCalibrationStableRange, ...] = ()
    indeterminate: tuple[str, ...] = sweep.parameter_names
    selected_calibration_predictions: dict[
        int,
        LatticeDomainCalibrationPrediction,
    ] | None = None
    maximum_stability_evaluations = (
        (
            sweep.max_stability_candidates
            * (1 + 2 * len(sweep.parameter_names))
            + 1
        )
        * len(reference.calibration_frames)
    )
    stability_total = completed + maximum_stability_evaluations
    stability_candidates_evaluated = 0
    for candidate in ranked_candidates[: sweep.max_stability_candidates]:
        (
            stability_results,
            candidate_predictions,
            completed,
            stability_skipped,
            candidate_ranges,
            candidate_indeterminate,
        ) = _evaluate_stability_candidate(
            candidate,
            reference.calibration_frames,
            sweep=sweep,
            evaluator=evaluator,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            completed_evaluations=completed,
            total_evaluations=stability_total,
            precomputed_predictions=(
                diagnostic_prediction_cache
                if candidate is diagnostic_best
                else None
            ),
        )
        if candidate is diagnostic_best:
            diagnostic_prediction_cache = None
        stability_candidates_evaluated += 1
        skipped.extend(stability_skipped)
        variant_results.extend(stability_results)
        if (
            candidate.metrics.mean_adjusted_rand_index
            >= sweep.minimum_stability_ari
            and not candidate_indeterminate
        ):
            selected_best = candidate
            stable_ranges = candidate_ranges
            indeterminate = ()
            selected_calibration_predictions = candidate_predictions
            break
        if candidate is diagnostic_best:
            stable_ranges = candidate_ranges
            indeterminate = candidate_indeterminate
        del candidate_predictions

    remaining_multivariate = (
        sweep.max_multivariate_variants - len(multivariate)
    )
    if selected_best is not None and remaining_multivariate > 0:
        refinement, refinement_skipped = _build_multivariate_variants(
            sweep,
            tuple(variant_results),
            center_settings=selected_best.variant.settings,
            max_variants=remaining_multivariate,
            variant_id_prefix=f"refine:{selected_best.variant.variant_id}",
        )
        skipped.extend(refinement_skipped)
        refinement_results = []
        refinement_total = (
            completed + len(refinement) * len(reference.calibration_frames)
        )
        for variant in refinement:
            result, refinement_predictions, completed = _evaluate_variant(
                variant,
                reference.calibration_frames,
                evaluator=evaluator,
                phase="multivariate",
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                completed_evaluations=completed,
                total_evaluations=refinement_total,
            )
            refinement_results.append(result)
        if refinement:
            del refinement_predictions
        variant_results.extend(refinement_results)

        remaining_stability_candidates = max(
            0,
            sweep.max_stability_candidates - stability_candidates_evaluated,
        )
        refinement_stability_total = completed + (
            remaining_stability_candidates
            * (1 + 2 * len(sweep.parameter_names))
            * len(reference.calibration_frames)
        )
        better_refinements = tuple(
            value
            for value in _rank_variants(tuple(refinement_results))
            if value.score > selected_best.score
        )
        if better_refinements and remaining_stability_candidates > 0:
            selected_calibration_predictions = None
        for candidate in better_refinements[:remaining_stability_candidates]:
            (
                stability_results,
                candidate_predictions,
                completed,
                stability_skipped,
                candidate_ranges,
                candidate_indeterminate,
            ) = _evaluate_stability_candidate(
                candidate,
                reference.calibration_frames,
                sweep=sweep,
                evaluator=evaluator,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                completed_evaluations=completed,
                total_evaluations=refinement_stability_total,
            )
            stability_candidates_evaluated += 1
            skipped.extend(stability_skipped)
            variant_results.extend(stability_results)
            if (
                candidate.metrics.mean_adjusted_rand_index
                >= sweep.minimum_stability_ari
                and not candidate_indeterminate
            ):
                selected_best = candidate
                stable_ranges = candidate_ranges
                indeterminate = ()
                selected_calibration_predictions = candidate_predictions
                break
            del candidate_predictions

    best = selected_best if selected_best is not None else diagnostic_best
    if selected_calibration_predictions is None:
        _diagnostic_result, calibration_predictions, completed = _evaluate_variant(
            best.variant,
            reference.calibration_frames,
            evaluator=evaluator,
            phase="stability",
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            completed_evaluations=completed,
            total_evaluations=stability_total,
        )
    else:
        calibration_predictions = selected_calibration_predictions
    calibration_reports = _frame_reports(
        reference.calibration_frames,
        calibration_predictions,
    )
    if (
        selected_best is None
    ):
        _emit_terminal_stability_progress(
            progress_callback,
            completed=completed,
            best=best,
            reference=reference,
        )
        return _build_report(
            reference,
            sweep,
            status="no_stable_solution",
            selected_settings=None,
            best_variant_id=None,
            variant_results=variant_results,
            skipped_variants=skipped,
            holdout_metrics=None,
            holdout_passed=None,
            frame_reports=calibration_reports,
            selected_predictions=calibration_predictions,
            stable_ranges=stable_ranges,
            indeterminate_parameters=indeterminate,
        )

    holdout_predictions = {}
    holdout_reports = []
    holdout_total = completed + len(reference.holdout_frames)
    for frame in reference.holdout_frames:
        _raise_if_canceled(cancel_callback)
        prediction = _normalize_prediction(evaluator(frame, best.variant.settings))
        report = evaluate_lattice_domain_partition(prediction.labels, frame.labels)
        holdout_predictions[frame.frame_index] = prediction
        holdout_reports.append((frame, report))
        completed += 1
        _emit_progress(
            progress_callback,
            LatticeDomainCalibrationProgress(
                phase="holdout",
                completed_evaluations=completed,
                total_evaluations=holdout_total,
                variant_id=best.variant.variant_id,
                frame_index=frame.frame_index,
            ),
        )
    holdout_metrics = _aggregate_validation_reports(
        report for _frame, report in holdout_reports
    )
    holdout_passed = (
        holdout_metrics.mean_adjusted_rand_index
        >= float(sweep.minimum_holdout_ari)
    )
    selected_predictions = {
        **calibration_predictions,
        **holdout_predictions,
    }
    first_shell_validation = _first_shell_validation(
        reference,
        selected_predictions,
        settings=sweep.baseline_settings,
    )
    first_shell_validation_passed = _first_shell_validation_passes(
        first_shell_validation,
        minimum_f1=sweep.minimum_first_shell_f1,
        settings=sweep.baseline_settings,
    )
    return _build_report(
        reference,
        sweep,
        status=(
            "stable"
            if first_shell_validation_passed
            else "stable_geometry_unverified"
        ),
        selected_settings=best.variant.settings,
        best_variant_id=best.variant.variant_id,
        variant_results=variant_results,
        skipped_variants=skipped,
        holdout_metrics=holdout_metrics,
        holdout_passed=holdout_passed,
        frame_reports=(*calibration_reports, *holdout_reports),
        selected_predictions=selected_predictions,
        stable_ranges=stable_ranges,
        indeterminate_parameters=indeterminate,
    )


def run_lattice_domain_calibration_for_source(
    reference: LatticeDomainCalibrationReferenceDataset,
    sweep: LatticeDomainCalibrationSweepSettings,
    source: M6DomainTypeAnalysisSource,
    *,
    source_file_name: str,
    progress_callback: LatticeDomainCalibrationProgressCallback | None = None,
    cancel_callback: LatticeDomainCalibrationCancelCallback | None = None,
) -> LatticeDomainCalibrationReport:
    """Re-run final M3/M6 partitions from completed Position Analysis samples."""

    if not isinstance(source, M6DomainTypeAnalysisSource):
        raise TypeError("source must be a completed M6 analysis source.")
    actual_source_name = Path(str(source_file_name)).name
    if Path(reference.source_file_name).name.casefold() != actual_source_name.casefold():
        raise ValueError("Reference dataset belongs to another source file.")
    if reference.source_view != source.source_view:
        raise ValueError("Reference dataset uses another source view.")
    if reference.use_segmentation_centroids != source.use_segmentation_centroids:
        raise ValueError("Reference dataset uses another centroid source mode.")
    if reference.source_frame_count != source.frame_count:
        raise ValueError("Reference dataset uses another source frame count.")
    if (
        reference.source_sample_fingerprint
        != lattice_domain_calibration_source_fingerprint(source)
    ):
        raise ValueError("Reference dataset belongs to different analyzed samples.")

    sample_by_frame = {}
    for range_analysis in source.range_analyses:
        for frame_result in range_analysis.frame_results:
            analysis = frame_result.m6_orientation_analysis
            if analysis is not None:
                sample_by_frame[frame_result.frame_index] = analysis.sample_coordinates
    missing = sorted(
        frame.frame_index
        for frame in reference.frames
        if frame.frame_index not in sample_by_frame
    )
    if missing:
        raise ValueError(
            "Completed Position Analysis does not contain reference frames: "
            + ", ".join(str(value + 1) for value in missing)
        )

    def evaluator(frame, settings):
        analysis = analyze_molecular_m6_orientation(
            sample_by_frame[frame.frame_index],
            settings=settings,
        )
        lattice = analysis.lattice_domain_analysis
        if lattice is None:
            raise RuntimeError("Final lattice-domain analysis is unavailable.")
        point_ids = analysis.first_shell_graph.point_ids
        return LatticeDomainCalibrationPrediction(
            labels=lattice_domain_partition_labels_from_analysis(lattice),
            first_shell_neighbor_pairs=tuple(
                tuple(sorted((point_ids[left], point_ids[right])))
                for left, right in analysis.first_shell_graph.edges_ij
            ),
        )

    return run_lattice_domain_calibration(
        reference,
        sweep,
        evaluator=evaluator,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )


def lattice_domain_calibration_source_fingerprint(
    source: M6DomainTypeAnalysisSource,
) -> str:
    """Identify every completed sample consumed by a calibration source."""

    if not isinstance(source, M6DomainTypeAnalysisSource):
        raise TypeError("source must be a completed M6 analysis source.")
    samples = {}
    for range_analysis in source.range_analyses:
        for frame_result in range_analysis.frame_results:
            analysis = frame_result.m6_orientation_analysis
            if analysis is not None:
                samples[frame_result.frame_index] = analysis.sample_coordinates
    payload = {
        "frame_count": source.frame_count,
        "source_view": source.source_view,
        "use_segmentation_centroids": source.use_segmentation_centroids,
        "samples": [
            {
                "frame_index": sample.frame_index,
                "point_source_ids": sample.point_source_ids,
                "point_source_kinds": sample.point_source_kinds,
                "point_annotation_fingerprints": (
                    sample.point_annotation_fingerprints
                ),
                "source_points_xy_px": sample.source_points_xy_px,
                "points_xy_nm": sample.points_xy_nm,
                "distance_to_valid_fov_boundary_nm": (
                    sample.distance_to_valid_fov_boundary_nm
                ),
                "valid_fov_polygon_xy_nm": sample.valid_fov_polygon_xy_nm,
                "plot_canvas_polygon_xy_nm": sample.plot_canvas_polygon_xy_nm,
                "window_side_lengths_nm": sample.window_side_lengths_nm,
                "coordinate_transform_fingerprint": (
                    sample.coordinate_transform_fingerprint
                ),
                "spatial_calibration_fingerprint": (
                    sample.spatial_calibration_fingerprint
                ),
                "registration_fingerprint": sample.registration_fingerprint,
                "scan_angle_deg": sample.scan_angle_deg,
                "scan_angle_missing_qc": sample.scan_angle_missing_qc,
                "coordinate_frame": sample.coordinate_frame,
                "orientation_reference": sample.orientation_reference,
            }
            for _frame_index, sample in sorted(samples.items())
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _evaluate_variant(
    variant: LatticeDomainCalibrationVariant,
    frames: tuple[LatticeDomainCalibrationReferenceFrame, ...],
    *,
    evaluator: LatticeDomainCalibrationEvaluator,
    phase: str,
    progress_callback: LatticeDomainCalibrationProgressCallback | None,
    cancel_callback: LatticeDomainCalibrationCancelCallback | None,
    completed_evaluations: int,
    total_evaluations: int,
    stability_reference: (
        dict[int, LatticeDomainCalibrationPrediction] | None
    ) = None,
) -> tuple[
    LatticeDomainCalibrationVariantResult,
    dict[int, LatticeDomainCalibrationPrediction],
    int,
]:
    reports = []
    predictions = {}
    completed = completed_evaluations
    for frame in frames:
        _raise_if_canceled(cancel_callback)
        prediction = _normalize_prediction(evaluator(frame, variant.settings))
        predictions[frame.frame_index] = prediction
        reports.append(
            evaluate_lattice_domain_partition(
                prediction.labels,
                frame.labels,
                stability_reference=(
                    None
                    if stability_reference is None
                    else stability_reference[frame.frame_index].labels
                ),
            )
        )
        completed += 1
        _emit_progress(
            progress_callback,
            LatticeDomainCalibrationProgress(
                phase=phase,
                completed_evaluations=completed,
                total_evaluations=max(completed, total_evaluations),
                variant_id=variant.variant_id,
                frame_index=frame.frame_index,
            ),
        )
    metrics = _aggregate_validation_reports(reports)
    return (
        LatticeDomainCalibrationVariantResult(
            variant=variant,
            metrics=metrics,
            score=_selection_score(metrics),
        ),
        predictions,
        completed,
    )


def _evaluate_stability_candidate(
    candidate: LatticeDomainCalibrationVariantResult,
    frames: tuple[LatticeDomainCalibrationReferenceFrame, ...],
    *,
    sweep: LatticeDomainCalibrationSweepSettings,
    evaluator: LatticeDomainCalibrationEvaluator,
    progress_callback: LatticeDomainCalibrationProgressCallback | None,
    cancel_callback: LatticeDomainCalibrationCancelCallback | None,
    completed_evaluations: int,
    total_evaluations: int,
    precomputed_predictions: (
        dict[int, LatticeDomainCalibrationPrediction] | None
    ) = None,
) -> tuple[
    tuple[LatticeDomainCalibrationVariantResult, ...],
    dict[int, LatticeDomainCalibrationPrediction],
    int,
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
    tuple[LatticeDomainCalibrationStableRange, ...],
    tuple[str, ...],
]:
    if precomputed_predictions is None:
        _candidate_result, candidate_predictions, completed = _evaluate_variant(
            candidate.variant,
            frames,
            evaluator=evaluator,
            phase="stability",
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            completed_evaluations=completed_evaluations,
            total_evaluations=total_evaluations,
        )
    else:
        candidate_predictions = precomputed_predictions
        completed = completed_evaluations
    stability_variants, skipped = _build_stability_variants(
        candidate.variant,
        sweep.parameter_names,
    )
    stability_results = []
    for variant in stability_variants:
        result, variant_predictions, completed = _evaluate_variant(
            variant,
            frames,
            evaluator=evaluator,
            phase="stability",
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            completed_evaluations=completed,
            total_evaluations=total_evaluations,
            stability_reference=candidate_predictions,
        )
        stability_results.append(result)
    if stability_variants:
        del variant_predictions
    ranges, indeterminate = _stability_ranges_around_best(
        candidate,
        tuple(stability_results),
        parameter_names=sweep.parameter_names,
        minimum_ari=sweep.minimum_stability_ari,
    )
    return (
        tuple(stability_results),
        candidate_predictions,
        completed,
        skipped,
        ranges,
        indeterminate,
    )


def _normalize_prediction(
    value: LatticeDomainPartitionLabels | LatticeDomainCalibrationPrediction,
) -> LatticeDomainCalibrationPrediction:
    if isinstance(value, LatticeDomainCalibrationPrediction):
        return value
    if isinstance(value, LatticeDomainPartitionLabels):
        return LatticeDomainCalibrationPrediction(labels=value)
    raise TypeError("Calibration evaluator must return partition labels or a prediction.")


def _aggregate_validation_reports(
    reports: Iterable[LatticeDomainValidationReport],
) -> LatticeDomainCalibrationAggregateMetrics:
    values = tuple(reports)
    if not values:
        raise ValueError("At least one validation report is required.")
    true_positive = sum(value.boundary_true_positive_count for value in values)
    false_positive = sum(value.boundary_false_positive_count for value in values)
    false_negative = sum(value.boundary_false_negative_count for value in values)
    return LatticeDomainCalibrationAggregateMetrics(
        frame_count=len(values),
        evaluated_molecule_count=sum(value.evaluated_molecule_count for value in values),
        mean_adjusted_rand_index=_mean(value.adjusted_rand_index for value in values),
        mean_variation_of_information_nats=_mean(
            value.variation_of_information_nats for value in values
        ),
        mean_absolute_domain_count_error=_mean(
            abs(value.domain_count_error) for value in values
        ),
        mean_correctly_assigned_molecule_fraction=_mean(
            value.correctly_assigned_molecule_fraction or 0.0 for value in values
        ),
        boundary_precision=_safe_ratio(true_positive, true_positive + false_positive),
        boundary_recall=_safe_ratio(true_positive, true_positive + false_negative),
        mean_confidence_brier_score=_optional_mean(
            value.confidence_brier_score for value in values
        ),
        mean_confidence_expected_calibration_error=_optional_mean(
            value.confidence_expected_calibration_error for value in values
        ),
        mean_partition_stability_ari=_optional_mean(
            value.partition_stability_ari for value in values
        ),
        over_segmentation_count=sum(
            value.over_segmentation_count for value in values
        ),
        under_segmentation_count=sum(
            value.under_segmentation_count for value in values
        ),
    )


def _selection_score(metrics: LatticeDomainCalibrationAggregateMetrics) -> float:
    return (
        metrics.mean_adjusted_rand_index
        + 0.02 * metrics.mean_correctly_assigned_molecule_fraction
        - 0.001 * metrics.mean_variation_of_information_nats
    )


def _frame_reports(
    frames: tuple[LatticeDomainCalibrationReferenceFrame, ...],
    predictions: dict[int, LatticeDomainCalibrationPrediction],
) -> tuple[
    tuple[LatticeDomainCalibrationReferenceFrame, LatticeDomainValidationReport],
    ...,
]:
    return tuple(
        (
            frame,
            evaluate_lattice_domain_partition(
                predictions[frame.frame_index].labels,
                frame.labels,
            ),
        )
        for frame in frames
    )


def _build_report(
    reference: LatticeDomainCalibrationReferenceDataset,
    sweep: LatticeDomainCalibrationSweepSettings,
    *,
    status: str,
    selected_settings: MolecularM6OrientationAnalysisSettings | None,
    best_variant_id: str | None,
    variant_results: Iterable[LatticeDomainCalibrationVariantResult],
    skipped_variants: Iterable[LatticeDomainCalibrationSkippedVariant],
    holdout_metrics: LatticeDomainCalibrationAggregateMetrics | None,
    holdout_passed: bool | None,
    frame_reports: tuple[
        tuple[LatticeDomainCalibrationReferenceFrame, LatticeDomainValidationReport],
        ...,
    ],
    selected_predictions: dict[int, LatticeDomainCalibrationPrediction],
    stable_ranges: tuple[LatticeDomainCalibrationStableRange, ...],
    indeterminate_parameters: tuple[str, ...],
) -> LatticeDomainCalibrationReport:
    first_shell_validation = _first_shell_validation(
        reference,
        selected_predictions,
        settings=sweep.baseline_settings,
    )
    return LatticeDomainCalibrationReport(
        status=status,
        reference_dataset_id=reference.dataset_id,
        reference_dataset_fingerprint=reference.fingerprint,
        source_file_name=reference.source_file_name,
        source_frame_count=reference.source_frame_count,
        source_sample_fingerprint=reference.source_sample_fingerprint,
        source_view=reference.source_view,
        use_segmentation_centroids=reference.use_segmentation_centroids,
        baseline_settings=sweep.baseline_settings,
        selected_settings=selected_settings,
        best_variant_id=best_variant_id,
        calibration_frame_indices=tuple(
            value.frame_index for value in reference.calibration_frames
        ),
        holdout_frame_indices=tuple(
            value.frame_index for value in reference.holdout_frames
        ),
        variant_results=tuple(variant_results),
        skipped_variants=tuple(skipped_variants),
        holdout_metrics=holdout_metrics,
        holdout_passed=holdout_passed,
        quality_impacts=_quality_impacts(reference, frame_reports),
        first_shell_validation=first_shell_validation,
        first_shell_validation_passed=_first_shell_validation_passes(
            first_shell_validation,
            minimum_f1=sweep.minimum_first_shell_f1,
            settings=sweep.baseline_settings,
        ),
        stable_ranges=stable_ranges,
        indeterminate_parameters=indeterminate_parameters,
        algorithm_versions=(
            ("calibration", LATTICE_DOMAIN_CALIBRATION_ALGORITHM_VERSION),
            ("local_symmetry", LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION),
            (
                "edge_compatibility",
                LATTICE_DOMAIN_EDGE_COMPATIBILITY_ALGORITHM_VERSION,
            ),
            ("seed_growth", LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION),
            ("final_partition", LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION),
        ),
    )


def _quality_impacts(
    reference: LatticeDomainCalibrationReferenceDataset,
    frame_reports: tuple[
        tuple[LatticeDomainCalibrationReferenceFrame, LatticeDomainValidationReport],
        ...,
    ],
) -> tuple[LatticeDomainCalibrationQualityImpact, ...]:
    impacts = []
    for split in ("calibration", "holdout"):
        split_reports = tuple(
            value for value in frame_reports if value[0].split == split
        )
        for quality_tag in LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS:
            tagged = tuple(
                report
                for frame, report in split_reports
                if quality_tag in frame.quality_tags
            )
            control = tuple(
                report
                for frame, report in split_reports
                if quality_tag not in frame.quality_tags
            )
            tagged_metrics = (
                None if not tagged else _aggregate_validation_reports(tagged)
            )
            control_metrics = (
                None if not control else _aggregate_validation_reports(control)
            )
            impacts.append(
                LatticeDomainCalibrationQualityImpact(
                    quality_tag=quality_tag,
                    split=split,
                    tagged_metrics=tagged_metrics,
                    control_metrics=control_metrics,
                    mean_adjusted_rand_index_delta=(
                        None
                        if tagged_metrics is None or control_metrics is None
                        else (
                            tagged_metrics.mean_adjusted_rand_index
                            - control_metrics.mean_adjusted_rand_index
                        )
                    ),
                )
            )
    return tuple(impacts)


def _first_shell_validation(
    reference: LatticeDomainCalibrationReferenceDataset,
    predictions: dict[int, LatticeDomainCalibrationPrediction],
    *,
    settings: MolecularM6OrientationAnalysisSettings,
) -> tuple[LatticeDomainCalibrationFirstShellValidation, ...]:
    output = []
    for symmetry in ("trifold", "sixfold"):
        frames = tuple(
            frame
            for frame in reference.frames
            if frame.symmetry_class == symmetry and frame.frame_index in predictions
        )
        annotated_frames = tuple(
            frame for frame in frames if frame.first_shell_neighbor_pairs
        )
        manual_available = bool(annotated_frames)
        reference_edges = {
            (frame.frame_index, *pair)
            for frame in annotated_frames
            for pair in frame.first_shell_neighbor_pairs
        }
        predicted_edges = {
            (frame.frame_index, *pair)
            for frame in annotated_frames
            for pair in predictions[frame.frame_index].first_shell_neighbor_pairs
        }
        true_positive = len(reference_edges.intersection(predicted_edges))
        precision = (
            None
            if not manual_available
            else _safe_ratio(true_positive, len(predicted_edges))
        )
        recall = (
            None
            if not manual_available
            else _safe_ratio(true_positive, len(reference_edges))
        )
        f1 = (
            None
            if precision is None or recall is None or precision + recall == 0.0
            else 2.0 * precision * recall / (precision + recall)
        )
        output.append(
            LatticeDomainCalibrationFirstShellValidation(
                symmetry_class=symmetry,
                split="all",
                first_shell_r_min_nm=settings.first_shell_r_min_nm,
                first_shell_r_max_nm=settings.first_shell_r_max_nm,
                status=(
                    "available"
                    if manual_available
                    else "missing_manual_neighbors"
                ),
                reference_edge_count=len(reference_edges),
                predicted_edge_count=len(predicted_edges),
                true_positive_edge_count=true_positive,
                precision=precision,
                recall=recall,
                f1_score=f1,
            )
        )
    return tuple(output)


def _first_shell_validation_passes(
    validation: tuple[LatticeDomainCalibrationFirstShellValidation, ...],
    *,
    minimum_f1: float,
    settings: MolecularM6OrientationAnalysisSettings,
) -> bool:
    by_symmetry = {value.symmetry_class: value for value in validation}
    range_matches_ttmapp = (
        settings.first_shell_r_min_nm == TTMAPP_FIRST_SHELL_R_MIN_NM
        and settings.first_shell_r_max_nm == TTMAPP_FIRST_SHELL_R_MAX_NM
    )
    return range_matches_ttmapp and all(
        symmetry in by_symmetry
        and by_symmetry[symmetry].status == "available"
        and by_symmetry[symmetry].f1_score is not None
        and by_symmetry[symmetry].f1_score >= minimum_f1
        for symmetry in ("trifold", "sixfold")
    )


def _validate_complete_quality_controls(
    reference: LatticeDomainCalibrationReferenceDataset,
) -> None:
    missing = []
    for split in ("calibration", "holdout"):
        frames = tuple(frame for frame in reference.frames if frame.split == split)
        for quality_tag in LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS:
            if not any(quality_tag in frame.quality_tags for frame in frames):
                missing.append(f"{split}:{quality_tag}:tagged")
            if not any(quality_tag not in frame.quality_tags for frame in frames):
                missing.append(f"{split}:{quality_tag}:control")
    if missing:
        raise ValueError(
            "Calibration reference lacks tagged/control quality examples: "
            + ", ".join(missing)
        )


def _emit_terminal_stability_progress(
    callback: LatticeDomainCalibrationProgressCallback | None,
    *,
    completed: int,
    best: LatticeDomainCalibrationVariantResult,
    reference: LatticeDomainCalibrationReferenceDataset,
) -> None:
    _emit_progress(
        callback,
        LatticeDomainCalibrationProgress(
            phase="stability",
            completed_evaluations=completed,
            total_evaluations=completed,
            variant_id=best.variant.variant_id,
            frame_index=reference.calibration_frames[-1].frame_index,
        ),
    )


def _emit_progress(
    callback: LatticeDomainCalibrationProgressCallback | None,
    progress: LatticeDomainCalibrationProgress,
) -> None:
    if callback is not None:
        callback(progress)


def _raise_if_canceled(
    callback: LatticeDomainCalibrationCancelCallback | None,
) -> None:
    if callback is not None and callback():
        raise LatticeDomainCalibrationCanceled("Lattice-domain calibration canceled.")


def _mean(values: Iterable[float]) -> float:
    normalized = tuple(float(value) for value in values)
    return sum(normalized) / len(normalized)


def _optional_mean(values: Iterable[float | None]) -> float | None:
    normalized = tuple(float(value) for value in values if value is not None)
    return None if not normalized else sum(normalized) / len(normalized)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator
