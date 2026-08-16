from __future__ import annotations

from .m6_reference_payload import (
    M6_REFERENCE_TABLE_FILES,
    build_m6_reference_tables,
)
from .m6_reference_schema import (
    M6_REFERENCE_DATASET_VERSION,
    M6ReferenceDatasetPublication,
    M6ReferenceDatasetSettings,
    M6ReferenceMeasurementGroup,
)
from .reference_dataset import (
    ReferenceDatasetDraft,
    ReferencePartitionIdentity,
    ReferenceDatasetPublicationCandidate,
    prepare_reference_dataset,
    reference_json_lines_file,
)


def publish_m6_reference_dataset(
    measurements: tuple[M6ReferenceMeasurementGroup, ...],
    settings: M6ReferenceDatasetSettings,
) -> M6ReferenceDatasetPublication:
    """Validate and atomically publish an immutable M6 dataset version."""

    return prepare_m6_reference_dataset(measurements, settings).publish()


def prepare_m6_reference_dataset(
    measurements: tuple[M6ReferenceMeasurementGroup, ...],
    settings: M6ReferenceDatasetSettings,
) -> ReferenceDatasetPublicationCandidate:
    """Prepare an operator preview backed by the production publisher."""

    if not isinstance(settings, M6ReferenceDatasetSettings):
        raise TypeError("settings must be M6ReferenceDatasetSettings.")
    measurements = tuple(measurements)
    tables = build_m6_reference_tables(tuple(measurements))
    return prepare_reference_dataset(ReferenceDatasetDraft(
        target="m6",
        settings=settings,
        initial_dataset_version=M6_REFERENCE_DATASET_VERSION,
        payload_files=tuple(
            reference_json_lines_file(name, tables.tables[name])
            for name in M6_REFERENCE_TABLE_FILES
        ),
        partitions=tuple(
            ReferencePartitionIdentity(
                split=split,
                measurement_group_count=tables.measurement_group_count(split),
                partition_fingerprint=tables.partition_fingerprint(split),
            )
            for split in ("calibration", "validation")
        ),
        source_revisions=tuple(
            value.source_revision for value in measurements
        ),
    ))


__all__ = ["prepare_m6_reference_dataset", "publish_m6_reference_dataset"]
