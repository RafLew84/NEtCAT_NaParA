"""Audit TTMAPP readiness and manual evidence for hierarchy step 89.4."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from moltrack.analysis import MolecularOrderTypeSessionState
from moltrack.persistence import load_moltrack_session


def build_validation_report(
    session,
    prior_report: dict[str, object],
    *,
    session_path: Path,
    prior_report_path: Path,
    representative_paths: tuple[Path, ...],
) -> dict[str, object]:
    orientations = getattr(session, "molecular_orientations", None)
    orientation_count = (
        0
        if orientations is None
        else len(tuple(orientations.measurements))
    )
    stacking = getattr(session, "molecular_stacking_state", None)
    stacking_computed = (
        stacking is not None
        and getattr(stacking, "status", None) == "computed"
    )
    order_state = getattr(
        session,
        "molecular_order_type_analysis_state",
        None,
    )
    order_cache_available = (
        isinstance(order_state, MolecularOrderTypeSessionState)
        and order_state.cache_record is not None
    )
    baseline = prior_report["classification_runs"]["baseline"]["summary"]
    manual_status = prior_report["manual_review"]["status"]
    representatives_exist = bool(representative_paths) and all(
        path.is_file() for path in representative_paths
    )
    hierarchy_inputs_ready = orientation_count > 0 and stacking_computed
    status = (
        "hierarchical_inputs_available_pending_rebuild_and_visual_review"
        if hierarchy_inputs_ready
        else "partial_insufficient_hierarchical_inputs"
    )
    representative_overlays = [
        {
            "path": str(path.resolve()),
            "sha256": _sha256_file(path),
        }
        for path in representative_paths
    ]
    return {
        "validation_id": "molecular-order-types-ttmapp-step-89.4",
        "status": status,
        "source_session": str(session_path.resolve()),
        "source_session_sha256": _sha256_file(session_path),
        "source_mpp": session.source_path,
        "source_view": prior_report["source_view"],
        "ranges": prior_report["ranges"],
        "prior_geometry_validation": {
            "report": str(prior_report_path.resolve()),
            "report_sha256": _sha256_file(prior_report_path),
            "manual_review_status": manual_status,
            "representative_overlay_count": len(representative_paths),
            "all_representative_overlays_present": representatives_exist,
            "representative_overlays": representative_overlays,
            "observation_count": baseline["observation_count"],
            "classified_observation_count": baseline[
                "classified_observation_count"
            ],
            "unclassified_observation_count": baseline[
                "unclassified_observation_count"
            ],
            "domain_type_count": baseline["domain_type_count"],
            "interpretation": (
                "Existing representative overlays support only the prior "
                "M6 geometry review and remain tolerance-sensitive."
            ),
        },
        "hierarchical_input_readiness": {
            "molecular_orientation_measurement_count": orientation_count,
            "stacking_analysis_computed": stacking_computed,
            "hierarchical_type_cache_available": order_cache_available,
            "cache_dependency_match_verified": False,
            "ready_for_full_hierarchy_validation": hierarchy_inputs_ready,
        },
        "layer_conclusions": {
            "geometry": (
                "reviewed_with_caution"
                if manual_status == "reviewed_with_caution"
                and representatives_exist
                else "not_verified"
            ),
            "molecular_orientation": (
                "available_pending_visual_review"
                if orientation_count > 0
                else "not_evaluable_missing_orientation_measurements"
            ),
            "stacking": (
                "available_pending_visual_review"
                if stacking_computed
                else "not_evaluable_missing_stacking_analysis"
            ),
            "combined_hierarchy": (
                "pending_rebuild_and_visual_review"
                if hierarchy_inputs_ready
                else "not_evaluable_missing_hierarchical_inputs"
            ),
        },
        "false_confidence_guard": (
            "No conclusion about molecular orientation, ABAB, phase "
            "boundaries, or combined hierarchy is made from this session "
            "when their required inputs are absent. Cache presence alone is "
            "not treated as proof that dependency fingerprints still match."
        ),
        "next_manual_action": (
            (
                "Rebuild Order Hierarchy from the saved orientation and "
                "stacking inputs, then review representative domains in "
                "both ranges."
            )
            if hierarchy_inputs_ready
            else (
                "Save a current MolTrack state after molecular orientation, "
                "stacking, and Order Hierarchy classification, then rerun "
                "this validator and review representative domains in both "
                "ranges."
            )
        ),
    }


def validate(
    session_path: Path,
    prior_report_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    prior_report = json.loads(
        prior_report_path.read_text(encoding="utf-8")
    )
    hierarchy_keys = (
        "molecular_orientations",
        "molecular_stacking_analysis",
        "molecular_order_type_analysis",
    )
    present_keys = _present_json_keys(session_path, hierarchy_keys)
    if present_keys:
        session = load_moltrack_session(session_path)
    else:
        # Old segmentation-heavy states can be hundreds of MB. Avoid decoding
        # their masks when none of the hierarchy inputs can be present.
        session = SimpleNamespace(
            source_path=str(prior_report.get("source_mpp", "")),
            molecular_orientations=None,
            molecular_stacking_state=None,
            molecular_order_type_analysis_state=None,
        )
    representative_paths = tuple(
        sorted(
            (prior_report_path.parent / "representatives").glob("*.png")
        )
    )
    report = build_validation_report(
        session,
        prior_report,
        session_path=session_path,
        prior_report_path=prior_report_path,
        representative_paths=representative_paths,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation_report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    return report


def _present_json_keys(
    path: Path,
    keys: tuple[str, ...],
    *,
    chunk_size: int = 1024 * 1024,
) -> frozenset[str]:
    needles = {
        key: json.dumps(key, ensure_ascii=True).encode("ascii")
        for key in keys
    }
    maximum_needle_length = max(
        (len(needle) for needle in needles.values()),
        default=1,
    )
    found: set[str] = set()
    overlap = b""
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            searchable = overlap + chunk
            found.update(
                key
                for key, needle in needles.items()
                if needle in searchable
            )
            if len(found) == len(needles):
                break
            overlap = searchable[-(maximum_needle_length - 1):]
    return frozenset(found)


def _markdown_report(report: dict[str, object]) -> str:
    readiness = report["hierarchical_input_readiness"]
    geometry = report["prior_geometry_validation"]
    conclusions = report["layer_conclusions"]
    return "\n".join([
        "# TTMAPP hierarchical molecular-order validation (step 89.4)",
        "",
        f"- Status: `{report['status']}`",
        f"- Session: `{report['source_session']}`",
        f"- Session SHA-256: `{report['source_session_sha256']}`",
        f"- Source view: `{report['source_view']}`",
        "",
        "## Input readiness",
        "",
        (
            "- Molecular orientation measurements: "
            f"`{readiness['molecular_orientation_measurement_count']}`"
        ),
        (
            "- Stacking analysis computed: "
            f"`{str(readiness['stacking_analysis_computed']).lower()}`"
        ),
        (
            "- Hierarchical cache available: "
            f"`{str(readiness['hierarchical_type_cache_available']).lower()}`"
        ),
        (
            "- Cache dependency match verified: "
            f"`{str(readiness['cache_dependency_match_verified']).lower()}`"
        ),
        "",
        "## Manual evidence",
        "",
        (
            "- Prior geometry review: "
            f"`{geometry['manual_review_status']}`"
        ),
        (
            "- Representative overlays present: "
            f"`{geometry['representative_overlay_count']}`"
        ),
        (
            "- Prior observations: "
            f"`{geometry['observation_count']}` "
            f"({geometry['classified_observation_count']} classified, "
            f"{geometry['unclassified_observation_count']} unclassified)"
        ),
        "",
        "## Layer conclusions",
        "",
        f"- Geometry: `{conclusions['geometry']}`",
        (
            "- Molecular orientation: "
            f"`{conclusions['molecular_orientation']}`"
        ),
        f"- Stacking: `{conclusions['stacking']}`",
        (
            "- Combined hierarchy: "
            f"`{conclusions['combined_hierarchy']}`"
        ),
        "",
        "## Confidence guard",
        "",
        report["false_confidence_guard"],
        "",
        "## Next action",
        "",
        report["next_manual_action"],
        "",
    ])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--session",
        type=Path,
        default=Path("data/TTMAPP/m6_state.moltrack.json"),
    )
    parser.add_argument(
        "--prior-report",
        type=Path,
        default=Path(
            "notes/ttmapp_domain_type_validation_83_3/"
            "validation_report.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("notes/ttmapp_order_validation_89_4"),
    )
    args = parser.parse_args()
    report = validate(args.session, args.prior_report, args.output_dir)
    print(
        f"Validation status: {report['status']}\n"
        f"Report: {args.output_dir / 'validation_report.md'}"
    )


if __name__ == "__main__":
    main()
