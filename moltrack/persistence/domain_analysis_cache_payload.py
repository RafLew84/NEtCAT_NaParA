from __future__ import annotations

from typing import Any, cast

from moltrack.analysis.domain_analysis.cache import (
    ClassifierFrameCacheKey,
    ClassifierFrameCacheRecord,
    M6FrameCacheKey,
)
from moltrack.analysis.domain_analysis.geometry import (
    GeometryMode,
    M6AnalyzedMolecule,
    MoleculeSourceKind,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.domain_analysis.models import (
    M6ComponentMembership,
    M6FrameComputation,
)
from moltrack.analysis.domain_analysis.session_state import (
    DomainAnalysisClassifierCacheRecord,
    DomainAnalysisM6CacheRecord,
    DomainAnalysisSessionDiagnostic,
)

from .domain_analysis_classifier_payload import (
    classifier_configuration_from_payload,
    classifier_configuration_to_payload,
    molecule_classification_from_payload,
    molecule_classification_to_payload,
)
from .domain_backend_payload import (
    backend_evidence_from_payload,
    backend_evidence_to_payload,
    backend_identity_from_payload,
    backend_identity_to_payload,
)
from .domain_analysis_payload_validation import (
    float_pair_field,
    integer_field,
    integer_pairs_field,
    list_field,
    mapping,
    number_field,
    optional_text_field,
    pairs_to_lists,
    required,
    text_field,
    text_list_field,
)


CACHE_SCHEMA_VERSION = 3


def domain_analysis_cache_to_payload(
    m6_records: tuple[DomainAnalysisM6CacheRecord, ...],
    classifier_records: tuple[DomainAnalysisClassifierCacheRecord, ...],
) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "m6_frames": [_m6_record_to_payload(value) for value in m6_records],
        "classifier_frames": [
            _classifier_record_to_payload(value)
            for value in classifier_records
        ],
    }


def domain_analysis_cache_from_payload(
    payload: Any,
) -> tuple[
    tuple[DomainAnalysisM6CacheRecord, ...],
    tuple[DomainAnalysisClassifierCacheRecord, ...],
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    path = "domain_analysis.cache"
    saved = mapping(payload, path)
    version = integer_field(saved, "schema_version", path)
    if version == 1:
        raise ValueError(
            "Domain Analysis cache schema_version 1 lacks source-kind "
            "provenance and was discarded."
        )
    if version != CACHE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported {path} schema_version: {version}.")
    diagnostics: list[DomainAnalysisSessionDiagnostic] = []
    m6_records: list[DomainAnalysisM6CacheRecord] = []
    for index, value in enumerate(list_field(saved, "m6_frames", path)):
        item_path = f"{path}.m6_frames[{index}]"
        try:
            m6_records.append(_m6_record_from_payload(value, path=item_path))
        except (TypeError, ValueError) as exc:
            diagnostics.append(DomainAnalysisSessionDiagnostic(
                component="m6_cache",
                identifier=item_path,
                schema_version=str(version),
                reason=str(exc),
            ))
    classifier_records: list[DomainAnalysisClassifierCacheRecord] = []
    for index, value in enumerate(
        list_field(saved, "classifier_frames", path)
    ):
        item_path = f"{path}.classifier_frames[{index}]"
        try:
            classifier_records.append(
                _classifier_record_from_payload(value, path=item_path)
            )
        except (TypeError, ValueError) as exc:
            diagnostics.append(DomainAnalysisSessionDiagnostic(
                component="classifier_cache",
                identifier=item_path,
                schema_version=str(version),
                reason=str(exc),
            ))
    m6_records = _without_conflicting_m6_records(
        m6_records,
        diagnostics=diagnostics,
        schema_version=version,
    )
    classifier_records = _without_conflicting_classifier_records(
        classifier_records,
        diagnostics=diagnostics,
        schema_version=version,
    )
    return tuple(m6_records), tuple(classifier_records), tuple(diagnostics)


def _without_conflicting_m6_records(
    records: list[DomainAnalysisM6CacheRecord],
    *,
    diagnostics: list[DomainAnalysisSessionDiagnostic],
    schema_version: int,
) -> list[DomainAnalysisM6CacheRecord]:
    by_key: dict[M6FrameCacheKey, list[DomainAnalysisM6CacheRecord]] = {}
    for record in records:
        by_key.setdefault(record.key, []).append(record)
    restored: list[DomainAnalysisM6CacheRecord] = []
    for key, values in by_key.items():
        if any(value.computation != values[0].computation for value in values[1:]):
            diagnostics.append(DomainAnalysisSessionDiagnostic(
                component="m6_cache",
                identifier=key.physical_frame_id,
                schema_version=str(schema_version),
                reason="All conflicting records for the same M6 key were skipped.",
            ))
        else:
            restored.append(values[0])
    return restored


def _without_conflicting_classifier_records(
    records: list[DomainAnalysisClassifierCacheRecord],
    *,
    diagnostics: list[DomainAnalysisSessionDiagnostic],
    schema_version: int,
) -> list[DomainAnalysisClassifierCacheRecord]:
    by_key: dict[
        ClassifierFrameCacheKey,
        list[DomainAnalysisClassifierCacheRecord],
    ] = {}
    for record in records:
        by_key.setdefault(record.key, []).append(record)
    restored: list[DomainAnalysisClassifierCacheRecord] = []
    for key, values in by_key.items():
        if any(value.record != values[0].record for value in values[1:]):
            diagnostics.append(DomainAnalysisSessionDiagnostic(
                component="classifier_cache",
                identifier=(
                    f"{key.physical_frame_id}:"
                    f"{key.configuration.identity.classifier_id}"
                ),
                schema_version=str(schema_version),
                reason=(
                    "All conflicting records for the same classifier key were "
                    "skipped."
                ),
            ))
        else:
            restored.append(values[0])
    return restored


def _m6_record_to_payload(
    value: DomainAnalysisM6CacheRecord,
) -> dict[str, Any]:
    key = value.key
    computation = _m6_computation_to_payload(value.computation)
    return {
        "key": {
            "physical_frame_id": key.physical_frame_id,
            "geometry_mode": key.geometry_mode,
            "coordinate_transform_fingerprint": (
                key.coordinate_transform_fingerprint
            ),
            "backend_identity": backend_identity_to_payload(
                key.backend_identity
            ),
        },
        "computation": computation,
        "result_fingerprint": canonical_sha256(computation),
    }


def _m6_record_from_payload(
    payload: Any,
    *,
    path: str,
) -> DomainAnalysisM6CacheRecord:
    saved = mapping(payload, path)
    if saved.get("status", "completed") != "completed":
        raise ValueError(f"{path} is an incomplete M6 cache record.")
    key_path = f"{path}.key"
    key_payload = mapping(required(saved, "key", path), key_path)
    computation_payload = required(saved, "computation", path)
    computation = _m6_computation_from_payload(
        computation_payload,
        path=f"{path}.computation",
    )
    expected_fingerprint = text_field(saved, "result_fingerprint", path)
    if canonical_sha256(computation_payload) != expected_fingerprint:
        raise ValueError(f"{path}.result_fingerprint does not match its result.")
    return DomainAnalysisM6CacheRecord(
        key=M6FrameCacheKey(
            physical_frame_id=text_field(
                key_payload, "physical_frame_id", key_path
            ),
            geometry_mode=cast(
                GeometryMode,
                text_field(key_payload, "geometry_mode", key_path),
            ),
            coordinate_transform_fingerprint=text_field(
                key_payload,
                "coordinate_transform_fingerprint",
                key_path,
            ),
            backend_identity=backend_identity_from_payload(
                required(key_payload, "backend_identity", key_path),
                path=f"{key_path}.backend_identity",
            ),
        ),
        computation=computation,
    )


def _m6_computation_to_payload(value: M6FrameComputation) -> dict[str, Any]:
    if value.backend_identity is None or value.native_evidence is None:
        raise ValueError("Only backend-qualified M6 computations can be saved.")
    return {
        "frame_index": value.frame_index,
        "molecules": [_molecule_to_payload(item) for item in value.molecules],
        "analyzed_pixels_xy": pairs_to_lists(value.analyzed_pixels_xy),
        "pixel_area_nm2": value.pixel_area_nm2,
        "full_domains": [
            _membership_to_payload(item) for item in value.full_domains
        ],
        "small_ordered_islands": [
            _membership_to_payload(item)
            for item in value.small_ordered_islands
        ],
        "coordinate_frame": value.coordinate_frame,
        "coordinate_transform_fingerprint": (
            value.coordinate_transform_fingerprint
        ),
        "backend_identity": backend_identity_to_payload(value.backend_identity),
        "native_evidence": backend_evidence_to_payload(value.native_evidence),
        "result_fingerprint": value.result_fingerprint,
    }


def _m6_computation_from_payload(
    payload: Any,
    *,
    path: str,
) -> M6FrameComputation:
    saved = mapping(payload, path)
    return M6FrameComputation(
        frame_index=integer_field(saved, "frame_index", path),
        molecules=tuple(
            _molecule_from_payload(
                value,
                path=f"{path}.molecules[{index}]",
            )
            for index, value in enumerate(list_field(saved, "molecules", path))
        ),
        analyzed_pixels_xy=integer_pairs_field(
            saved, "analyzed_pixels_xy", path
        ),
        pixel_area_nm2=number_field(saved, "pixel_area_nm2", path),
        full_domains=tuple(
            _membership_from_payload(
                value,
                path=f"{path}.full_domains[{index}]",
            )
            for index, value in enumerate(
                list_field(saved, "full_domains", path)
            )
        ),
        small_ordered_islands=tuple(
            _membership_from_payload(
                value,
                path=f"{path}.small_ordered_islands[{index}]",
            )
            for index, value in enumerate(
                list_field(saved, "small_ordered_islands", path)
            )
        ),
        coordinate_frame=text_field(saved, "coordinate_frame", path),
        coordinate_transform_fingerprint=text_field(
            saved,
            "coordinate_transform_fingerprint",
            path,
        ),
        backend_identity=backend_identity_from_payload(
            required(saved, "backend_identity", path),
            path=f"{path}.backend_identity",
        ),
        native_evidence=backend_evidence_from_payload(
            required(saved, "native_evidence", path),
            path=f"{path}.native_evidence",
        ),
    )


def _molecule_to_payload(value: M6AnalyzedMolecule) -> dict[str, Any]:
    return {
        "source_id": value.source_id,
        "source_kind": value.source_kind,
        "raw_centroid_xy": list(value.raw_centroid_xy),
        "centroid_xy_nm": list(value.centroid_xy_nm),
        "footprint_pixels_xy": pairs_to_lists(value.footprint_pixels_xy),
    }


def _molecule_from_payload(payload: Any, *, path: str) -> M6AnalyzedMolecule:
    saved = mapping(payload, path)
    return M6AnalyzedMolecule(
        source_id=text_field(saved, "source_id", path),
        source_kind=cast(
            MoleculeSourceKind,
            text_field(saved, "source_kind", path),
        ),
        raw_centroid_xy=float_pair_field(saved, "raw_centroid_xy", path),
        centroid_xy_nm=float_pair_field(saved, "centroid_xy_nm", path),
        footprint_pixels_xy=integer_pairs_field(
            saved, "footprint_pixels_xy", path
        ),
    )


def _membership_to_payload(value: M6ComponentMembership) -> dict[str, Any]:
    return {
        "lattice_domain_id": value.lattice_domain_id,
        "source_ids": list(value.source_ids),
        "core_source_ids": list(value.core_source_ids),
        "halo_source_ids": list(value.halo_source_ids),
        "qc_flags": list(value.qc_flags),
    }


def _membership_from_payload(
    payload: Any,
    *,
    path: str,
) -> M6ComponentMembership:
    saved = mapping(payload, path)
    return M6ComponentMembership(
        lattice_domain_id=text_field(saved, "lattice_domain_id", path),
        source_ids=tuple(text_list_field(saved, "source_ids", path)),
        core_source_ids=tuple(
            text_list_field(saved, "core_source_ids", path)
        ),
        halo_source_ids=tuple(
            text_list_field(saved, "halo_source_ids", path)
        ),
        qc_flags=tuple(text_list_field(saved, "qc_flags", path)),
    )


def _classifier_record_to_payload(
    value: DomainAnalysisClassifierCacheRecord,
) -> dict[str, Any]:
    key = value.key
    return {
        "key": {
            "physical_frame_id": key.physical_frame_id,
            "configuration": classifier_configuration_to_payload(
                key.configuration
            ),
            "m6_gate_fingerprint": key.m6_gate_fingerprint,
            "raw_frame_fingerprint": key.raw_frame_fingerprint,
            "raw_sampling_geometry_fingerprint": (
                key.raw_sampling_geometry_fingerprint
            ),
        },
        "record": {
            "classifications": [
                molecule_classification_to_payload(item)
                for item in value.record.classifications
            ],
            "result_fingerprint": value.record.result_fingerprint,
        },
    }


def _classifier_record_from_payload(
    payload: Any,
    *,
    path: str,
) -> DomainAnalysisClassifierCacheRecord:
    saved = mapping(payload, path)
    if saved.get("status", "completed") != "completed":
        raise ValueError(f"{path} is an incomplete classifier cache record.")
    key_path = f"{path}.key"
    key_payload = mapping(required(saved, "key", path), key_path)
    configuration = classifier_configuration_from_payload(
        required(key_payload, "configuration", key_path),
        path=f"{key_path}.configuration",
    )
    record_path = f"{path}.record"
    record_payload = mapping(required(saved, "record", path), record_path)
    classifications = tuple(
        molecule_classification_from_payload(
            value,
            configuration,
            path=f"{record_path}.classifications[{index}]",
        )
        for index, value in enumerate(
            list_field(record_payload, "classifications", record_path)
        )
    )
    return DomainAnalysisClassifierCacheRecord(
        key=ClassifierFrameCacheKey(
            physical_frame_id=text_field(
                key_payload, "physical_frame_id", key_path
            ),
            configuration=configuration,
            m6_gate_fingerprint=text_field(
                key_payload, "m6_gate_fingerprint", key_path
            ),
            raw_frame_fingerprint=optional_text_field(
                key_payload, "raw_frame_fingerprint", key_path
            ),
            raw_sampling_geometry_fingerprint=text_field(
                key_payload,
                "raw_sampling_geometry_fingerprint",
                key_path,
            ),
        ),
        record=ClassifierFrameCacheRecord(
            classifications=classifications,
            result_fingerprint=text_field(
                record_payload, "result_fingerprint", record_path
            ),
        ),
    )
