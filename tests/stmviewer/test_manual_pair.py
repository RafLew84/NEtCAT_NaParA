"""Manual pair trials preserve source pixels and record operator choices."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.io import open_stp


def pair_frames():
    template = open_stp(Path(__file__).parent / 'fixtures' / 'asymmetric.stp')
    reference = replace(template, data=np.arange(60, dtype=np.float64).reshape(6, 10),
                        source_frame_index=0)
    moving = replace(reference, data=reference.data.copy(), source_frame_index=1)
    return reference, moving


def test_manual_steps_from_zero_create_an_unassessed_pair_trial():
    from stmviewer.manual_pair import ManualPairDraft

    reference, moving = pair_frames()
    draft = ManualPairDraft(reference, moving)
    assert draft.shift_xy == (0, 0)
    draft.nudge(1, 0)
    draft.nudge(1, 0)
    draft.nudge(0, -1)
    trial = draft.apply()

    assert trial.shift_xy == (2, -1)
    assert trial.method == 'manual'
    assert trial.label == 'Ręczne'
    assert trial.status == 'manual' and trial.quality_score is None
    assert trial.reference.source_frame_index == 0
    assert trial.moving.source_frame_index == 1
    assert trial.manual.start_xy == (0, 0)
    assert trial.manual.correction_xy == (2, -1)
    assert trial.manual.source_label is None
    assert trial.manual.settings_version == 1


def automatic_trial(reference, moving, shift=(2.4, -1.25)):
    from stmviewer.pair_comparison import PairTrial
    from stmviewer.registration import FrameOrigin

    return PairTrial(FrameOrigin(reference.source, reference.source_frame_index),
                     FrameOrigin(moving.source, moving.source_frame_index),
                     'phase_correlation', 'Phase', 'normalization=phase', 'CPU',
                     shift, 'ok', 0.9)


def test_copy_keeps_fractional_start_and_reset_without_inheriting_confidence():
    from stmviewer.manual_pair import ManualPairDraft

    reference, moving = pair_frames()
    automatic = automatic_trial(reference, moving)
    draft = ManualPairDraft(reference, moving, start=automatic)
    draft.nudge(1, 0)
    draft.nudge(0, -1)
    copied = draft.apply()
    assert copied.shift_xy == (3.4, -2.25)
    assert copied.manual.start_xy == (2.4, -1.25)
    assert copied.manual.correction_xy == (1, -1)
    assert 'Phase' in copied.manual.source_label
    assert 'normalization=phase' in copied.manual.source_label
    assert copied.quality_score is None and copied.status == 'manual'
    draft.reset()
    assert draft.shift_xy == (2.4, -1.25)
    assert draft.apply().manual.correction_xy == (0, 0)
    assert automatic.shift_xy == (2.4, -1.25) and automatic.quality_score == 0.9
    assert copied.shift_xy == (3.4, -2.25)  # Reset cannot mutate a saved snapshot.


def test_start_from_another_pair_or_nonfinite_xy_is_rejected():
    import pytest
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.registration import FrameOrigin

    reference, moving = pair_frames()
    automatic = automatic_trial(reference, moving)
    unrelated = FrameOrigin(reference.source, 10)
    for invalid in (replace(automatic, reference=unrelated), replace(automatic, moving=unrelated),
                    replace(automatic, shift_xy=(np.nan, 0)),
                    replace(automatic, shift_xy=(0, np.inf)),
                    replace(automatic, shift_xy=(1,))):
        with pytest.raises(ValueError):
            ManualPairDraft(reference, moving, start=invalid)


def test_only_one_integer_source_pixel_in_one_axis_is_a_manual_step():
    import pytest
    from stmviewer.manual_pair import ManualPairDraft

    draft = ManualPairDraft(*pair_frames())
    draft.nudge(-1, 0)
    draft.nudge(0, 1)
    for step in ((0, 0), (1, 1), (2, 0), (0, -2), (0.5, 0), (True, 0), (1.0, 0)):
        with pytest.raises(ValueError):
            draft.nudge(*step)
        assert draft.shift_xy == (-1, 1)


def test_draft_and_saved_trial_describe_start_correction_and_source():
    from stmviewer.manual_pair import ManualPairDraft

    reference, moving = pair_frames()
    draft = ManualPairDraft(reference, moving, start=automatic_trial(reference, moving))
    draft.nudge(-1, 0)
    draft.nudge(0, 1)
    assert draft.start_xy == (2.4, -1.25)
    assert draft.correction_xy == (-1, 1)
    assert draft.shift_xy == (1.4, -0.25)
    trial = draft.apply()
    assert 'v1' in trial.settings_text
    assert 'Początek XY=(2.4, -1.25) px' in trial.settings_text
    assert 'Korekta XY=(-1, +1) px' in trial.settings_text
    assert 'Phase' in trial.settings_text
    assert 'normalization=phase' in trial.settings_text


def test_correcting_a_manual_trial_keeps_bounded_provenance_and_immutable_snapshots():
    from dataclasses import FrozenInstanceError, asdict
    from stmviewer.pair_comparison import PairTrial
    import pytest
    from stmviewer.manual_pair import ManualPairDraft

    reference, moving = pair_frames()
    trial = automatic_trial(reference, moving)
    for _ in range(20):
        draft = ManualPairDraft(reference, moving, start=trial)
        draft.nudge(1, 0)
        trial = draft.apply()
    assert trial.shift_xy == (22.4, -1.25)
    assert trial.manual.start_xy == (21.4, -1.25)
    assert trial.manual.correction_xy == (1, 0)
    assert 'Ręczne v1' in trial.manual.source_label
    assert len(trial.settings_text) < 400
    assert not any(isinstance(value, PairTrial) for value in asdict(trial.manual).values())
    with pytest.raises(FrozenInstanceError):
        trial.shift_xy = (0, 0)
    with pytest.raises(FrozenInstanceError):
        trial.manual.start_xy = (0, 0)
    draft.nudge(-1, 0)
    assert trial.shift_xy == (22.4, -1.25)


def test_return_to_the_same_xy_restores_the_original_raster_even_after_no_overlap():
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.pair_comparison import PairImages

    reference, moving = pair_frames()
    reference_before, moving_before = reference.data.copy(), moving.data.copy()
    images = PairImages(reference, moving)
    draft = ManualPairDraft(reference, moving,
                            start=automatic_trial(reference, moving, (-0.5, 0.5)))
    original = images.render(draft.shift_xy, layer='moving')
    assert original.rgba[1, 0, 0] == 23  # Bilinear sample 5.5 in the original range 0..59.
    for _ in range(20):
        draft.nudge(1, 0)
    absent = images.render(draft.shift_xy)
    assert absent.overlap_pixels == 0
    assert draft.apply().shift_xy == (19.5, 0.5)  # Such diagnostic trials are allowed.
    for _ in range(20):
        draft.nudge(-1, 0)
    assert draft.shift_xy == (-0.5, 0.5)
    np.testing.assert_array_equal(images.render(draft.shift_xy, layer='moving').rgba, original.rgba)
    np.testing.assert_array_equal(reference.data, reference_before)
    np.testing.assert_array_equal(moving.data, moving_before)
    assert images.contrast == (0, 59)
