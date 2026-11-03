"""One analysis request applies the full configuration to local or shared classes."""

from dataclasses import replace

import numpy as np
import pytest

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.pipeline import analyze_frame
from stmdomains.analysis.series_analysis import FrameOutcome, analyze_series
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from test_class_discovery import input_at


def test_current_frame_request_fits_locally_and_reuses_all_settings():
    plan = SeriesAnalysisPlan(start=1, current_frame=True, k=4,
                              acceptance=ClassAcceptanceSettings(.06, .8),
                              order_settings=OrderSettings(order_quantile=.925),
                              domain_settings=DomainSettings(minimum_domain_size=6))
    events = list(analyze_series(input_at, frame_count=3, series_id="session-A", plan=plan))
    catalogue, outcome = events
    assert catalogue.scope == "current_frame" and catalogue.frame_indices == (1,)
    assert outcome.index == 1 and outcome.result.catalogue is catalogue
    result = outcome.result
    single = analyze_frame(input_at(1), k=4, acceptance=plan.acceptance,
                           order_settings=plan.order_settings, settings=plan.domain_settings)
    assert result.assignments == single.assignments
    np.testing.assert_array_equal(result.domain_labels, single.domain_labels)
    reused = list(analyze_series(input_at, frame_count=3, series_id="session-A", catalogue=catalogue,
                                 plan=replace(plan, fit_source="existing")))
    assert reused[0] is catalogue and reused[1].result.assignments == result.assignments


@pytest.mark.parametrize("points,status", [([], "no_annotations"), ([(10, 10)], "insufficient_data")])
def test_unavailable_local_data_still_records_all_requested_parameters(points, status):
    plan = SeriesAnalysisPlan(current_frame=True, acceptance=ClassAcceptanceSettings(.06, .8),
                              order_settings=OrderSettings(order_quantile=.925))
    events = list(analyze_series(lambda i: input_at(i, points=points), frame_count=1,
                                 series_id="session-A", plan=plan))
    assert len(events) == 1 and isinstance(events[0], FrameOutcome)
    result = events[0].result
    assert result.status == status and result.catalogue is None
    assert result.parameters["class_margin"] == .06
    assert result.parameters["class_radius_multiplier"] == .8
    assert result.parameters["order_quantile"] == .925


def test_local_catalogue_cannot_be_applied_to_changed_input_or_multiple_frames():
    catalogue = analyze_frame(input_at(0), k=4).catalogue
    for plan in (SeriesAnalysisPlan(end=1, k=4, fit_source="existing"),
                 SeriesAnalysisPlan(start=1, current_frame=True, k=4, fit_source="existing")):
        with pytest.raises(ValueError, match="katalog"):
            list(analyze_series(input_at, frame_count=2, series_id="session-A", plan=plan, catalogue=catalogue))
    changed = input_at(0, points=[(12, 12)])
    with pytest.raises(ValueError, match="Lokalny katalog"):
        list(analyze_series(lambda _: changed, frame_count=2, series_id="session-A", catalogue=catalogue,
                            plan=SeriesAnalysisPlan(current_frame=True, k=4, fit_source="existing")))

