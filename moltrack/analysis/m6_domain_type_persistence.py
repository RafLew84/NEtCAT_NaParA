from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .frame_ranges import MolecularFrameRange, MolecularFrameRangeAnalysisScope
from .m6_domain_type_aggregates import M6DomainTypeRangeAggregate
from .m6_domain_type_lifecycle import M6DomainTypeAnalysisOutcome
from .m6_domain_type_observations import M6DomainTypeObservation
from .m6_domain_type_range_comparison import (
    M6DomainTypeRangeComparison,
    M6DomainTypeRangeComparisonRow,
    M6DomainTypeRangeDeltas,
    M6DomainTypeRangeSide,
)
from .m6_domain_type_results import (
    M6DomainType,
    M6DomainTypeAssignment,
    M6DomainTypeClassificationQcReport,
    M6DomainTypeClassificationResult,
)
from .m6_domain_type_settings import M6DomainTypeClassificationSettings
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .m6_single_range_domain_type_summary import (
    M6SingleRangeDomainTypeRow,
    M6SingleRangeDomainTypeSummary,
    M6SingleRangeFrameMapping,
)


M6_DOMAIN_TYPE_CONFIGURATION_SCHEMA_VERSION = 1
M6_DOMAIN_TYPE_CACHE_RECORD_SCHEMA_VERSION = 1
M6_DOMAIN_TYPE_ALGORITHM_VERSION = "complete-linkage-domain-types-v1"

_OBSERVATION_FIELDS = (
    "range_name", "range_start_frame", "range_end_frame", "source_view",
    "m6_settings_fingerprint", "m6_context_fingerprint", "frame_index",
    "source_frame_index", "ordered_component_id", "m6_orientation_domain_id",
    "component_type", "qualification_status", "unclassified_reason",
    "orientation_deg", "molecule_count",
    "molecule_fraction_of_valid_representatives", "footprint_area_nm2",
    "footprint_fraction_of_valid_fov", "molecular_mask_area_nm2",
    "domain_mean_local_q6", "domain_coherent_q6", "centroid_x_nm",
    "centroid_y_nm", "min_x_nm", "min_y_nm", "max_x_nm", "max_y_nm",
    "internal_first_shell_bond_count", "domain_median_bond_length_nm",
    "domain_bond_length_mad_nm", "domain_bond_length_iqr_nm",
    "domain_bond_length_robust_cv", "insufficient_bonds_for_length_stats_qc",
    "bond_length_heterogeneity_qc", "edge_truncated",
    "footprint_disconnected_qc",
)
_DOMAIN_TYPE_FIELDS = (
    "domain_type_id", "prototype_orientation_deg", "prototype_bond_length_nm",
    "orientation_circular_spread_deg", "bond_length_iqr_nm", "observation_count",
)
_ASSIGNMENT_FIELDS = (
    "observation_key", "status", "domain_type_id", "unclassified_reason",
)
_QC_REPORT_FIELDS = (
    "observation_count", "classified_observation_count",
    "unclassified_observation_count", "unclassified_reason_counts",
)
_RANGE_AGGREGATE_FIELDS = (
    "domain_type_id", "label", "available_frame_count",
    "valid_representative_fraction_frame_count", "valid_fov_fraction_frame_count",
    "observation_count", "frames_with_type_count",
    "mean_instances_per_available_frame",
    "mean_molecule_fraction_of_valid_representatives",
    "mean_footprint_fraction_of_valid_fov", "mean_domain_coherent_q6",
    "mean_molecule_count", "mean_footprint_area_nm2",
)
_FRAME_MAPPING_FIELDS = (
    "working_frame_index", "source_frame_index", "m6_availability_status",
    "m6_unavailability_reason",
)
_RANGE_DELTAS_FIELDS = (
    "domain_instance_count", "frames_with_type_count",
    "frames_with_type_percentage_points",
    "mean_domain_instances_per_available_frame",
    "mean_molecule_fraction_percentage_points",
    "mean_footprint_fraction_percentage_points", "mean_domain_coherent_q6",
    "mean_molecule_count", "mean_footprint_area_nm2",
)
_SUMMARY_SCALAR_FIELDS = (
    "source_view", "classification_input_fingerprint", "analyzed_frame_count",
    "available_frame_count", "valid_representative_fraction_frame_count",
    "valid_fov_fraction_frame_count", "frames_with_full_domain_count",
    "frames_with_full_domain_percent", "mean_full_domains_per_available_frame",
    "median_full_domains_per_available_frame", "max_full_domains_per_available_frame",
    "domain_observation_count", "domain_type_count",
    "unclassified_observation_count", "full_domain_molecule_fraction",
    "full_domain_footprint_fraction",
)
_SUMMARY_FIELDS = {
    *_SUMMARY_SCALAR_FIELDS,
    "frame_range", "frame_mapping", "unclassified_aggregate", "type_summaries",
}


class M6DomainTypeCacheDecodeError(ValueError):
    """A cache record is unsupported, corrupt, or internally inconsistent."""


@dataclass(frozen=True)
class M6DomainTypeCacheRecord:
    """Optional reproducible result guarded by its complete scientific context."""

    algorithm_version: str
    analysis_scope: MolecularFrameRangeAnalysisScope
    m6_context_fingerprint: str
    input_fingerprint: str
    context_fingerprint: str
    outcome: M6DomainTypeAnalysisOutcome
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.algorithm_version != M6_DOMAIN_TYPE_ALGORITHM_VERSION:
            raise ValueError("Unsupported M6 domain type algorithm version.")
        if not isinstance(self.analysis_scope, MolecularFrameRangeAnalysisScope):
            raise TypeError("analysis_scope must be a frame range analysis scope.")
        if not isinstance(self.outcome, M6DomainTypeAnalysisOutcome):
            raise TypeError("outcome must be an M6 domain type analysis outcome.")
        for field_name in (
            "m6_context_fingerprint",
            "input_fingerprint",
            "context_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty.")
            object.__setattr__(self, field_name, value)
        if self.uses_tracking is not False:
            raise ValueError("M6 domain type cache must not use tracking.")
        classification = self.outcome.classification
        if classification is None:
            raise ValueError("A reproducible domain type cache requires classification.")
        if self.analysis_scope != self.outcome.analysis_scope:
            raise ValueError("Cache scope and outcome scope must match.")
        if self.m6_context_fingerprint != classification.m6_context_fingerprint:
            raise ValueError("Cache M6 context fingerprint does not match the result.")
        if self.input_fingerprint != classification.input_fingerprint:
            raise ValueError("Cache input fingerprint does not match the result.")
        if self.context_fingerprint != self.outcome.context_fingerprint:
            raise ValueError("Cache analysis context fingerprint does not match the result.")
        object.__setattr__(self, "uses_tracking", False)

    @classmethod
    def from_outcome(
        cls,
        outcome: M6DomainTypeAnalysisOutcome,
    ) -> "M6DomainTypeCacheRecord":
        if not isinstance(outcome, M6DomainTypeAnalysisOutcome):
            raise TypeError("outcome must be an M6 domain type analysis outcome.")
        classification = outcome.classification
        if classification is None:
            raise ValueError("A reproducible domain type cache requires classification.")
        return cls(
            algorithm_version=M6_DOMAIN_TYPE_ALGORITHM_VERSION,
            analysis_scope=outcome.analysis_scope,
            m6_context_fingerprint=classification.m6_context_fingerprint,
            input_fingerprint=classification.input_fingerprint,
            context_fingerprint=outcome.context_fingerprint,
            outcome=outcome,
        )

    def matches_context(
        self,
        *,
        analysis_scope: MolecularFrameRangeAnalysisScope,
        m6_context_fingerprint: str,
        context_fingerprint: str,
    ) -> bool:
        if not isinstance(analysis_scope, MolecularFrameRangeAnalysisScope):
            return False
        if (
            analysis_scope != self.analysis_scope
            or str(m6_context_fingerprint).strip() != self.m6_context_fingerprint
        ):
            return False
        return str(context_fingerprint).strip() == self.context_fingerprint

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_record_schema_version": M6_DOMAIN_TYPE_CACHE_RECORD_SCHEMA_VERSION,
            "algorithm_version": self.algorithm_version,
            "analysis_scope": self.analysis_scope.to_dict(),
            "m6_context_fingerprint": self.m6_context_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "context_fingerprint": self.context_fingerprint,
            "uses_tracking": False,
            "outcome": _outcome_to_payload(self.outcome),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "M6DomainTypeCacheRecord":
        try:
            return cls._from_dict(payload)
        except M6DomainTypeCacheDecodeError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise M6DomainTypeCacheDecodeError(
                "M6 domain type cache record cannot be restored."
            ) from exc

    @classmethod
    def _from_dict(cls, payload: Mapping[str, object]) -> "M6DomainTypeCacheRecord":
        record = _exact_mapping(
            payload,
            required={
                "cache_record_schema_version",
                "algorithm_version",
                "analysis_scope",
                "m6_context_fingerprint",
                "input_fingerprint",
                "context_fingerprint",
                "uses_tracking",
                "outcome",
            },
            label="M6 domain type cache record",
        )
        if record["cache_record_schema_version"] != M6_DOMAIN_TYPE_CACHE_RECORD_SCHEMA_VERSION:
            raise ValueError("Unsupported M6 domain type cache record schema version.")
        if record["uses_tracking"] is not False:
            raise ValueError("M6 domain type cache must declare uses_tracking=false.")
        return cls(
            algorithm_version=record["algorithm_version"],
            analysis_scope=MolecularFrameRangeAnalysisScope.from_dict(
                _mapping(record["analysis_scope"], "analysis_scope")
            ),
            m6_context_fingerprint=record["m6_context_fingerprint"],
            input_fingerprint=record["input_fingerprint"],
            context_fingerprint=record["context_fingerprint"],
            outcome=_outcome_from_payload(record["outcome"]),
        )


@dataclass(frozen=True)
class M6DomainTypeSessionState:
    """Versioned domain-type settings plus an independently optional cache."""

    analysis_scope: MolecularFrameRangeAnalysisScope
    classification_settings: M6DomainTypeClassificationSettings
    cache_record: M6DomainTypeCacheRecord | None = None
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.analysis_scope, MolecularFrameRangeAnalysisScope):
            raise TypeError("analysis_scope must be a frame range analysis scope.")
        if not isinstance(
            self.classification_settings,
            M6DomainTypeClassificationSettings,
        ):
            raise TypeError("classification_settings must be domain type settings.")
        if self.cache_record is not None:
            if not isinstance(self.cache_record, M6DomainTypeCacheRecord):
                raise TypeError("cache_record must be an M6 domain type cache or None.")
            if self.cache_record.analysis_scope != self.analysis_scope:
                raise ValueError("Configuration and cache scopes must match.")
            classification = self.cache_record.outcome.classification
            assert classification is not None
            if classification.classification_settings != self.classification_settings:
                raise ValueError("Configuration and cache settings must match.")
        if self.uses_tracking is not False:
            raise ValueError("M6 domain type analysis must not use tracking.")
        object.__setattr__(self, "uses_tracking", False)

    @classmethod
    def from_outcome(
        cls,
        outcome: M6DomainTypeAnalysisOutcome,
    ) -> "M6DomainTypeSessionState":
        cache_record = M6DomainTypeCacheRecord.from_outcome(outcome)
        classification = outcome.classification
        assert classification is not None
        return cls(
            analysis_scope=outcome.analysis_scope,
            classification_settings=classification.classification_settings,
            cache_record=cache_record,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "configuration_schema_version": M6_DOMAIN_TYPE_CONFIGURATION_SCHEMA_VERSION,
            "analysis_scope": self.analysis_scope.to_dict(),
            "classification_settings": self.classification_settings.to_dict(),
            "uses_tracking": False,
            "reproducible_cache": (
                None if self.cache_record is None else self.cache_record.to_dict()
            ),
        }

    def restore_outcome_for(
        self,
        *,
        analysis_scope: MolecularFrameRangeAnalysisScope,
        m6_context_fingerprint: str,
        context_fingerprint: str,
    ) -> M6DomainTypeAnalysisOutcome | None:
        """Approve the pending cache only for the exact recomputed context."""

        cache_record = self.cache_record
        if cache_record is None or not cache_record.matches_context(
            analysis_scope=analysis_scope,
            m6_context_fingerprint=m6_context_fingerprint,
            context_fingerprint=context_fingerprint,
        ):
            return None
        return cache_record.outcome

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "M6DomainTypeSessionState":
        state = _exact_mapping(
            payload,
            required={
                "configuration_schema_version",
                "analysis_scope",
                "classification_settings",
                "uses_tracking",
                "reproducible_cache",
            },
            label="M6 domain type analysis state",
        )
        if state["configuration_schema_version"] != M6_DOMAIN_TYPE_CONFIGURATION_SCHEMA_VERSION:
            raise ValueError("Unsupported M6 domain type configuration schema version.")
        if state["uses_tracking"] is not False:
            raise ValueError("M6 domain type state must declare uses_tracking=false.")
        analysis_scope = MolecularFrameRangeAnalysisScope.from_dict(
            _mapping(state["analysis_scope"], "analysis_scope")
        )
        settings = M6DomainTypeClassificationSettings.from_dict(
            _mapping(state["classification_settings"], "classification_settings")
        )
        cache_record = None
        if state["reproducible_cache"] is not None:
            try:
                cache_record = M6DomainTypeCacheRecord.from_dict(
                    _mapping(state["reproducible_cache"], "reproducible_cache")
                )
                candidate = cls(
                    analysis_scope=analysis_scope,
                    classification_settings=settings,
                    cache_record=cache_record,
                )
            except M6DomainTypeCacheDecodeError:
                cache_record = None
            else:
                return candidate
        return cls(
            analysis_scope=analysis_scope,
            classification_settings=settings,
            cache_record=cache_record,
        )


def _outcome_to_payload(outcome: M6DomainTypeAnalysisOutcome) -> dict[str, object]:
    return {
        "status": outcome.status,
        "status_message": outcome.status_message,
        "context_fingerprint": outcome.context_fingerprint,
        "analysis_scope": outcome.analysis_scope.to_dict(),
        "available_m6_frame_count": outcome.available_m6_frame_count,
        "uses_tracking": False,
        "classification": _classification_to_payload(outcome.classification),
        "table_result": _table_result_to_payload(outcome.table_result),
    }


def _outcome_from_payload(payload: object) -> M6DomainTypeAnalysisOutcome:
    value = _exact_mapping(
        payload,
        required={
            "status",
            "status_message",
            "context_fingerprint",
            "analysis_scope",
            "available_m6_frame_count",
            "uses_tracking",
            "classification",
            "table_result",
        },
        label="domain type outcome",
    )
    if value["uses_tracking"] is not False:
        raise ValueError("Domain type outcome must declare uses_tracking=false.")
    classification = (
        None
        if value["classification"] is None
        else _classification_from_payload(value["classification"])
    )
    table_result = (
        None
        if value["table_result"] is None
        else _table_result_from_payload(value["table_result"])
    )
    return M6DomainTypeAnalysisOutcome(
        status=value["status"],
        status_message=value["status_message"],
        context_fingerprint=value["context_fingerprint"],
        analysis_scope=MolecularFrameRangeAnalysisScope.from_dict(
            _mapping(value["analysis_scope"], "analysis_scope")
        ),
        available_m6_frame_count=value["available_m6_frame_count"],
        classification=classification,
        table_result=table_result,
    )


def _classification_to_payload(
    value: M6DomainTypeClassificationResult | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "analysis_scope": value.analysis_scope.to_dict(),
        "classification_settings": value.classification_settings.to_dict(),
        "m6_settings": value.m6_settings.to_dict(),
        "m6_context_fingerprint": value.m6_context_fingerprint,
        "input_fingerprint": value.input_fingerprint,
        "observations": [
            _simple_payload(item, _OBSERVATION_FIELDS)
            for item in value.observations
        ],
        "domain_types": [
            _simple_payload(item, _DOMAIN_TYPE_FIELDS)
            for item in value.domain_types
        ],
        "assignments": [
            _simple_payload(item, _ASSIGNMENT_FIELDS)
            for item in value.assignments
        ],
        "qc_report": _simple_payload(value.qc_report, _QC_REPORT_FIELDS),
        "uses_tracking": False,
    }


def _classification_from_payload(payload: object) -> M6DomainTypeClassificationResult:
    value = _exact_mapping(
        payload,
        required={
            "analysis_scope",
            "classification_settings",
            "m6_settings",
            "m6_context_fingerprint",
            "input_fingerprint",
            "observations",
            "domain_types",
            "assignments",
            "qc_report",
            "uses_tracking",
        },
        label="domain type classification",
    )
    if value["uses_tracking"] is not False:
        raise ValueError("Domain type classification must declare uses_tracking=false.")
    return M6DomainTypeClassificationResult(
        analysis_scope=MolecularFrameRangeAnalysisScope.from_dict(
            _mapping(value["analysis_scope"], "classification analysis_scope")
        ),
        classification_settings=M6DomainTypeClassificationSettings.from_dict(
            _mapping(value["classification_settings"], "classification settings")
        ),
        m6_settings=MolecularM6OrientationAnalysisSettings.from_dict(
            _mapping(value["m6_settings"], "M6 settings")
        ),
        m6_context_fingerprint=value["m6_context_fingerprint"],
        input_fingerprint=value["input_fingerprint"],
        observations=tuple(
            _simple_from_payload(
                M6DomainTypeObservation,
                item,
                _OBSERVATION_FIELDS,
            )
            for item in _sequence(value["observations"], "observations")
        ),
        domain_types=tuple(
            _simple_from_payload(M6DomainType, item, _DOMAIN_TYPE_FIELDS)
            for item in _sequence(value["domain_types"], "domain_types")
        ),
        assignments=tuple(
            _assignment_from_payload(item)
            for item in _sequence(value["assignments"], "assignments")
        ),
        qc_report=_simple_from_payload(
            M6DomainTypeClassificationQcReport,
            value["qc_report"],
            _QC_REPORT_FIELDS,
        ),
    )


def _table_result_to_payload(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, M6SingleRangeDomainTypeSummary):
        return {"result_kind": "single_range", "summary": _summary_to_payload(value)}
    if isinstance(value, M6DomainTypeRangeComparison):
        return {
            "result_kind": "compare_ranges",
            "first_summary": _summary_to_payload(value.first_summary),
            "second_summary": _summary_to_payload(value.second_summary),
            "rows": [_comparison_row_to_payload(row) for row in value.rows],
        }
    raise TypeError("Unsupported M6 domain type table result.")


def _table_result_from_payload(payload: object) -> object:
    value = _mapping(payload, "domain type table result")
    result_kind = value.get("result_kind")
    if result_kind == "single_range":
        exact = _exact_mapping(
            value,
            required={"result_kind", "summary"},
            label="single-range domain type table",
        )
        return _summary_from_payload(exact["summary"])
    if result_kind == "compare_ranges":
        exact = _exact_mapping(
            value,
            required={"result_kind", "first_summary", "second_summary", "rows"},
            label="domain type comparison table",
        )
        return M6DomainTypeRangeComparison(
            first_summary=_summary_from_payload(exact["first_summary"]),
            second_summary=_summary_from_payload(exact["second_summary"]),
            rows=tuple(
                _comparison_row_from_payload(row)
                for row in _sequence(exact["rows"], "comparison rows")
            ),
        )
    raise ValueError("Unsupported M6 domain type table result kind.")


def _summary_to_payload(value: M6SingleRangeDomainTypeSummary) -> dict[str, object]:
    scalar_fields = {
        field_name: _json_value(getattr(value, field_name))
        for field_name in _SUMMARY_SCALAR_FIELDS
    }
    return {
        **scalar_fields,
        "frame_range": _frame_range_to_payload(value.frame_range),
        "frame_mapping": [
            _simple_payload(item, _FRAME_MAPPING_FIELDS)
            for item in value.frame_mapping
        ],
        "unclassified_aggregate": _simple_payload(
            value.unclassified_aggregate,
            _RANGE_AGGREGATE_FIELDS,
        ),
        "type_summaries": [
            {
                "domain_type": _simple_payload(
                    item.domain_type,
                    _DOMAIN_TYPE_FIELDS,
                ),
                "range_aggregate": _simple_payload(
                    item.range_aggregate,
                    _RANGE_AGGREGATE_FIELDS,
                ),
                "frames_with_type_percent": item.frames_with_type_percent,
            }
            for item in value.type_summaries
        ],
    }


def _summary_from_payload(payload: object) -> M6SingleRangeDomainTypeSummary:
    value = _exact_mapping(
        payload,
        required=_SUMMARY_FIELDS,
        label="single-range summary",
    )
    scalar = dict(value)
    scalar["frame_range"] = _frame_range_from_payload(value["frame_range"])
    scalar["frame_mapping"] = tuple(
        _simple_from_payload(
            M6SingleRangeFrameMapping,
            item,
            _FRAME_MAPPING_FIELDS,
        )
        for item in _sequence(value["frame_mapping"], "frame_mapping")
    )
    scalar["unclassified_aggregate"] = _simple_from_payload(
        M6DomainTypeRangeAggregate,
        value["unclassified_aggregate"],
        _RANGE_AGGREGATE_FIELDS,
    )
    scalar["type_summaries"] = tuple(
        _summary_row_from_payload(item)
        for item in _sequence(value["type_summaries"], "type_summaries")
    )
    return M6SingleRangeDomainTypeSummary(**scalar)


def _summary_row_from_payload(payload: object) -> M6SingleRangeDomainTypeRow:
    value = _exact_mapping(
        payload,
        required={"domain_type", "range_aggregate", "frames_with_type_percent"},
        label="single-range type row",
    )
    return M6SingleRangeDomainTypeRow(
        domain_type=_simple_from_payload(
            M6DomainType,
            value["domain_type"],
            _DOMAIN_TYPE_FIELDS,
        ),
        range_aggregate=_simple_from_payload(
            M6DomainTypeRangeAggregate,
            value["range_aggregate"],
            _RANGE_AGGREGATE_FIELDS,
        ),
        frames_with_type_percent=value["frames_with_type_percent"],
    )


def _assignment_from_payload(payload: object) -> M6DomainTypeAssignment:
    value = _exact_mapping(
        payload,
        required={
            "observation_key",
            "status",
            "domain_type_id",
            "unclassified_reason",
        },
        label="domain type assignment",
    )
    value["observation_key"] = tuple(
        _sequence(value["observation_key"], "observation_key")
    )
    return M6DomainTypeAssignment(**value)


def _comparison_row_to_payload(value: M6DomainTypeRangeComparisonRow) -> dict[str, object]:
    return {
        "domain_type": _simple_payload(value.domain_type, _DOMAIN_TYPE_FIELDS),
        "first": _range_side_to_payload(value.first),
        "second": _range_side_to_payload(value.second),
        "deltas": _simple_payload(value.deltas, _RANGE_DELTAS_FIELDS),
    }


def _comparison_row_from_payload(payload: object) -> M6DomainTypeRangeComparisonRow:
    value = _exact_mapping(
        payload,
        required={"domain_type", "first", "second", "deltas"},
        label="domain type comparison row",
    )
    return M6DomainTypeRangeComparisonRow(
        domain_type=_simple_from_payload(
            M6DomainType,
            value["domain_type"],
            _DOMAIN_TYPE_FIELDS,
        ),
        first=_range_side_from_payload(value["first"]),
        second=_range_side_from_payload(value["second"]),
        deltas=_simple_from_payload(
            M6DomainTypeRangeDeltas,
            value["deltas"],
            _RANGE_DELTAS_FIELDS,
        ),
    )


def _range_side_to_payload(value: M6DomainTypeRangeSide) -> dict[str, object]:
    return {
        "range_aggregate": _simple_payload(
            value.range_aggregate,
            _RANGE_AGGREGATE_FIELDS,
        ),
        "frames_with_type_percent": value.frames_with_type_percent,
    }


def _range_side_from_payload(payload: object) -> M6DomainTypeRangeSide:
    value = _exact_mapping(
        payload,
        required={"range_aggregate", "frames_with_type_percent"},
        label="domain type range side",
    )
    return M6DomainTypeRangeSide(
        range_aggregate=_simple_from_payload(
            M6DomainTypeRangeAggregate,
            value["range_aggregate"],
            _RANGE_AGGREGATE_FIELDS,
        ),
        frames_with_type_percent=value["frames_with_type_percent"],
    )


def _frame_range_to_payload(value: MolecularFrameRange) -> dict[str, object]:
    return {
        "name": value.name,
        "start_frame": value.start_frame,
        "end_frame": value.end_frame,
    }


def _frame_range_from_payload(payload: object) -> MolecularFrameRange:
    value = _exact_mapping(
        payload,
        required={"name", "start_frame", "end_frame"},
        label="frame range",
    )
    return MolecularFrameRange(**value)


def _simple_payload(
    value: object,
    persisted_fields: tuple[str, ...],
) -> dict[str, object]:
    return {
        field_name: _json_value(getattr(value, field_name))
        for field_name in persisted_fields
    }


def _simple_from_payload(model_type, payload: object, persisted_fields):
    value = _exact_mapping(
        payload,
        required=set(persisted_fields),
        label=model_type.__name__,
    )
    return model_type(**value)


def _json_value(value: object) -> object:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping.")
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} field names must be strings.")
    return value


def _exact_mapping(
    value: object,
    *,
    required: set[str],
    label: str,
) -> dict[str, Any]:
    payload = dict(_mapping(value, label))
    unknown = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"Missing {label} fields: {', '.join(missing)}")
    return payload


def _sequence(value: object, label: str) -> list[object] | tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{label} must be a sequence.")
    return value
