from __future__ import annotations

from dataclasses import dataclass

from .data_models import MolTrackImageSeries
from .registration import MolTrackRegistrationResultSet, MolTrackRegistrationSettings


MOLTRACK_SESSION_SCHEMA_VERSION = 1
SUPPORTED_SESSION_REGISTRATION_VIEW_MODES = ("Show raw", "Show expanded aligned")


@dataclass(frozen=True)
class MolTrackSession:
    """Serializable state needed to restore a MolTrack working session."""

    source_path: str
    source_frame_indices: tuple[int, ...]
    active_frame_index: int
    reverse_frame_order: bool = False
    registration_view_mode: str = "Show raw"
    registration_settings: MolTrackRegistrationSettings | None = None
    registration_results: MolTrackRegistrationResultSet | None = None
    source_size_bytes: int | None = None
    source_mtime_ns: int | None = None
    schema_version: int = MOLTRACK_SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        source_path = str(self.source_path)
        if not source_path:
            raise ValueError("source_path must be a non-empty string.")
        source_frame_indices = tuple(int(index) for index in self.source_frame_indices)
        if not source_frame_indices:
            raise ValueError("source_frame_indices must contain at least one frame index.")
        if any(index < 0 for index in source_frame_indices):
            raise ValueError("source_frame_indices must be non-negative.")
        if len(set(source_frame_indices)) != len(source_frame_indices):
            raise ValueError("source_frame_indices must not contain duplicates.")

        active_frame_index = int(self.active_frame_index)
        if not 0 <= active_frame_index < len(source_frame_indices):
            raise IndexError("active_frame_index is out of source_frame_indices range.")

        registration_view_mode = str(self.registration_view_mode).strip()
        if registration_view_mode not in SUPPORTED_SESSION_REGISTRATION_VIEW_MODES:
            supported = ", ".join(SUPPORTED_SESSION_REGISTRATION_VIEW_MODES)
            raise ValueError(f"Unsupported registration_view_mode: {registration_view_mode!r}. Supported: {supported}.")

        schema_version = int(self.schema_version)
        if schema_version != MOLTRACK_SESSION_SCHEMA_VERSION:
            raise ValueError(f"Unsupported MolTrack session schema_version: {schema_version}.")

        source_size_bytes = _normalize_optional_non_negative_int(self.source_size_bytes, "source_size_bytes")
        source_mtime_ns = _normalize_optional_non_negative_int(self.source_mtime_ns, "source_mtime_ns")

        if self.registration_settings is not None and not isinstance(
            self.registration_settings, MolTrackRegistrationSettings
        ):
            raise TypeError("registration_settings must be a MolTrackRegistrationSettings instance.")
        if self.registration_results is not None and not isinstance(
            self.registration_results, MolTrackRegistrationResultSet
        ):
            raise TypeError("registration_results must be a MolTrackRegistrationResultSet instance.")
        if self.registration_results is not None:
            expected = tuple(range(len(source_frame_indices)))
            if self.registration_results.frame_indices != expected:
                raise ValueError("registration_results do not match source_frame_indices length.")
            if self.registration_settings is not None and self.registration_results.settings != self.registration_settings:
                raise ValueError("registration_settings must match registration_results.settings.")

        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "source_frame_indices", source_frame_indices)
        object.__setattr__(self, "active_frame_index", active_frame_index)
        object.__setattr__(self, "reverse_frame_order", bool(self.reverse_frame_order))
        object.__setattr__(self, "registration_view_mode", registration_view_mode)
        object.__setattr__(self, "source_size_bytes", source_size_bytes)
        object.__setattr__(self, "source_mtime_ns", source_mtime_ns)
        object.__setattr__(self, "schema_version", schema_version)

    @classmethod
    def from_image_series(
        cls,
        series: MolTrackImageSeries,
        *,
        registration_view_mode: str = "Show raw",
        source_size_bytes: int | None = None,
        source_mtime_ns: int | None = None,
    ) -> "MolTrackSession":
        if not isinstance(series, MolTrackImageSeries):
            raise TypeError("series must be a MolTrackImageSeries instance.")
        registration_results = series.registration_results
        registration_settings = registration_results.settings if registration_results is not None else None
        return cls(
            source_path=series.source_path,
            source_frame_indices=series.source_frame_indices,
            active_frame_index=series.active_frame_index,
            reverse_frame_order=series.reverse_frame_order,
            registration_view_mode=registration_view_mode,
            registration_settings=registration_settings,
            registration_results=registration_results,
            source_size_bytes=source_size_bytes,
            source_mtime_ns=source_mtime_ns,
        )


def _normalize_optional_non_negative_int(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative.")
    return normalized
