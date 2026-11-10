"""Auto uses raw centres and propagates selected K through the full analysis."""

from dataclasses import replace

import numpy as np
import pytest

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.pipeline import analyze_frame
from stmdomains.analysis.series_analysis import analyze_series, FrameOutcome
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from test_class_discovery import input_at


def lattice(angle=45, center=(128, 128)):
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), np.sin(theta)], [-np.sin(theta), np.cos(theta)]])
    return np.array([(x, y) for y in range(-5, 6) for x in range(-5, 6)]) * 10 @ rotation + center


def test_local_auto_is_not_overridden_by_manual_k_and_reaches_domains():
    data = input_at(0, points=lattice())
    result = analyze_frame(data, k=8, class_count_mode="auto", auto_max_k=4,
                           acceptance=ClassAcceptanceSettings(.06, .8),
                           settings=DomainSettings(minimum_domain_size=6))
    assert result.status == "complete", result.message
    assert result.catalogue.k == len(result.classes) == result.parameters["k"] == 1
    assert result.parameters["class_count_mode"] == "auto" and result.parameters["auto_max_k"] == 4
    assert result.metadata["class_selection"]["selected_k"] == 1
    assert result.parameters["minimum_domain_size"] == 6
    assert result.parameters["class_margin"] == .06
    assert result.assigned_count > 0
    repeated = analyze_frame(data, catalogue=result.catalogue)
    assert repeated.catalogue is result.catalogue
    assert repeated.metadata["class_selection"] == result.metadata["class_selection"]


@pytest.mark.parametrize("scope", ["selected_range", "whole_series"])
def test_shared_auto_fits_only_selected_data_once_and_preserves_settings(scope):
    seen = []
    def read(index):
        seen.append(index)
        return input_at(index, points=lattice())
    plan = SeriesAnalysisPlan(start=1, end=2, whole_series=scope == "whole_series", k=8,
                              class_count_mode="auto", auto_max_k=3,
                              acceptance=ClassAcceptanceSettings(.06, .8),
                              order_settings=OrderSettings(order_quantile=.925),
                              domain_settings=DomainSettings(minimum_domain_size=6))
    events = list(analyze_series(read, frame_count=3, series_id="session-A", plan=plan))
    cat, *outcomes = events
    assert cat.k == 1 and cat.scope == scope
    assert set(seen) == set(cat.frame_indices) == ({0, 1, 2} if scope == "whole_series" else {1, 2})
    for outcome in outcomes:
        result = outcome.result
        assert result.catalogue is cat and result.parameters["k"] == 1
        assert result.parameters["class_count_mode"] == "auto"
        assert result.parameters["class_margin"] == .06
        assert result.parameters["order_quantile"] == .925
        assert result.parameters["minimum_domain_size"] == 6
        assert result.metadata["class_selection"] == cat.state["class_selection"]
    reused = list(analyze_series(read, frame_count=3, series_id="session-A", catalogue=cat,
                                 plan=replace(plan, fit_source="existing", k=1)))
    assert reused[0] is cat


@pytest.mark.parametrize("points", [[], [(10, 10)], [(80, 80), (128, 80), (80, 128), (128, 128)]])
def test_local_insufficient_auto_has_no_k_or_catalogue(points):
    result = analyze_frame(input_at(0, points=points), class_count_mode="auto")
    assert result.status != "complete" and result.catalogue is None
    assert result.parameters["k"] is None and result.parameters["class_count_mode"] == "auto"
    assert result.metadata["class_selection"]["selected_k"] is None
    assert "Auto nierozstrzygnięte" in result.message


def test_shared_insufficient_auto_returns_decision_without_computing_fake_zero_frames():
    from stmdomains.analysis.series_analysis import ClassSelectionFailure
    events = list(analyze_series(lambda i: input_at(i, points=[]), frame_count=2, series_id="session-A",
                                 plan=SeriesAnalysisPlan(end=1, class_count_mode="auto")))
    assert len(events) == 1 and isinstance(events[0], ClassSelectionFailure)
    assert events[0].decision["selected_k"] is None
    assert len(events[0].decision["fit_frames"]) == 2
    assert not any(isinstance(event, FrameOutcome) for event in events)


def test_image_controls_distinguish_two_environments_noise_and_sparse_inputs(tmp_path):
    from stmdomains.tools.auto_classes_demo import create_auto_demo
    from stmdomains.io.moltrack_import import prepare_import
    from stmdomains.core.frame_presentation import FramePresenter
    series = prepare_import(create_auto_demo(tmp_path)).series
    presenter = FramePresenter(series)
    results = [analyze_frame(presenter.analysis_input(i), class_count_mode="auto") for i in range(5)]
    assert [r.catalogue.k if r.catalogue else None for r in results] == [1, 2, None, None, None]
    assert results[1].assigned_count > 0
    assert all(r.metadata["class_selection"]["selected_k"] is None for r in results[2:])


def test_single_target_can_use_auto_from_a_separate_range_and_cancel_selection():
    from stmdomains.core.analysis_result import AnalysisCancelled
    seen = []
    def read(index):
        assert index in (1, 2, 4)
        seen.append(index)
        return input_at(index, points=lattice())
    plan = SeriesAnalysisPlan(start=4, current_frame=True, class_count_mode="auto", auto_max_k=2,
                              fit_source="selected_range", fit_start=1, fit_end=2)
    events = list(analyze_series(read, frame_count=5, series_id="session-A", plan=plan))
    cat, outcome = events
    assert cat.k == 1 and cat.frame_indices == (1, 2) and outcome.index == 4
    assert outcome.result.parameters["class_count_mode"] == "auto"
    assert set(seen) == {1, 2, 4}
    cancelled = False
    def progress(message):
        nonlocal cancelled
        if "Auto: porównanie" in message:
            cancelled = True
    with pytest.raises(AnalysisCancelled):
        list(analyze_series(read, frame_count=5, series_id="session-A", plan=plan,
                            cancelled=lambda: cancelled, progress=progress))
