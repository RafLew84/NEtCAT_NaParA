from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import M6FrameGate, M6PublishedComponent


def m6_frame_gate_fingerprint(frame: M6FrameGate) -> str:
    """Hash one complete canonical frame gate without view-only provenance."""

    payload = {
        "schema_version": "domain-analysis-m6-gate-v1",
        "frame_index": frame.frame_index,
        "physical_frame_id": frame.physical_frame_id,
        "coordinate_frame": frame.coordinate_frame,
        "coordinate_transform_fingerprint": (
            frame.coordinate_transform_fingerprint
        ),
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
        "m6_settings_fingerprint": frame.m6_settings_fingerprint,
        "m6_algorithm_version": frame.m6_algorithm_version,
        "pixel_area_nm2": frame.pixel_area_nm2,
        "full_domains": [
            _published_component_payload(value)
            for value in frame.full_domains
        ],
        "small_ordered_islands": [
            _published_component_payload(value)
            for value in frame.small_ordered_islands
        ],
        "outside_source_ids": frame.outside_source_ids,
        "outside_points_xy_nm": frame.outside_points_xy_nm,
        "outside_pixels_xy": frame.outside_pixels_xy,
        "outside_area_nm2": frame.outside_area_nm2,
        "analyzed_source_ids": frame.analyzed_source_ids,
        "analyzed_pixels_xy": frame.analyzed_pixels_xy,
        "analyzed_area_nm2": frame.analyzed_area_nm2,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _published_component_payload(
    component: M6PublishedComponent,
) -> dict[str, object]:
    return {
        "lattice_domain_id": component.lattice_domain_id,
        "component_type": component.component_type,
        "source_ids": component.source_ids,
        "core_source_ids": component.core_source_ids,
        "halo_source_ids": component.halo_source_ids,
        "points_xy_nm": component.points_xy_nm,
        "footprint_pixels_xy": component.footprint_pixels_xy,
        "footprint_area_nm2": component.footprint_area_nm2,
        "centroid_xy_nm": component.centroid_xy_nm,
        "bounds_xyxy_nm": component.bounds_xyxy_nm,
    }
