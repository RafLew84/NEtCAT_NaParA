"""Final domain pixels, including splits and refusals, agree with molecule IDs."""

import numpy as np

from stmdomains.analysis import analyze_frame
from stmdomains.analysis.segmentation import segment_domains
from stmdomains.tools.analysis_demo import lattice_patches, molecule_image
from test_frame_analysis import analysis_input


def test_calculated_regions_follow_final_memberships_and_keep_empty_background():
    points = lattice_patches()
    data = analysis_input(points, image=molecule_image(points))
    result = analyze_frame(data)
    regions = result.domain_labels
    assert regions.shape == data.frame.image.shape
    assert set(np.unique(regions)) == {0, *(m.domain_local_id for m in result.assignments.values())}
    for detection in data.annotations.detections:
        x, y = np.rint(detection.center_xy).astype(int)
        assert regions[y, x] == result.assignments[detection.detection_id].domain_local_id
    assert regions[0, 0] == regions[-1, -1] == 0
    assert not regions.flags.writeable
    repeated = analyze_frame(data)
    np.testing.assert_array_equal(regions, repeated.domain_labels)


def test_raster_splits_graph_and_removes_small_fragment_before_assigning_region_ids():
    large = [(x, y) for x in (10, 20, 30, 40, 50, 60) for y in (10, 20, 30)]
    small = [(x, y) for x in (70, 80) for y in (10, 20, 30)]
    refused_walls = [(x, y) for x in (35, 65) for y in range(0, 41, 2)]
    points = np.array(large + small + refused_walls, dtype=float)
    accepted = np.arange(len(points)) < len(large + small)
    barrier = np.zeros((45, 95), dtype=bool)
    barrier[14:17, 14:17] = True  # An interior hole, away from the molecule centres.
    ids, regions, info = segment_domains(points, np.zeros(len(points), int), accepted,
                                        np.ones((len(points), 1)), 10., barrier, lambda: None)
    assert info["graph_domains"] == 1
    assert info["final_domains"] == 2
    assert list(ids[:18]) == [1] * 9 + [2] * 9
    assert np.all(ids[18:] == 0)
    assert regions[20, 20] == 1 and regions[20, 50] == 2
    assert regions[20, 75] == regions[20, 35] == regions[15, 15] == 0
    assert set(np.unique(regions)) == {0, 1, 2}
    for (x, y), identity in zip(points.astype(int), ids):
        assert regions[y, x] == identity


def test_zero_and_unavailable_results_have_no_positive_region_pixels():
    points = lattice_patches(aligned=True)
    zero = analyze_frame(analysis_input(points, image=molecule_image(points, steps=True)))
    assert zero.status == "complete"
    assert zero.domain_labels is not None and not np.any(zero.domain_labels)
    assert analyze_frame(analysis_input()).domain_labels is None


def test_pixel_ids_are_renumbered_when_a_split_changes_domain_order():
    top = [(x, y) for x in (10, 20, 30) for y in (10, 20, 30)]
    bottom = [(x, y) for x in (10, 20, 30) for y in (50, 60, 70)]
    bridge = [(x, 40) for x in (10, 20, 30)]
    separate = [(x, y) for x in (60, 70, 80) for y in (25, 35, 45)]
    walls = [(x, y) for x in range(0, 41, 2) for y in (35, 45)]
    points = np.array(top + bottom + bridge + separate + walls, dtype=float)
    accepted = np.arange(len(points)) < 30
    ids, regions, info = segment_domains(points, np.zeros(len(points), int), accepted,
                                        np.ones((len(points), 1)), 10.,
                                        np.zeros((85, 95), bool), lambda: None)
    assert info["graph_domains"] == 2 and info["final_domains"] == 3
    assert list(ids[:30]) == [1] * 9 + [3] * 9 + [0] * 3 + [2] * 9
    assert (regions[20, 20], regions[35, 70], regions[60, 20]) == (1, 2, 3)
    assert regions[40, 20] == 0
