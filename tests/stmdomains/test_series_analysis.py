"""A shared fit feeds every selected frame with the same domain settings."""

import numpy as np
import pytest
from dataclasses import replace

from stmdomains.analysis import analyze_frame
from stmdomains.analysis.domain_settings import DomainSettings
from test_class_discovery import input_at


def test_series_matches_individual_analysis_with_one_shared_catalogue():
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan

    read = []

    def read_frame(index):
        read.append(index)
        return input_at(index)

    settings = DomainSettings(minimum_domain_size=6, edge_distance_factor=1.8)
    plan = SeriesAnalysisPlan(start=2, end=3, k=4, fit_source="selected_range",
                              fit_start=0, fit_end=1, domain_settings=settings)
    events = list(analyze_series(read_frame, frame_count=5, series_id="session-A", plan=plan))
    catalogue, *frames = events
    assert catalogue.frame_indices == (0, 1) and catalogue.k == 4
    assert [item.index for item in frames] == [2, 3] and set(read) == {0, 1, 2, 3}
    for item in frames:
        result = item.result
        assert not item.error and result.catalogue is catalogue
        assert result.parameters["minimum_domain_size"] == 6
        single = analyze_frame(input_at(item.index), catalogue=catalogue, settings=settings)
        assert result.assignments == single.assignments
        np.testing.assert_array_equal(result.domain_labels, single.domain_labels)


def test_frame_results_share_immutable_catalogue_storage():
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.core.immutable import freeze_metadata
    from types import MappingProxyType

    source = {"values": [1, 2]}
    snapshot = freeze_metadata(MappingProxyType(source))
    source["values"].append(3)
    assert snapshot["values"] == (1, 2)
    catalogue, *outcomes = analyze_series(input_at, frame_count=2, series_id="session-A",
                                          plan=SeriesAnalysisPlan(end=1, k=4))
    for outcome in outcomes:
        # The shared PCA/provenance can be large: keep one immutable copy per fit.
        assert outcome.result.metadata["model_state"] is catalogue.state
        assert outcome.result.metadata["fit_frames"][0] is catalogue.provenance["frames"][0]


def test_reuse_skips_fit_and_reports_empty_and_failed_frames_without_stopping(monkeypatch):
    from sklearn.decomposition import PCA
    from stmdomains.analysis.discovery import fit_shared_catalogue
    from stmdomains.analysis.class_settings import ClassFitSettings
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan

    catalogue = fit_shared_catalogue(input_at, frame_count=4, settings=ClassFitSettings(scope="selected_range"))

    def forbid_fit(*args, **kwargs):
        raise AssertionError("Existing shared catalogue must not be refitted")

    monkeypatch.setattr(PCA, "fit", forbid_fit)

    def read(index):
        if index == 1:
            raise OSError("cannot read frame")
        return input_at(index, points=[] if index == 2 else None)

    events = list(analyze_series(read, frame_count=4, series_id="session-A", catalogue=catalogue,
                                plan=SeriesAnalysisPlan(whole_series=True, fit_source="existing")))
    assert events[0] is catalogue
    assert [e.index for e in events[1:]] == [0, 1, 2, 3]
    assert events[1].result.status == events[4].result.status == "complete"
    assert events[2].result is None and "cannot read frame" in events[2].error
    assert events[3].result.status == "no_annotations"
    assert events[3].result.catalogue is catalogue


def test_cancel_during_fit_or_after_a_frame_stops_further_reads():
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.core.analysis_result import AnalysisCancelled

    cancelled = False

    def report(text):
        nonlocal cancelled
        if "Kalibracja" in text:
            cancelled = True

    plan = SeriesAnalysisPlan(end=2, fit_source="selected_range", fit_end=0)
    stream = analyze_series(input_at, frame_count=3, series_id="session-A", plan=plan,
                            cancelled=lambda: cancelled, progress=report)
    with pytest.raises(AnalysisCancelled):
        next(stream)
    cancelled = False
    reads = []

    def read(index):
        reads.append(index)
        return input_at(index)

    stream = analyze_series(read, frame_count=3, series_id="session-A", plan=plan,
                            cancelled=lambda: cancelled)
    next(stream)
    assert next(stream).index == 0
    before = list(reads)
    cancelled = True
    with pytest.raises(AnalysisCancelled):
        next(stream)
    assert reads == before


def test_invalid_scope_or_catalogue_never_reads_measurements():
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan

    def forbid_read(index):
        raise AssertionError("Invalid request must fail before image reads")

    for plan in (SeriesAnalysisPlan(start=2, end=1), SeriesAnalysisPlan(end=4),
                 SeriesAnalysisPlan(fit_source="selected_range", fit_end=4),
                 SeriesAnalysisPlan(fit_source="existing")):
        with pytest.raises(ValueError):
            list(analyze_series(forbid_read, frame_count=3, series_id="session-A", plan=plan))
    local = analyze_frame(input_at(0)).catalogue
    for catalogue in (local, replace(local, scope="selected_range", series_id="foreign"),
                      replace(local, scope="selected_range", parameters={})):
        with pytest.raises(ValueError):
            list(analyze_series(forbid_read, frame_count=3, series_id="session-A", catalogue=catalogue,
                                plan=SeriesAnalysisPlan(fit_source="existing")))
