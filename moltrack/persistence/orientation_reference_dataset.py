from __future__ import annotations

from .orientation_reference_payload import (
    ORIENTATION_REFERENCE_TABLE_FILES,
    build_orientation_reference_payload,
)
from .orientation_reference_schema import (
    ORIENTATION_REFERENCE_DATASET_VERSION,
    OrientationReferenceDatasetPublication,
    OrientationReferenceDatasetSettings,
    OrientationReferenceMeasurementGroup,
)
from .reference_dataset import (
    ReferenceDatasetDraft,
    ReferencePartitionIdentity,
    publish_reference_dataset,
    reference_json_lines_file,
)


def publish_orientation_reference_dataset(
    measurements: tuple[OrientationReferenceMeasurementGroup, ...],
    settings: OrientationReferenceDatasetSettings,
) -> OrientationReferenceDatasetPublication:
    """Validate and publish one immutable Orientation dataset version."""

    if not isinstance(settings, OrientationReferenceDatasetSettings):
        raise TypeError("settings must be OrientationReferenceDatasetSettings.")
    payload = build_orientation_reference_payload(tuple(measurements))
    files = tuple(
        reference_json_lines_file(name, payload.tables[name])
        for name in ORIENTATION_REFERENCE_TABLE_FILES
    ) + payload.objects
    publication = publish_reference_dataset(ReferenceDatasetDraft(
        target="orientation",
        settings=settings,
        initial_dataset_version=ORIENTATION_REFERENCE_DATASET_VERSION,
        payload_files=files,
        partitions=tuple(
            ReferencePartitionIdentity(
                split=split,
                measurement_group_count=payload.measurement_group_count(split),
                partition_fingerprint=payload.partition_fingerprint(split),
            )
            for split in ("calibration", "validation")
        ),
    ))
    return OrientationReferenceDatasetPublication(
        package_path=publication.package_path,
        dataset_id=publication.dataset_id,
        version_id=publication.version_id,
        version_fingerprint=publication.version_fingerprint,
        validation_epoch_id=publication.validation_epoch_id,
        relative_files=publication.relative_files,
    )


__all__ = ["publish_orientation_reference_dataset"]
