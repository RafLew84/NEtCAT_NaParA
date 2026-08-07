"""Validate the released Domain Analysis workflow on the local TTMAPP series."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAnalysisModule,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisSessionState,
    DomainComponentKey,
    TextureABCClassifierAdapter,
    with_scoped_domain_analysis_cache,
)
from moltrack.core import MolTrackImageSeries
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.persistence import (
    AnalysisExportPackageResult,
    CanonicalJsonObject,
    DomainAnalysisExportSettings,
    export_analysis_package,
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from moltrack.ui.domain_analysis_runtime import (
    _MolTrackM6Adapter,
    _domain_analysis_series,
)


DEFAULT_SOURCE_SHA256 = (
    "8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66"
)
DEFAULT_SESSION_SHA256 = (
    "3aa3d05969f88153da16947c52fa95ab10ca25cdf4f8485b741dfad7995a5810"
)


@dataclass(frozen=True)
class _CompletedAnalysis:
    series: MolTrackImageSeries
    analysis_series: DomainAnalysisSeries
    m6_adapter: _MolTrackM6Adapter
    module: DomainAnalysisModule
    configuration: ClassifierConfiguration
    request: DomainAnalysisRequest
    publication: DomainAnalysisPublication


@dataclass(frozen=True)
class _RoundTripEvidence:
    path: Path
    state: DomainAnalysisSessionState
    payload: dict[str, Any]


@dataclass(frozen=True)
class _ExportEvidence:
    package: AnalysisExportPackageResult
    manifest_path: Path
    manifest: dict[str, Any]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session",
        type=Path,
        default=Path("data/TTMAPP/detection250.moltrack.json"),
    )
    parser.add_argument("--frame-start", type=int, default=262)
    parser.add_argument("--frame-stop", type=int, default=268)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".tmp/ttmapp-domain-analysis-release-validation"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp/ttmapp-domain-analysis-release-report.json"),
    )
    parser.add_argument("--source-sha256", default=DEFAULT_SOURCE_SHA256)
    parser.add_argument("--session-sha256", default=DEFAULT_SESSION_SHA256)
    return parser.parse_args()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validated_input(
    path: Path,
    expected_sha256: str,
    name: str,
    *,
    root: Path,
) -> dict[str, Any]:
    resolved = path.resolve()
    actual_sha256 = _file_sha256(resolved)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"{name} SHA-256 mismatch: expected {expected_sha256}, "
            f"got {actual_sha256}."
        )
    return {
        "path": _display_path(resolved, root),
        "size_bytes": resolved.stat().st_size,
        "sha256": actual_sha256,
    }


def _classifier_configuration(
    classifier: TextureABCClassifierAdapter,
) -> ClassifierConfiguration:
    return ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=classifier.classifier_id,
            schema_version=classifier.classifier_schema_version,
            settings_fingerprint=classifier.classifier_settings_fingerprint,
            algorithm_version=classifier.classifier_algorithm_version,
        ),
        aggregation_preset=classifier.domain_aggregation_preset,
    )


def _snapshot_identity(publication: DomainAnalysisPublication) -> dict[str, Any]:
    gate = publication.result.m6_gate
    assert gate is not None
    outcomes = publication.result.classifier_outcomes or ()
    return {
        "request_fingerprint": publication.request_fingerprint,
        "m6_gate_fingerprints": [
            frame.m6_gate_fingerprint for frame in gate.frames
        ],
        "classifier_result_fingerprints": [
            outcome.classifier_result_fingerprint for outcome in outcomes
        ],
    }


def _frame_report(frame) -> dict[str, Any]:
    categories = [
        set(component.footprint_pixels_xy)
        for component in frame.full_domains + frame.small_ordered_islands
    ]
    categories.append(set(frame.outside_pixels_xy))
    for index, category in enumerate(categories):
        if not category.isdisjoint(set().union(*categories[index + 1 :])):
            raise AssertionError("M6 footprint categories overlap.")
    union = set().union(*categories)
    if union != set(frame.analyzed_pixels_xy):
        raise AssertionError("M6 footprint categories do not cover the frame.")
    full_members = sum(len(value.members) for value in frame.full_domains)
    island_members = sum(
        len(value.members) for value in frame.small_ordered_islands
    )
    if full_members == 0 or full_members + island_members + len(
        frame.outside_members
    ) != frame.analyzed_molecule_count:
        raise AssertionError("M6 membership is empty or incomplete.")
    return {
        "working_frame_index": frame.frame_index,
        "display_frame_number": frame.frame_index + 1,
        "physical_frame_id": frame.physical_frame_id,
        "analyzed_molecule_count": frame.analyzed_molecule_count,
        "full_domain_count": len(frame.full_domains),
        "full_domain_molecule_count": full_members,
        "small_ordered_island_count": len(frame.small_ordered_islands),
        "small_ordered_island_molecule_count": island_members,
        "outside_molecule_count": len(frame.outside_members),
        "analyzed_pixel_count": len(frame.analyzed_pixels_xy),
        "partition_is_disjoint_and_complete": True,
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
    }


def _classification_report(outcome) -> dict[str, Any]:
    classified = tuple(
        value
        for value in outcome.molecule_classifications
        if value.classification_status == "classified"
    )
    if any(value.m6_partition != "full_domain" for value in classified):
        raise AssertionError("A/B/C classified a molecule outside a full M6 domain.")
    labels = Counter(
        "not_gated" if value.orientation_label is None else value.orientation_label
        for value in outcome.molecule_classifications
    )
    if not {"A", "B", "C"}.issubset(labels):
        raise AssertionError("The real validation did not produce A, B, and C evidence.")
    domain_labels = Counter(value.label for value in outcome.domain_summaries)
    return {
        "classifier_id": outcome.classifier_id,
        "status": outcome.status,
        "classifier_result_fingerprint": outcome.classifier_result_fingerprint,
        "molecule_count": len(outcome.molecule_classifications),
        "molecule_label_counts": dict(sorted(labels.items())),
        "domain_count": len(outcome.domain_summaries),
        "domain_label_counts": dict(sorted(domain_labels.items())),
    }


def _session_state(
    module: DomainAnalysisModule,
    request: DomainAnalysisRequest,
    publication: DomainAnalysisPublication,
    configuration: ClassifierConfiguration,
) -> DomainAnalysisSessionState:
    gate = publication.result.m6_gate
    assert gate is not None and gate.frames and gate.frames[0].full_domains
    selected = gate.frames[0].full_domains[0]
    state = DomainAnalysisSessionState(
        draft=request,
        draft_classifier_configurations=(configuration,),
        draft_physical_frame_ids=tuple(
            frame.physical_frame_id for frame in gate.frames
        ),
        published_result=publication,
        selected_component=DomainComponentKey(
            physical_frame_id=gate.frames[0].physical_frame_id,
            lattice_domain_id=selected.lattice_domain_id,
        ),
        run_status=publication.result.run_status,
    )
    return with_scoped_domain_analysis_cache(
        state,
        module.session_cache_records(),
    )


def _round_trip_session(workspace: Path, series, state) -> _RoundTripEvidence:
    session_path = workspace / "round-trip.moltrack.json"
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": state},
    )
    loaded_session = load_moltrack_session(session_path)
    restored_state = loaded_session.domain_analysis_state
    if restored_state != state:
        raise AssertionError("Schema-v2 Save/Open changed the published snapshot.")
    serialized = session_path.read_text(encoding="utf-8")
    if '"raw_frame":' in serialized:
        raise AssertionError("Schema-v2 session embedded raw frame pixels.")
    payload = json.loads(serialized)
    if payload["schema_version"] != 2:
        raise AssertionError("Save did not produce MolTrack session schema v2.")
    return _RoundTripEvidence(session_path, restored_state, payload)


def _export_snapshot(
    workspace: Path,
    series,
    analysis_series,
    state,
) -> _ExportEvidence:
    source_indices = series.source_frame_indices
    if source_indices is None:
        raise RuntimeError("Image series has no source-frame mapping.")
    physical_ids = tuple(
        frame.geometry.physical_frame_id for frame in analysis_series.frames
    )
    settings = DomainAnalysisExportSettings(
        destination=workspace / "domain-analysis-export",
        source_frame_indices=source_indices,
        physical_frame_ids=physical_ids,
        source_identity=CanonicalJsonObject({
            "source_name": Path(series.source_path).name,
            "source_sha256": _file_sha256(Path(series.source_path)),
        }),
        m6_settings=CanonicalJsonObject(
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET.to_dict()
        ),
    )
    exported = export_analysis_package(state, settings)
    manifest_path = exported.package_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return _ExportEvidence(exported, manifest_path, manifest)


def _validate_export(manifest, publication: DomainAnalysisPublication) -> None:
    exported = manifest["analysis"]["domain_analysis"]
    identity = _snapshot_identity(publication)
    if manifest["export_schema_version"] != 9:
        raise AssertionError("Export did not produce schema v9.")
    if exported["request"]["request_fingerprint"] != identity[
        "request_fingerprint"
    ]:
        raise AssertionError("Export changed the published request.")
    exported_gate_fingerprints = [
        frame["m6_gate_fingerprint"]
        for frame in exported["m6_gate"]["frames"]
    ]
    if exported_gate_fingerprints != identity["m6_gate_fingerprints"]:
        raise AssertionError("Export changed the published M6 gate.")
    exported_classifier_fingerprints = [
        outcome["classifier_result_fingerprint"]
        for outcome in exported["classifier_outcomes"]
    ]
    if exported_classifier_fingerprints != identity[
        "classifier_result_fingerprints"
    ]:
        raise AssertionError("Export changed the published classifier outcome.")


def _git_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=True,
        encoding="utf-8",
        text=True,
    ).stdout.strip()


def _run_analysis(loaded: Any, frame_start: int, frame_stop: int) -> _CompletedAnalysis:
    series = restore_moltrack_image_series_from_session(loaded)
    analysis_series = _domain_analysis_series(series)
    classifier = TextureABCClassifierAdapter()
    configuration = _classifier_configuration(classifier)
    m6_adapter = _MolTrackM6Adapter(analysis_series)
    module = DomainAnalysisModule(
        m6_adapter,
        {ABC_ORIENTATION_CLASSIFIER_ID: classifier},
    )
    request = DomainAnalysisRequest(
        frame_range=range(frame_start, frame_stop),
        classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
    )
    result = module.run(analysis_series, request)
    if result.run_status != "completed" or result.classifier_status != "completed":
        raise AssertionError(
            f"Domain Analysis did not complete: {result.run_status}, "
            f"{result.classifier_status}."
        )
    publication = DomainAnalysisPublication(request=request, result=result)
    return _CompletedAnalysis(
        series,
        analysis_series,
        m6_adapter,
        module,
        configuration,
        request,
        publication,
    )


def _configuration_report(analysis: _CompletedAnalysis) -> dict[str, Any]:
    configuration = analysis.configuration
    return {
        "m6_preset": "TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET",
        "m6_settings": TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET.to_dict(),
        "m6_settings_fingerprint": analysis.m6_adapter.m6_settings_fingerprint,
        "m6_algorithm_version": analysis.m6_adapter.m6_algorithm_version,
        "classifier": {
            "classifier_id": configuration.identity.classifier_id,
            "schema_version": configuration.identity.schema_version,
            "settings_fingerprint": configuration.identity.settings_fingerprint,
            "algorithm_version": configuration.identity.algorithm_version,
            "aggregation_preset_id": configuration.aggregation_preset.preset_id,
            "aggregation_preset_fingerprint": (
                configuration.aggregation_preset.fingerprint
            ),
        },
    }


def _analysis_report(
    analysis: _CompletedAnalysis,
    snapshot_fingerprint: str,
) -> dict[str, Any]:
    result = analysis.publication.result
    gate = result.m6_gate
    outcomes = result.classifier_outcomes
    assert gate is not None and outcomes is not None and len(outcomes) == 1
    return {
        "run_status": result.run_status,
        "classifier_status": result.classifier_status,
        "snapshot_fingerprint": snapshot_fingerprint,
        "frames": [_frame_report(frame) for frame in gate.frames],
        "classifier": _classification_report(outcomes[0]),
    }


def _round_trip_report(
    evidence: _RoundTripEvidence,
    original_state: DomainAnalysisSessionState,
) -> dict[str, Any]:
    return {
        "moltrack_session_schema_version": evidence.payload["schema_version"],
        "domain_analysis_schema_version": evidence.state.schema_version,
        "published_snapshot_unchanged": evidence.state == original_state,
        "raw_frames_embedded": False,
        "m6_cache_record_count": len(evidence.state.m6_cache_records),
        "classifier_cache_record_count": len(
            evidence.state.classifier_cache_records
        ),
        "round_trip_session_sha256": _file_sha256(evidence.path),
        "snapshot_fingerprint": canonical_sha256(
            _snapshot_identity(evidence.state.published_result)
        ),
    }


def _export_report(
    evidence: _ExportEvidence,
    snapshot_fingerprint: str,
) -> dict[str, Any]:
    return {
        "export_schema_version": evidence.manifest["export_schema_version"],
        "analysis_mode": evidence.manifest["analysis"]["analysis_mode"],
        "published_snapshot_unchanged": True,
        "snapshot_fingerprint": snapshot_fingerprint,
        "manifest_sha256": _file_sha256(evidence.manifest_path),
        "relative_files": list(evidence.package.relative_files),
        "record_counts": dict(evidence.package.record_counts),
    }


def _validation_report(
    root: Path,
    analysis: _CompletedAnalysis,
    state: DomainAnalysisSessionState,
    round_trip: _RoundTripEvidence,
    exported: _ExportEvidence,
    source_input: dict[str, Any],
    session_input: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    request = analysis.request
    snapshot_fingerprint = canonical_sha256(
        _snapshot_identity(analysis.publication)
    )
    report = {
        "validation_schema_version": 1,
        "validated_code_commit": _git_commit(root),
        "validator_sha256": _file_sha256(Path(__file__).resolve()),
        "reproduction": {
            "working_directory": "repository_root",
            "command": (
                "python scripts/validate_ttmapp_domain_analysis_release.py "
                f"--session {session_input['path']} "
                f"--frame-start {request.frame_range.start} "
                f"--frame-stop {request.frame_range.stop}"
            ),
        },
        "inputs": {"source_mpp": source_input, "moltrack_session": session_input},
        "request": {
            "working_frame_start": request.frame_range.start,
            "working_frame_stop": request.frame_range.stop,
            "display_frame_start": request.frame_range.start + 1,
            "display_frame_stop_inclusive": request.frame_range.stop,
            "geometry_mode": request.geometry_mode,
            "classifier_ids": list(request.classifier_ids),
            "request_fingerprint": analysis.publication.request_fingerprint,
        },
        "configuration": _configuration_report(analysis),
        "analysis": _analysis_report(analysis, snapshot_fingerprint),
        "session_round_trip": _round_trip_report(round_trip, state),
        "export": _export_report(exported, snapshot_fingerprint),
    }
    return report, snapshot_fingerprint


def main() -> None:
    args = _parse_args()
    root = Path.cwd().resolve()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    session_input = _validated_input(
        args.session, args.session_sha256, "MolTrack session", root=root
    )
    loaded = load_moltrack_session(args.session)
    source_input = _validated_input(
        Path(loaded.source_path), args.source_sha256, "source MPP", root=root
    )
    analysis = _run_analysis(loaded, args.frame_start, args.frame_stop)
    state = _session_state(
        analysis.module,
        analysis.request,
        analysis.publication,
        analysis.configuration,
    )
    round_trip = _round_trip_session(workspace, analysis.series, state)
    exported = _export_snapshot(
        workspace,
        analysis.series,
        analysis.analysis_series,
        round_trip.state,
    )
    _validate_export(exported.manifest, analysis.publication)
    report, snapshot_fingerprint = _validation_report(
        root, analysis, state, round_trip, exported, source_input, session_input
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"validation report: {args.output}")
    print(f"snapshot fingerprint: {snapshot_fingerprint}")
    print("status: completed")


if __name__ == "__main__":
    main()
