from __future__ import annotations

import json
import os
import zipfile

from moltrack.core import (
    AnalysisRegion,
    CopiedAnalysisRegion,
    FrameScopedAnalysisRegion,
    MolTrackProject,
    SourceImageSeries,
    WorkingFrame,
    WorkingImageSeries,
)

MOLTRACK_PROJECT_SCHEMA = "moltrack.project.v1"
MOLTRACK_BUNDLE_CONTAINER = "zip"
MANIFEST_PATH = "manifest.json"


def build_project_manifest(project: MolTrackProject) -> dict:
    """Build the JSON-serializable manifest for a `.moltrack` project bundle."""
    return {
        "schema": MOLTRACK_PROJECT_SCHEMA,
        "bundle": {
            "container": MOLTRACK_BUNDLE_CONTAINER,
            "manifest_path": MANIFEST_PATH,
        },
        "project": {
            "name": project.project_name,
        },
        "source_series": {
            "source_uri": project.source_series.source_uri,
            "source_uris": list(project.source_series.source_uris),
            "display_name": project.source_series.display_name,
            "frame_count": project.source_series.frame_count,
        },
        "working_series": {
            "frame_mapping": [
                {
                    "working_frame_index": frame.working_frame_index,
                    "source_frame_index": frame.source_frame_index,
                }
                for frame in project.working_series.frames
            ],
            "removed_source_frame_indices": project.working_series.removed_source_frame_indices(),
        },
        "analysis_regions": [_analysis_region_to_manifest(region) for region in project.analysis_regions],
        "copied_analysis_regions": [
            {
                "region_name": copied_region.region.name,
                "working_frame_indices": list(copied_region.working_frame_indices),
            }
            for copied_region in project.copied_analysis_regions
        ],
        "frame_scoped_analysis_regions": [
            {
                "region": _analysis_region_to_manifest(scoped_region.region),
                "working_frame_indices": list(scoped_region.working_frame_indices),
            }
            for scoped_region in project.frame_scoped_analysis_regions
        ],
    }


def save_project(path: str | os.PathLike[str], project: MolTrackProject) -> None:
    """Save a MolTrack project bundle with manifest-backed derived state."""
    output_path = os.fspath(path)
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    manifest = build_project_manifest(project)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_PATH, json.dumps(manifest, ensure_ascii=False, indent=2))


def load_project(path: str | os.PathLike[str]) -> MolTrackProject:
    """Load a MolTrack project bundle from its manifest."""
    with zipfile.ZipFile(os.fspath(path), mode="r") as zf:
        manifest = json.loads(zf.read(MANIFEST_PATH).decode("utf-8"))
    return project_from_manifest(manifest)


def project_from_manifest(manifest: dict) -> MolTrackProject:
    schema = manifest.get("schema")
    if schema != MOLTRACK_PROJECT_SCHEMA:
        raise ValueError(f"Unsupported MolTrack project schema: {schema!r}")

    source_payload = manifest["source_series"]
    source_series = SourceImageSeries(
        source_uri=source_payload["source_uri"],
        source_uris=tuple(source_payload.get("source_uris") or (source_payload["source_uri"],)),
        frame_count=int(source_payload["frame_count"]),
        display_name=source_payload.get("display_name", ""),
    )
    frames = tuple(
        WorkingFrame(
            working_frame_index=int(item["working_frame_index"]),
            source_frame_index=int(item["source_frame_index"]),
        )
        for item in manifest["working_series"]["frame_mapping"]
    )
    working_series = WorkingImageSeries(source_series=source_series, frames=frames)
    analysis_regions = tuple(_analysis_region_from_manifest(item) for item in manifest.get("analysis_regions", ()))
    region_by_name = {region.name: region for region in analysis_regions}
    copied_analysis_regions = tuple(
        CopiedAnalysisRegion(
            region=region_by_name[item["region_name"]],
            working_frame_indices=tuple(int(index) for index in item["working_frame_indices"]),
        )
        for item in manifest.get("copied_analysis_regions", ())
    )
    frame_scoped_analysis_regions = tuple(
        FrameScopedAnalysisRegion(
            region=_analysis_region_from_manifest(item["region"]),
            working_frame_indices=tuple(int(index) for index in item["working_frame_indices"]),
        )
        for item in manifest.get("frame_scoped_analysis_regions", ())
    )
    return MolTrackProject(
        source_series=source_series,
        working_series=working_series,
        project_name=manifest.get("project", {}).get("name", "Untitled MolTrack Project"),
        analysis_regions=analysis_regions,
        copied_analysis_regions=copied_analysis_regions,
        frame_scoped_analysis_regions=frame_scoped_analysis_regions,
    )


def _analysis_region_to_manifest(region: AnalysisRegion) -> dict:
    payload = {
        "kind": region.kind.value,
        "name": region.name,
        "color_rgb": list(region.color_rgb),
        "coordinate_system": region.coordinate_system,
    }
    if region.rect_xyxy is not None:
        payload["geometry"] = {"type": "rect", "rect_xyxy": list(region.rect_xyxy)}
    else:
        payload["geometry"] = {
            "type": "polygon",
            "vertices_xy": region.polygon_xy.tolist(),
        }
    return payload


def _analysis_region_from_manifest(payload: dict) -> AnalysisRegion:
    geometry = payload["geometry"]
    if geometry["type"] == "rect":
        return AnalysisRegion.rectangle(
            kind=payload["kind"],
            name=payload["name"],
            color_rgb=tuple(payload["color_rgb"]),
            rect_xyxy=tuple(geometry["rect_xyxy"]),
        )
    if geometry["type"] == "polygon":
        return AnalysisRegion.polygon(
            kind=payload["kind"],
            name=payload["name"],
            color_rgb=tuple(payload["color_rgb"]),
            vertices_xy=geometry["vertices_xy"],
        )
    raise ValueError(f"Unsupported analysis region geometry type: {geometry['type']!r}")
