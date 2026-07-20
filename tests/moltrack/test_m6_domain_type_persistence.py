from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from moltrack.analysis import (
    M6_DOMAIN_TYPE_ALGORITHM_VERSION,
    M6DomainTypeAnalysisOutcome,
    M6DomainTypeCacheRecord,
    M6DomainTypeSessionState,
    build_m6_domain_type_range_comparison,
    build_m6_single_range_domain_type_summary,
)
from moltrack.persistence import load_moltrack_session, save_moltrack_session

from test_m6_domain_type_range_comparison import (
    AFTER,
    BEFORE,
    _classification as _comparison_classification,
    _range_analysis as _comparison_range_analysis,
)
from test_m6_session_persistence import _series
from test_m6_single_range_domain_type_summary import (
    _classification as _single_classification,
    _observation as _single_observation,
    _range_analysis as _single_range_analysis,
)


def _single_outcome() -> M6DomainTypeAnalysisOutcome:
    observations = (
        _single_observation(
            0,
            10,
            10.0,
            4.0,
            range_end=1,
            molecule_fraction=0.2,
            footprint_fraction=0.1,
        ),
        _single_observation(
            1,
            11,
            11.0,
            4.1,
            range_end=1,
            molecule_fraction=0.3,
            footprint_fraction=0.2,
        ),
    )
    classification = _single_classification(observations, frame_count=2)
    table_result = build_m6_single_range_domain_type_summary(
        classification,
        _single_range_analysis(((1, 0.2, 0.1), (1, 0.3, 0.2))),
    )
    return M6DomainTypeAnalysisOutcome(
        status="ready",
        status_message="Found one shared structural domain type.",
        context_fingerprint="single-analysis-context-v1",
        analysis_scope=classification.analysis_scope,
        available_m6_frame_count=2,
        classification=classification,
        table_result=table_result,
    )


def _comparison_outcome() -> M6DomainTypeAnalysisOutcome:
    classification = _comparison_classification()
    table_result = build_m6_domain_type_range_comparison(
        classification,
        _comparison_range_analysis(BEFORE),
        _comparison_range_analysis(AFTER),
    )
    return M6DomainTypeAnalysisOutcome(
        status="ready",
        status_message="Found shared structural domain types in both ranges.",
        context_fingerprint="comparison-analysis-context-v1",
        analysis_scope=classification.analysis_scope,
        available_m6_frame_count=6,
        classification=classification,
        table_result=table_result,
    )


class M6DomainTypePersistenceTests(unittest.TestCase):
    def test_complete_result_round_trips_for_each_analysis_mode(self) -> None:
        for outcome in (_single_outcome(), _comparison_outcome()):
            with self.subTest(mode=outcome.analysis_scope.analysis_mode):
                original = M6DomainTypeSessionState.from_outcome(outcome)

                payload = original.to_dict()
                restored = M6DomainTypeSessionState.from_dict(payload)

                self.assertEqual(restored, original)
                self.assertEqual(
                    payload["configuration_schema_version"],
                    1,
                )
                self.assertEqual(
                    payload["reproducible_cache"]["cache_record_schema_version"],
                    1,
                )
                self.assertEqual(
                    payload["reproducible_cache"]["algorithm_version"],
                    M6_DOMAIN_TYPE_ALGORITHM_VERSION,
                )
                self.assertFalse(payload["uses_tracking"])
                self.assertFalse(
                    payload["reproducible_cache"]["uses_tracking"]
                )
                self.assertEqual(
                    restored.cache_record.outcome.table_result,
                    outcome.table_result,
                )

    def test_future_or_corrupt_cache_is_discarded_without_losing_configuration(self) -> None:
        original = M6DomainTypeSessionState.from_outcome(_single_outcome())
        for mutate in (
            lambda cache: cache.__setitem__("cache_record_schema_version", 999),
            lambda cache: cache.__setitem__("input_fingerprint", "stale"),
        ):
            with self.subTest(mutation=mutate):
                payload = original.to_dict()
                mutate(payload["reproducible_cache"])

                restored = M6DomainTypeSessionState.from_dict(payload)

                self.assertEqual(restored.analysis_scope, original.analysis_scope)
                self.assertEqual(
                    restored.classification_settings,
                    original.classification_settings,
                )
                self.assertIsNone(restored.cache_record)

    def test_cache_matches_only_identical_mode_ranges_and_m6_context(self) -> None:
        state = M6DomainTypeSessionState.from_outcome(_comparison_outcome())
        cache = state.cache_record
        self.assertIsInstance(cache, M6DomainTypeCacheRecord)
        self.assertIs(
            state.restore_outcome_for(
                analysis_scope=state.analysis_scope,
                m6_context_fingerprint=cache.m6_context_fingerprint,
                context_fingerprint=cache.context_fingerprint,
            ),
            cache.outcome,
        )
        self.assertIsNone(
            state.restore_outcome_for(
                analysis_scope=replace(
                    state.analysis_scope,
                    ranges=(
                        replace(BEFORE, end_frame=1),
                        AFTER,
                    ),
                ),
                m6_context_fingerprint=cache.m6_context_fingerprint,
                context_fingerprint=cache.context_fingerprint,
            )
        )
        self.assertIsNone(
            state.restore_outcome_for(
                analysis_scope=state.analysis_scope,
                m6_context_fingerprint="different-m6-context",
                context_fingerprint=cache.context_fingerprint,
            )
        )
        self.assertIsNone(
            state.restore_outcome_for(
                analysis_scope=_single_outcome().analysis_scope,
                m6_context_fingerprint=cache.m6_context_fingerprint,
                context_fingerprint=cache.context_fingerprint,
            )
        )
        self.assertIsNone(
            state.restore_outcome_for(
                analysis_scope=state.analysis_scope,
                m6_context_fingerprint=cache.m6_context_fingerprint,
                context_fingerprint="different-analysis-context",
            )
        )

    def test_session_round_trip_and_legacy_payload_without_domain_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"domain type persistence source")
            for outcome in (_single_outcome(), _comparison_outcome()):
                mode = outcome.analysis_scope.analysis_mode
                session_path = directory / f"{mode}.moltrack.json"
                state = M6DomainTypeSessionState.from_outcome(outcome)

                save_moltrack_session(
                    session_path,
                    _series(source_path),
                    {"m6_domain_type_analysis": state},
                )
                saved_payload = json.loads(
                    session_path.read_text(encoding="utf-8")
                )
                loaded = load_moltrack_session(session_path)

                self.assertEqual(loaded.m6_domain_type_analysis_state, state)
                self.assertFalse(
                    saved_payload["m6_domain_type_analysis"]["uses_tracking"]
                )

            saved_payload.pop("m6_domain_type_analysis")
            session_path.write_text(json.dumps(saved_payload), encoding="utf-8")
            legacy = load_moltrack_session(session_path)

        self.assertIsNone(legacy.m6_domain_type_analysis_state)

    def test_incompatible_domain_type_configuration_does_not_block_session_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"domain type persistence source")
            session_path = directory / "state.moltrack.json"
            state = M6DomainTypeSessionState.from_outcome(_single_outcome())
            save_moltrack_session(
                session_path,
                _series(source_path),
                {"m6_domain_type_analysis": state},
            )
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            payload["m6_domain_type_analysis"]["configuration_schema_version"] = 999
            session_path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_moltrack_session(session_path)

        self.assertIsNone(loaded.m6_domain_type_analysis_state)
        self.assertEqual(loaded.source_frame_indices, (0,))


if __name__ == "__main__":
    unittest.main()
