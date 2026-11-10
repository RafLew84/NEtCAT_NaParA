"""Order controls change calibrated decisions while preserving fitted classes."""

import numpy as np
import pytest

from stmdomains.analysis.order import evaluate_order
from stmdomains.analysis.order_settings import OrderSettings


def test_quantile_recalibrates_thresholds_without_changing_the_observed_score():
    points = np.array([(x, y) for y in range(9) for x in range(9)], dtype=float)
    base, calibration = evaluate_order(points, 1., lambda: None, lambda text: None)
    loose, updated = evaluate_order(points, 1., lambda: None, lambda text: None,
                                    settings=OrderSettings(order_quantile=.925))
    np.testing.assert_array_equal(loose["score"], base["score"])
    assert np.all(loose["threshold"] <= base["threshold"])
    assert np.any(loose["threshold"] < base["threshold"])
    assert updated["quantile"] == .925
    assert updated["identifier"] != calibration["identifier"]
    assert updated["seed"] == calibration["seed"]
    assert all(row["quantile"] == .925 for row in updated["calibration"])


def test_smaller_window_rebuilds_calibration_keeps_catalogue_and_restores_domains():
    from stmdomains.analysis import analyze_frame, recalculate_order
    from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
    from stmdomains.analysis.domain_settings import DomainSettings
    from stmdomains.tools.analysis_demo import lattice_patches, molecule_image
    from test_frame_analysis import analysis_input

    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    base = analyze_frame(data, settings=DomainSettings(minimum_domain_size=6),
                         acceptance=ClassAcceptanceSettings(class_margin=.06))
    settings = OrderSettings(order_radius_factor=2., order_sigma_factor=1.)
    progress = []
    changed = recalculate_order(data, base, settings, progress=progress.append)
    assert changed.catalogue is base.catalogue
    assert changed.classes == base.classes
    assert changed.parameters["minimum_domain_size"] == 6
    assert changed.parameters["class_margin"] == .06
    assert changed.parameters["order_radius_factor"] == 2.
    assert changed.metadata["order_calibration"]["identifier"] != base.metadata["order_calibration"]["identifier"]
    assert any("Kalibracja" in text for text in progress)
    assert changed.metadata["order_evaluation"]["input_sha256"] == base.metadata["input_sha256"]
    assert changed.assigned_count < base.assigned_count
    assert any(m.rejection_reason == "insufficient_local_support" for m in changed.assignments.values())
    for identity, member in base.assignments.items():
        updated = changed.assignments[identity]
        assert updated.provisional_class_id == member.provisional_class_id
        assert updated.metadata["class_reliable"] == member.metadata["class_reliable"]
    restored = recalculate_order(data, changed, OrderSettings())
    assert restored.assignments == base.assignments
    assert restored.parameters == base.parameters
    np.testing.assert_array_equal(restored.domain_labels, base.domain_labels)


def test_explicit_discovery_uses_the_new_order_gate_to_select_training_samples():
    from stmdomains.analysis import discover_classes
    from stmdomains.analysis.class_settings import ClassFitSettings
    from test_class_discovery import input_at

    fit = ClassFitSettings(k=1, scope="selected_range", start=0, end=1)
    base = discover_classes(input_at, frame_count=3, current_index=2, settings=fit)
    stricter = OrderSettings(order_minimum_local_count=20)
    changed = discover_classes(input_at, frame_count=3, current_index=2, settings=fit,
                                order_settings=stricter)
    assert changed.catalogue.identifier != base.catalogue.identifier
    assert changed.catalogue.state["fit_count"] < base.catalogue.state["fit_count"]
    assert changed.parameters["order_minimum_local_count"] == 20
    for row in changed.catalogue.provenance["frames"]:
        assert row["order_settings"] == stricter.parameters()
        assert row["order_seed"] == 20261102
        assert row["order_calibration_id"] == changed.metadata["order_calibration"]["identifier"]


def test_molecule_details_show_score_threshold_and_insufficient_support_with_used_parameters():
    from stmdomains.analysis import analyze_frame, recalculate_order
    from stmdomains.tools.analysis_demo import lattice_patches, molecule_image
    from stmdomains.ui.assignment_details import assignment_details
    from test_frame_analysis import analysis_input

    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    base = analyze_frame(data)
    result = recalculate_order(data, base, OrderSettings(order_radius_factor=2., order_sigma_factor=1.))
    member = next(m for m in result.assignments.values() if m.rejection_reason == "insufficient_local_support")
    text = assignment_details(result, member.detection_id)
    for label in ("Punkty lokalne:", "Punkty efektywne:", "Koherencja:", "próg kontroli", "kwantyl 0.95",
                  "promień 2 × d", "sigma 1 × d", "nie potwierdza sieci 2D"):
        assert label in text


def test_regular_random_and_rows_remain_distinct_controls_of_periodicity_not_2d_lattices():
    rng = np.random.default_rng(517)
    regular = np.array([(x, y) for y in range(9) for x in range(9)], dtype=float)
    random = rng.uniform(0, 12., (180, 2))
    rows = np.column_stack((rng.uniform(0, 8., 81), np.repeat(np.arange(9), 9)))
    outcomes = [evaluate_order(p, 1., lambda: None, lambda text: None)[0] for p in (regular, random, rows)]
    assert outcomes[0]["supported"].mean() > .75
    assert outcomes[1]["supported"].mean() < .2
    assert outcomes[2]["supported"].mean() > .5  # A positive gate does not establish a 2D lattice.


def test_sigma_support_minima_and_scale_are_applied_to_both_observation_and_calibration():
    points = np.array([(x, y) for y in range(9) for x in range(9)], dtype=float)
    base, baseline = evaluate_order(points, 1., lambda: None, lambda text: None)
    for settings in (OrderSettings(order_sigma_factor=1.),
                     OrderSettings(order_minimum_local_count=20),
                     OrderSettings(order_minimum_effective_count=16.)):
        changed, calibration = evaluate_order(points, 1., lambda: None, lambda text: None, settings=settings)
        assert calibration["identifier"] != baseline["identifier"]
        assert calibration["settings"] == settings.parameters()
        if settings.order_sigma_factor == 1.:
            assert np.any(changed["effective_n"] < base["effective_n"])
        else:
            assert changed["sufficient"].sum() < base["sufficient"].sum()
    smaller = OrderSettings(order_radius_factor=2., order_sigma_factor=1.)
    original, calibration = evaluate_order(points, 1., lambda: None, lambda text: None, settings=smaller)
    scaled, repeated = evaluate_order(points * 7., 7., lambda: None, lambda text: None, settings=smaller)
    assert repeated == calibration
    np.testing.assert_array_equal(scaled["supported"], original["supported"])
    np.testing.assert_allclose(scaled["score"], original["score"], atol=1e-12)


@pytest.mark.parametrize("settings", [
    {"order_quantile": 1.}, {"order_quantile": float("nan")},
    {"order_minimum_local_count": 2}, {"order_minimum_local_count": 10.5},
    {"order_minimum_effective_count": float("inf")}, {"order_minimum_effective_count": 0},
    {"order_radius_factor": 0}, {"order_sigma_factor": -1.},
])
def test_invalid_order_settings_are_refused(settings):
    with pytest.raises(ValueError):
        OrderSettings(**settings)


def test_tuning_rejects_changed_source_and_cancelled_calibration():
    from dataclasses import replace
    from stmdomains.analysis import analyze_frame, recalculate_order
    from stmdomains.core.analysis_result import AnalysisCancelled
    from test_frame_analysis import analysis_input, five_lattices

    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    base = analyze_frame(data)
    for changed in (replace(data, series_id="other"),
                    replace(data, frame=replace(data.frame, image=data.frame.image + .1))):
        with pytest.raises(ValueError, match="Analizuj klatkę"):
            recalculate_order(changed, base, OrderSettings())
    cancelled = False

    def progress(text):
        nonlocal cancelled
        if "Kalibracja" in text:
            cancelled = True

    with pytest.raises(AnalysisCancelled):
        recalculate_order(data, base, OrderSettings(), cancelled=lambda: cancelled, progress=progress)
