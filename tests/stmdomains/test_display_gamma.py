"""Gamma uses original measurement samples and never alters annotations."""

from pathlib import Path

import numpy as np
import pytest

from stmdomains.core.display import render_image
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.series import Series


def test_gamma_brightens_normalized_measurements_without_touching_source():
    samples = np.array([[0., 0., 0., .25, .5, .75, 1., 1., 1., np.nan, np.inf]])
    before = samples.copy()
    rendered = render_image(samples, gamma=2)
    assert rendered.rgba[0, :, 0].tolist() == [0, 0, 0, 128, 180, 221, 255, 255, 255, 0, 0]
    assert rendered.rgba[0, :, 3].tolist() == [255] * 9 + [0, 0]
    np.testing.assert_array_equal(samples, before)


@pytest.mark.parametrize("gamma", [0, -1, np.nan, np.inf])
def test_gamma_must_be_finite_and_positive_even_without_valid_samples(gamma):
    with pytest.raises(ValueError, match="[Gg]amma"):
        render_image(np.array([[np.nan]]), gamma=gamma)


def make_presenter():
    images = np.array([[[0., 0., .25, 1., 1.], [0., 0., .25, 1., 1.]]] * 2)
    payload = {
        "registration": {"results_by_frame": [
            {"frame_index": 0, "shift_xy": [0, 0]},
            {"frame_index": 1, "shift_xy": [-.5, .5]},
        ]},
        "molecular_detections": {"frame_count": 2, "detections": [
            {"frame_index": 0, "detection_id": "molecule", "bbox_xyxy": [2, 0, 3, 1]},
        ]},
        "molecular_segmentations": {"frame_count": 2, "segmentations": [
            {"frame_index": 0, "segmentation_id": "mask", "prompt_detection_ids": ["molecule"],
             "mask": {"encoding": "rle", "shape": [2, 5], "counts": [2, 1, 7]}},
        ]},
    }
    series = Series(Path("input.json"), Path("input.mpp"), (0, 1), 0, images, raw_payload=payload)
    return FramePresenter(series)


def test_presenter_keeps_gamma_and_contrast_common_to_both_views_without_changing_masks():
    presenter = make_presenter()
    before = presenter.series.raw_frames.copy()
    normal = presenter.present(0)
    raw = presenter.present(0, gamma=2)
    aligned = presenter.present(0, "expanded_aligned", gamma=2)
    assert raw.gamma == aligned.gamma == 2
    assert raw.rendered.rgba[0, 2].tolist() == [128, 128, 128, 255]
    assert aligned.rendered.rgba[0, 3].tolist() == [128, 128, 128, 255]
    assert aligned.rendered.rgba[0, 0].tolist() == [0, 0, 0, 0]
    np.testing.assert_array_equal(normal.masks.rgba, raw.masks.rgba)
    assert raw.annotations.detections[0].bbox_xyxy == (2, 0, 3, 1)
    np.testing.assert_array_equal(presenter.present(0).rendered.rgba, normal.rendered.rgba)
    np.testing.assert_array_equal(presenter.series.raw_frames, before)


def test_prepared_original_contrast_can_be_reused_without_reestimating_the_view():
    from stmdomains.core.display import contrast_limits

    original = np.array([[0., 0., .25, 1., 1., np.nan]])
    limits = contrast_limits(original)
    assert limits == (0., 1.)
    view = render_image(np.array([[.25, np.nan]]), limits=limits, gamma=2)
    assert view.rgba[0].tolist() == [[128, 128, 128, 255], [0, 0, 0, 0]]


@pytest.mark.parametrize("gamma, grey", [(0.5, 64), (1, 128), (2, 180)])
def test_constant_samples_use_middle_intensity_before_gamma(gamma, grey):
    with np.errstate(all="raise"):
        image = render_image(np.array([[7., 7., np.nan]]), gamma=gamma)
    assert image.rgba[0].tolist() == [[grey, grey, grey, 255]] * 2 + [[0, 0, 0, 0]]


def test_no_finite_samples_remain_explicitly_absent_for_every_gamma():
    for gamma in (0.2, 1, 5):
        with np.errstate(all="raise"):
            image = render_image(np.array([[np.nan, np.inf, -np.inf]]), gamma=gamma)
        assert not image.has_data
        assert not image.rgba.any()


def test_scrubbing_gamma_keeps_image_cache_bounded_and_reproduces_original_preview():
    presenter = make_presenter()
    original = presenter.present(0).rendered.rgba.copy()
    for gamma in np.linspace(0.2, 5, 49):
        for mode in ("raw", "expanded_aligned"):
            presenter.present(0, mode, float(gamma))
            # At most three images, each no larger than the known 6×3 canvas.
            assert presenter.image_cache_bytes <= 3 * 6 * 3 * 4
    np.testing.assert_array_equal(presenter.present(0).rendered.rgba, original)
