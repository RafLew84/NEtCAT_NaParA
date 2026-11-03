"""Acceptance changes decisions without rediscovering the descriptor classes."""

import numpy as np
import pytest
from dataclasses import replace

from stmdomains.analysis import analyze_frame, recalculate_class_acceptance
from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.tools.analysis_demo import lattice_patches, molecule_image
from test_frame_analysis import analysis_input


def test_stricter_acceptance_changes_domains_but_keeps_catalogue_and_restores_baseline():
    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    base = analyze_frame(data)
    strict = recalculate_class_acceptance(data, base, ClassAcceptanceSettings(class_radius_multiplier=.05))
    assert strict.assigned_count < base.assigned_count
    assert strict.catalogue is base.catalogue
    assert strict.metadata["model_id"] == base.metadata["model_id"]
    assert strict.classes == base.classes
    assert strict.parameters["class_radius_multiplier"] == .05
    for identity, member in base.assignments.items():
        updated = strict.assignments[identity]
        assert updated.provisional_class_id == member.provisional_class_id
        assert updated.metadata["order_supported"] == member.metadata["order_supported"]
    restored = recalculate_class_acceptance(data, strict, ClassAcceptanceSettings())
    assert restored.assignments == base.assignments
    assert restored.parameters == base.parameters
    np.testing.assert_array_equal(restored.domain_labels, base.domain_labels)


def test_molecule_details_distinguish_radius_refusal_from_order_and_final_domain():
    from stmdomains.ui.assignment_details import assignment_details

    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    base = analyze_frame(data)
    strict = recalculate_class_acceptance(data, base, ClassAcceptanceSettings(class_radius_multiplier=.05))
    member = next(m for m in strict.assignments.values()
                  if m.metadata.get("order_supported") and not m.metadata.get("class_radius_passed"))
    text = assignment_details(strict, member.detection_id)
    assert "Klasa wstępna:" in text
    assert "Akceptacja klasy: odrzucona" in text
    assert "poza promieniem klasy" in text
    assert "Porządek lokalny: potwierdzony" in text
    assert "Domena końcowa: brak" in text
    assert "nie jest prawdopodobieństwem" in text


def test_margin_and_radius_have_independent_effects_on_a_known_two_class_example():
    from stmdomains.analysis.clustering import apply_classes, fit_model

    # Symmetric training pairs have centres -1.5 / 1.5 and radius 0.5.
    state = fit_model(np.array([[-2.], [-1.], [1.], [2.]]), 2, lambda: None)
    samples = np.array([[.05], [1.4], [3.]])
    valid = np.ones(3, bool)
    strict = apply_classes(samples, valid, state, lambda: None,
                           acceptance=ClassAcceptanceSettings(.075, 4.))
    loose = apply_classes(samples, valid, state, lambda: None,
                          acceptance=ClassAcceptanceSettings(.06, 4.))
    assert list(strict[1]) == [False, True, True]
    assert list(loose[1]) == [True, True, True]
    np.testing.assert_array_equal(strict[0], loose[0])
    radial = apply_classes(samples, valid, state, lambda: None,
                           acceptance=ClassAcceptanceSettings(.06, 1.1))
    assert list(radial[1]) == [False, True, False]
    assert not radial[2]["class_radius_passed"][2]
    assert radial[2]["class_margin_passed"][2]


def test_one_class_uses_radius_and_valid_descriptor_without_a_competing_class():
    from stmdomains.analysis.clustering import apply_classes, fit_model

    state = fit_model(np.array([[-1.], [1.]]), 1, lambda: None)
    samples = np.array([[0.], [.5], [2.], [.5]])
    valid = np.array([True, True, True, False])
    narrow = apply_classes(samples, valid, state, lambda: None,
                           acceptance=ClassAcceptanceSettings(1., 1.1))
    broad = apply_classes(samples, valid, state, lambda: None,
                          acceptance=ClassAcceptanceSettings(1., 2.1))
    assert list(narrow[1]) == [True, True, False, False]
    assert list(broad[1]) == [True, True, True, False]
    assert narrow[2]["class_margin_passed"].all()


@pytest.mark.parametrize("values", [
    {"class_margin": -.01}, {"class_margin": 1.01}, {"class_margin": float("nan")},
    {"class_radius_multiplier": 0}, {"class_radius_multiplier": 10.01},
    {"class_radius_multiplier": float("inf")},
])
def test_invalid_acceptance_settings_are_refused(values):
    with pytest.raises(ValueError):
        ClassAcceptanceSettings(**values)


def test_acceptance_requires_unchanged_inputs_and_existing_catalogue_and_honours_cancel():
    from stmdomains.core.analysis_result import AnalysisCancelled

    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    base = analyze_frame(data)
    for other in (replace(data, series_id="other"),
                  replace(data, frame=replace(data.frame, source_index=5)),
                  replace(data, frame=replace(data.frame, image=data.frame.image + .1)),
                  replace(data, annotations=replace(data.annotations, detections=data.annotations.detections[:-1]))):
        with pytest.raises(ValueError, match="Analizuj klatkę"):
            recalculate_class_acceptance(other, base, ClassAcceptanceSettings())
    with pytest.raises(ValueError, match="Najpierw"):
        recalculate_class_acceptance(data, replace(base, catalogue=None), ClassAcceptanceSettings())
    cancelled = False

    def cancel_at_progress(text):
        nonlocal cancelled
        cancelled = True

    with pytest.raises(AnalysisCancelled):
        recalculate_class_acceptance(data, base, ClassAcceptanceSettings(),
                                      cancelled=lambda: cancelled, progress=cancel_at_progress)
