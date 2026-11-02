"""Stored global translations preserve the original measurement geometry."""

import numpy as np
import pytest

from stmdomains.core.registration import parse_registration


def registration_payload(shifts):
    return {
        "reference_frame_index": 0,
        "results_by_frame": [
            {"frame_index": index, "shift_xy": shift, "method": "manual"}
            for index, shift in enumerate(shifts)
        ],
    }


def test_non_square_frame_uses_padding_from_all_global_translations():
    registration = parse_registration(
        registration_payload([(0, 0), (-1.25, .5), (2.5, -1.5)]), 3, (3, 5),
    )
    assert registration.available
    assert registration.expanded_shape == (6, 10)
    assert registration.origin(0) == (2, 2)
    assert registration.origin(1) == (.75, 2.5)
    assert registration.origin(2) == (4.5, .5)
    assert registration.field_rect(1, "raw") == (0, 0, 5, 3)
    assert registration.field_rect(1, "expanded_aligned") == (.75, 2.5, 5, 3)

    raw = np.arange(15, dtype=np.float64).reshape(3, 5)
    expanded = registration.image(raw, 0, "expanded_aligned")
    np.testing.assert_array_equal(expanded[2:5, 2:7], raw)
    assert np.isnan(expanded[:2]).all()
    assert np.isnan(expanded[:, :2]).all()
    assert registration.image(raw, 0, "raw") is raw


def test_missing_registration_keeps_raw_available_with_reason():
    registration = parse_registration(None, 1, (2, 3))
    assert not registration.available
    assert "Brak" in registration.reason
    raw = np.ones((2, 3))
    assert registration.image(raw, 0, "raw") is raw
    assert registration.field_rect(0, "raw") == (0, 0, 3, 2)
    with pytest.raises(ValueError, match="Brak"):
        registration.image(raw, 0, "expanded_aligned")


@pytest.mark.parametrize("payload", [
    {}, [], {"results_by_frame": None},
    registration_payload([(0, 0)]),
    {"results_by_frame": [{"frame_index": 0, "shift_xy": [0, 0]}] * 2},
    {"results_by_frame": [{"frame_index": 0, "shift_xy": [0, 0]},
                          {"frame_index": 5, "shift_xy": [1, 1]}]},
    {"frame_count": 3, **registration_payload([(0, 0), (1, 1)])},
    {"results_by_frame": [{"frame_index": False, "shift_xy": [0, 0]},
                          {"frame_index": 1, "shift_xy": [1, 1]}]},
    registration_payload([(0, 0), (np.nan, 1)]),
    registration_payload([(0, 0), (np.inf, 1)]),
    registration_payload([(0, 0), ("2", 1)]),
    registration_payload([(0, 0), (True, 1)]),
    registration_payload([(0, 0), (1,)]),
    {"results_by_frame": [{"frame_index": 0, "shift_xy": [0, 0]},
                          {"frame_index": 1, "shift_xy": [1, 1], "status": "failed"}]},
])
def test_incomplete_ambiguous_or_failed_registration_disables_entire_canvas(payload):
    registration = parse_registration(payload, 2, (3, 5))
    assert not registration.available
    assert registration.reason
    np.testing.assert_array_equal(registration.image(np.zeros((3, 5)), 1, "raw"), 0)
    with pytest.raises(ValueError):
        registration.origin(0)


@pytest.mark.parametrize("status, description", [
    ("low_confidence", "niska pewność"),
    ("manual_review", "wymaga oceny"),
    (None, "status nieznany"),
])
def test_quality_is_described_without_discarding_finite_translations(status, description):
    payload = registration_payload([(0, 0)])
    payload["results_by_frame"][0]["status"] = status
    registration = parse_registration(payload, 1, (2, 3))
    assert registration.available
    assert description in registration.describe(0)
    assert "jakość nieznana" in registration.describe(0)
    assert "manual" in registration.describe(0)
    assert "klatka 1" in registration.describe(0)
    assert "OK" not in registration.describe(0)


def test_mask_uses_nearest_neighbour_and_false_padding_from_saved_source():
    registration = parse_registration(registration_payload([(0, 0), (.25, .25)]), 2, (3, 5))
    source = np.zeros((3, 5), dtype=bool)
    source[1, 2] = True
    aligned = registration.transform_mask(source, 1, "raw", "expanded_aligned")
    expected = np.zeros((4, 6), dtype=bool)
    expected[1, 2] = True
    np.testing.assert_array_equal(aligned, expected)
    assert registration.transform_mask(source, 1, "raw", "raw") is source
    restored = registration.transform_mask(aligned, 1, "expanded_aligned", "raw")
    np.testing.assert_array_equal(restored, source)
    assert source.sum() == 1
    with pytest.raises(ValueError, match="Wymiary"):
        registration.transform_mask(np.ones((3, 5), dtype=bool), 1, "expanded_aligned", "raw")


def test_fractional_linear_image_keeps_padding_distinct_and_never_resamples_a_preview():
    registration = parse_registration(registration_payload([(0, 0), (.5, .25)]), 2, (3, 5))
    # Literal plane: intensity rises by 2 per column and 10 per row.
    raw = np.array([[0, 2, 4, 6, 8], [10, 12, 14, 16, 18], [20, 22, 24, 26, 28]], dtype=float)
    raw.setflags(write=False)
    expected = np.array([
        [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        [np.nan, 8.5, 10.5, 12.5, 14.5, np.nan],
        [np.nan, 18.5, 20.5, 22.5, 24.5, np.nan],
        [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
    ])
    for _ in range(4):
        np.testing.assert_array_equal(registration.image(raw, 1, "expanded_aligned"), expected)
        assert registration.image(raw, 1, "raw") is raw
    assert registration.field_rect(1, "expanded_aligned") == (.5, .25, 5, 3)
    assert not raw.flags.writeable


def test_quality_score_and_unknown_reference_do_not_invent_missing_metadata():
    payload = registration_payload([(0, 0)])
    del payload["reference_frame_index"]
    record = payload["results_by_frame"][0]
    record.update(status="ok", quality_score=.125, method=None)
    registration = parse_registration(payload, 1, (2, 3))
    assert "OK" in registration.describe(0)
    assert "jakość 0.125" in registration.describe(0)
    assert "metoda nieznana" in registration.describe(0)
    assert "referencja: nieznana" in registration.describe(0)
