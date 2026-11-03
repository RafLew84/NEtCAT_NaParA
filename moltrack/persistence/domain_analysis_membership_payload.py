from __future__ import annotations

from typing import Any, cast

from moltrack.analysis.domain_analysis import M6PublishedMolecule
from moltrack.analysis.domain_analysis.geometry import MoleculeSourceKind

from .domain_analysis_payload_validation import (
    float_pair_field,
    integer_pairs_field,
    mapping,
    text_field,
)


def published_molecule_to_payload(
    value: M6PublishedMolecule,
) -> dict[str, Any]:
    payload = {
        "source_id": value.source_id,
        "source_kind": value.source_kind,
        "point_xy_nm": list(value.point_xy_nm),
    }
    if value.raw_centroid_xy is not None:
        payload["raw_centroid_xy"] = list(value.raw_centroid_xy)
    if value.footprint_pixels_xy is not None:
        payload["footprint_pixels_xy"] = [
            list(pixel) for pixel in value.footprint_pixels_xy
        ]
    return payload


def published_molecule_from_payload(
    payload: Any,
    *,
    path: str,
) -> M6PublishedMolecule:
    saved = mapping(payload, path)
    return M6PublishedMolecule(
        source_id=text_field(saved, "source_id", path),
        source_kind=cast(
            MoleculeSourceKind,
            text_field(saved, "source_kind", path),
        ),
        point_xy_nm=float_pair_field(saved, "point_xy_nm", path),
        raw_centroid_xy=(
            float_pair_field(saved, "raw_centroid_xy", path)
            if "raw_centroid_xy" in saved
            else None
        ),
        footprint_pixels_xy=(
            integer_pairs_field(saved, "footprint_pixels_xy", path)
            if "footprint_pixels_xy" in saved
            else None
        ),
    )
