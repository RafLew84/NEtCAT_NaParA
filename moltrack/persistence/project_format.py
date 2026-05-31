from __future__ import annotations

import json
import os
import zipfile

from moltrack.core import MolTrackProject, SourceImageSeries, WorkingFrame, WorkingImageSeries

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
    }


def save_project(path: str | os.PathLike[str], project: MolTrackProject) -> None:
    """Save an empty MolTrack project bundle with a manifest only."""
    output_path = os.fspath(path)
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    manifest = build_project_manifest(project)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_PATH, json.dumps(manifest, ensure_ascii=False, indent=2))


def load_project(path: str | os.PathLike[str]) -> MolTrackProject:
    """Load an empty MolTrack project bundle from its manifest."""
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
    return MolTrackProject(
        source_series=source_series,
        working_series=WorkingImageSeries(source_series=source_series, frames=frames),
        project_name=manifest.get("project", {}).get("name", "Untitled MolTrack Project"),
    )
