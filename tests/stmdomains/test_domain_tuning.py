"""Domain settings change partitions without changing the fitted class catalogue."""

from dataclasses import replace

import numpy as np
import pytest

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.segmentation import segment_domains


def partition(points, settings, *, features=None, accepted=None, shape=(100, 100)):
    points = np.asarray(points, dtype=float)
    return segment_domains(
        points, np.zeros(len(points), int),
        np.ones(len(points), bool) if accepted is None else accepted,
        np.ones((len(points), 1)) if features is None else features,
        10., np.zeros(shape, bool), lambda: None, settings=settings,
    )


def test_minimum_applies_to_graph_and_to_each_raster_fragment():
    points = [(x, y) for x in (10, 20, 30, 40) for y in (10, 20, 30)]
    walls = [(25, y) for y in range(0, 41, 2)]
    accepted = np.arange(len(points + walls)) < len(points)
    base = DomainSettings()
    _, _, info = partition(points + walls, base, accepted=accepted)
    assert info["graph_domains"] == 1 and info["final_domains"] == 0
    ids, _, info = partition(points + walls, replace(base, minimum_domain_size=6), accepted=accepted)
    assert info["graph_domains"] == 1 and info["final_domains"] == 2
    assert list(ids[:12]) == [1] * 6 + [2] * 6
    assert partition(points[:6], base)[2]["graph_domains"] == 0
    assert partition(points[:6], replace(base, minimum_domain_size=6))[2]["graph_domains"] == 1


@pytest.mark.parametrize("setting,value", [("edge_distance_factor", .9), ("raster_radius_factor", .2)])
def test_link_distance_and_mask_radius_control_spatial_connectivity(setting, value):
    points = [(x, 20) for x in (10, 20, 30, 40, 50, 60, 70, 80)]
    assert partition(points, DomainSettings())[2]["final_domains"] == 1
    assert partition(points, replace(DomainSettings(), **{setting: value}))[2]["final_domains"] == 0


def test_edge_region_and_geometry_switch_act_on_descriptor_similarity():
    points = [(x, 20) for x in (10, 20, 30, 40, 50, 60)]
    angles = np.linspace(0, .5, 6)
    features = np.column_stack((np.cos(angles), np.sin(angles)))
    base = DomainSettings(minimum_domain_size=1)
    assert partition(points, base, features=features)[2]["final_domains"] == 1
    strict_edge = replace(base, edge_max_hellinger=.05)
    assert partition(points, strict_edge, features=features)[2]["final_domains"] == 6
    strict_region = replace(base, edge_max_hellinger=.1, region_max_hellinger_diameter=.15)
    assert partition(points, strict_region, features=features)[2]["final_domains"] > 1
    disabled = replace(strict_edge, geometry_mode="off")
    assert partition(points, disabled, features=features)[2]["final_domains"] == 1


@pytest.mark.parametrize("change", [
    {"minimum_domain_size": 0}, {"minimum_domain_size": 1.5}, {"minimum_domain_size": 3001},
    {"edge_distance_factor": float("nan")}, {"edge_distance_factor": 0},
    {"raster_radius_factor": float("inf")}, {"raster_radius_factor": -1},
    {"geometry_mode": "unknown"}, {"edge_max_hellinger": .6},
    {"region_max_hellinger_diameter": 1.1}, {"edge_max_hellinger": -.1},
])
def test_invalid_settings_are_refused(change):
    with pytest.raises(ValueError):
        replace(DomainSettings(), **change)


def test_tuning_preserves_model_classes_and_restores_baseline_without_refitting(monkeypatch):
    from sklearn.decomposition import PCA
    from stmdomains.analysis import analyze_frame, recalculate_domains
    from stmdomains.tools.analysis_demo import lattice_patches, molecule_image
    from test_frame_analysis import analysis_input, memberships

    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    base = analyze_frame(data)

    def forbid_refit(*args, **kwargs):
        raise AssertionError("Domain tuning must retain the fitted catalogue")

    monkeypatch.setattr(PCA, "fit", forbid_refit)
    settings = DomainSettings(minimum_domain_size=6, edge_distance_factor=1.7,
                              geometry_mode="off", raster_radius_factor=.9)
    tuned = recalculate_domains(data, base, settings)
    assert tuned.classes == base.classes
    assert tuned.metadata["model_state"] == base.metadata["model_state"]
    assert tuned.metadata["model_id"] == base.metadata["model_id"]
    assert tuned.metadata["fit_scope"] == "current_frame"
    assert all(tuned.parameters[key] == value for key, value in settings.parameters().items())
    for key, item in base.assignments.items():
        assert tuned.assignments[key].provisional_class_id == item.provisional_class_id
        assert tuned.assignments[key].metadata == item.metadata
    assert memberships(tuned) != memberships(base)
    restored = recalculate_domains(data, tuned, DomainSettings())
    assert memberships(restored) == memberships(base)
    np.testing.assert_array_equal(restored.domain_labels, base.domain_labels)
    assert restored.parameters == base.parameters
    assert recalculate_domains(data, base, settings) is not tuned


def test_reuse_refuses_changed_input_frame_or_upstream_parameters_and_honours_cancel():
    from stmdomains.analysis import analyze_frame, recalculate_domains
    from stmdomains.core.analysis_result import AnalysisCancelled
    from test_frame_analysis import analysis_input, five_lattices

    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    base = analyze_frame(data)
    for other in (replace(data, series_id="other"),
                  replace(data, frame=replace(data.frame, source_index=99)),
                  replace(data, frame=replace(data.frame, image=data.frame.image + 1)),
                  replace(data, annotations=replace(data.annotations, detections=data.annotations.detections[:-1]))):
        with pytest.raises(ValueError, match="Analizuj klatkę"):
            recalculate_domains(other, base, DomainSettings())
    wrong_method = replace(base, parameters={**base.parameters, "class_margin": .9})
    with pytest.raises(ValueError, match="Analizuj klatkę"):
        recalculate_domains(data, wrong_method, DomainSettings())
    with pytest.raises(AnalysisCancelled):
        recalculate_domains(data, base, DomainSettings(), cancelled=lambda: True)
