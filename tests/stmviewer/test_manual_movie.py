"""Complete registration -> manual pair correction -> rebuilt movie."""
from pathlib import Path

from stmviewer.manual_pair import ManualPairDraft
from stmviewer.mpp import open_mpp_series
from stmviewer.registration import register_series


def cpu_result():
    frames = open_mpp_series(Path(__file__).parent / 'fixtures/registration/cpu.mpp',
                             check_cancelled=lambda: None)
    return register_series(frames)


def corrected_trial(result, index, dx, dy):
    from stmviewer.manual_movie import movie_pair_trial

    draft = ManualPairDraft(result.frames[index - 1].original,
                            result.frames[index].original,
                            movie_pair_trial(result, index))
    draft.nudge(dx, dy)
    return draft.apply()


def test_correcting_a_pair_replaces_its_shift_and_moves_only_its_suffix():
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial

    base = cpu_result()
    trial = corrected_trial(base, 1, 1, 0)
    changed = apply_movie_correction(base, trial)
    assert [frame.shift_xy for frame in base.frames] == [(0, 0), (2, -1), (-1, 1)]
    assert [frame.shift_xy for frame in changed.frames] == [(0, 0), (3, -1), (0, 1)]
    assert movie_pair_trial(changed, 2).shift_xy == (-3, 2)
    assert [frame.quality_score for frame in changed.frames] == [1, None, None]
    assert [frame.status for frame in changed.frames] == ['ok', 'manual_review', 'manual_review']
    assert changed.revision != base.revision
    assert changed.corrections[0].baseline_xy == (2, -1)
    assert changed.corrections[0].start_xy == (2, -1)
    assert changed.corrections[0].correction_xy == (1, 0)
    assert changed.corrections[0].shift_xy == (3, -1)
    assert changed.corrections[0].reference.source_frame_index == 0
    assert changed.corrections[0].moving.source_frame_index == 1


def test_two_pair_overrides_replace_without_double_application_and_undo_independently():
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial, remove_movie_correction

    base = cpu_result()
    first = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    unchanged = ManualPairDraft(first.frames[0].original, first.frames[1].original,
                                movie_pair_trial(first, 1)).apply()
    assert apply_movie_correction(first, unchanged) is first
    both = apply_movie_correction(first, corrected_trial(first, 2, 0, 1))
    assert [f.shift_xy for f in both.frames] == [(0, 0), (3, -1), (0, 2)]
    assert len(both.corrections) == 2
    replaced = apply_movie_correction(both, corrected_trial(both, 1, 1, 0))
    assert [f.shift_xy for f in replaced.frames] == [(0, 0), (4, -1), (1, 2)]
    assert len(replaced.corrections) == 2
    undo_first = remove_movie_correction(both, 1)
    assert [f.shift_xy for f in undo_first.frames] == [(0, 0), (2, -1), (-1, 2)]
    assert undo_first.frames[1].quality_score == base.frames[1].quality_score
    assert undo_first.frames[2].quality_score is None
    assert len(undo_first.corrections) == 1
    restored = remove_movie_correction(undo_first, 2)
    assert [f.shift_xy for f in restored.frames] == [(0, 0), (2, -1), (-1, 1)]
    assert [f.quality_score for f in restored.frames] == [f.quality_score for f in base.frames]
    assert [f.status for f in restored.frames] == [f.status for f in base.frames]
    assert restored.corrections == ()


def test_starting_another_edit_identifies_the_current_manual_movie_result():
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial

    base = cpu_result()
    changed = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    start = movie_pair_trial(changed, 1)
    assert start.shift_xy == (3, -1)
    assert 'ręczna' in start.label
    draft = ManualPairDraft(changed.frames[0].original, changed.frames[1].original, start)
    draft.nudge(-1, 0)
    trial = draft.apply()
    assert 'ręczna' in trial.manual.source_label
    assert trial.movie_revision == changed.revision


def test_fractional_trial_uses_original_samples_and_undo_restores_geometry():
    from dataclasses import replace

    import numpy as np
    from nanotrack.core import RegistrationFrameResult
    from make_registration_fixtures import frames_with_data
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial, remove_movie_correction

    class QuarterPixelBackend:
        def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
            return RegistrationFrameResult(moving_frame_index, (0.5, -0.25), 'controlled')

    samples = np.array([[0, 1, 4, 9], [16, 25, 36, 49], [64, 81, 100, 121]], dtype=np.float64)
    originals = frames_with_data(samples, samples.copy())
    before = [frame.data.copy() for frame in originals]
    base = register_series(originals, backend=QuarterPixelBackend())
    start = replace(movie_pair_trial(base, 1), shift_xy=(0.25, -0.25), label='Próba innej metody')
    draft = ManualPairDraft(*originals, start)
    draft.nudge(1, 0)
    changed = apply_movie_correction(base, draft.apply())

    assert changed.frames[1].shift_xy == (1.25, -0.25)
    assert changed.frames[1].image.data[1, 2] == 6.25  # Original bilinear sample at (x=.75, y=.25).
    assert changed.frames[1].original_rect == (1.25, 0.75, 4, 3)
    assert changed.canvas_shape == (4, 6)
    assert changed.padding_ltrb == (0, 1, 2, 0)
    assert changed.frames[1].valid_mask.sum() == 6
    assert changed.pixel_size_nm == base.pixel_size_nm
    assert changed.frames[1].image.size_x_nm == 6 * changed.pixel_size_nm[0]
    assert changed.frames[1].image.size_y_nm == 4 * changed.pixel_size_nm[1]
    assert np.isnan(changed.frames[1].image.data[~changed.frames[1].valid_mask]).all()
    for original, old in zip(originals, before):
        np.testing.assert_array_equal(original.data, old)
    restored = remove_movie_correction(changed, 1)
    assert restored.padding_ltrb == base.padding_ltrb
    assert restored.canvas_shape == base.canvas_shape
    for expected, actual in zip(base.frames, restored.frames):
        np.testing.assert_array_equal(actual.image.data, expected.image.data)
        np.testing.assert_array_equal(actual.valid_mask, expected.valid_mask)
        assert actual.original is expected.original
        assert not actual.image.data.flags.writeable


def test_cancel_and_render_error_preserve_previous_complete_movie_and_corrections():
    from dataclasses import replace
    from threading import Event

    import numpy as np
    import pytest
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.registration import RegistrationCancelled, RegistrationError

    base = cpu_result()
    previous = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    old_values = [frame.image.data.copy() for frame in previous.frames]
    trial = corrected_trial(previous, 2, 0, 1)
    stop = Event()
    reports = []

    def progress(done, total, text):
        reports.append((done, total))
        stop.set()

    with pytest.raises(RegistrationCancelled):
        apply_movie_correction(previous, trial, progress=progress, cancelled=stop.is_set)
    assert reports == [(1, 3)]
    start = replace(movie_pair_trial(previous, 1), shift_xy=(1e30, 0))
    huge = ManualPairDraft(previous.frames[0].original, previous.frames[1].original, start).apply()
    with pytest.raises(RegistrationError, match='Aligned'):
        apply_movie_correction(previous, huge)
    assert len(previous.corrections) == 1
    assert [f.shift_xy for f in previous.frames] == [(0, 0), (3, -1), (0, 1)]
    for frame, old in zip(previous.frames, old_values):
        np.testing.assert_array_equal(frame.image.data, old)


def test_stale_or_unbound_trial_and_deleted_series_require_new_registration():
    from dataclasses import replace

    import pytest
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial, remove_movie_correction
    from stmviewer.registration import RegistrationError

    base = cpu_result()
    trial = corrected_trial(base, 1, 1, 0)
    changed = apply_movie_correction(base, trial)
    for active, candidate in ((changed, trial), (base, replace(trial, movie_revision=None)),
                              (cpu_result(), trial)):
        with pytest.raises(RegistrationError, match='nieaktualna'):
            apply_movie_correction(active, candidate)
    wrong_pair = replace(trial, moving=trial.reference)
    with pytest.raises(RegistrationError, match='pary'):
        apply_movie_correction(base, wrong_pair)
    for source in (base, changed):
        after_deletion = source.without_frame(0)
        assert not after_deletion.corrections_editable
        assert after_deletion.canvas_shape == source.canvas_shape
        assert after_deletion.padding_ltrb == source.padding_ltrb
        assert after_deletion.frames[0] is source.frames[1]
        assert after_deletion.corrections == source.corrections
        assert [f.source.source_frame_index for f in after_deletion.baseline] == [0, 1, 2]
        assert [f.shift_xy for f in after_deletion.baseline] == [(0, 0), (2, -1), (-1, 1)]
        for operation in (lambda: movie_pair_trial(after_deletion, 1),
                          lambda: apply_movie_correction(after_deletion, trial),
                          lambda: remove_movie_correction(after_deletion, 1)):
            with pytest.raises(RegistrationError, match='nową pełną rejestrację'):
                operation()
    fresh = register_series(tuple(frame.original for frame in changed.frames))
    assert fresh.corrections == ()
    assert fresh.corrections_editable
    assert fresh.revision != changed.revision
    assert [f.shift_xy for f in fresh.frames] == [(0, 0), (2, -1), (-1, 1)]
