"""Graph candidate -> active movie and frozen graph -> manual workflow."""
from dataclasses import replace

import numpy as np
import pytest

from make_registration_fixtures import frames_with_data
from stmviewer.graph_provenance import graph_sources
from stmviewer.graph_registration import solve_graph
from stmviewer.graph_types import GraphConfig, GraphEdge


def original_frames(count=2):
    samples = np.array([[0, 1, 4, 9], [16, 25, 36, 49], [64, 81, 100, 121]], dtype=np.float64)
    return frames_with_data(*(samples.copy() for _ in range(count)))


def candidate(frames, edges=None):
    edges = edges or (GraphEdge(0, 1, (1.25, -.25), 'ok'),)
    config = GraphConfig(3, '/not-installed/model.ckpt', 'a' * 64,
                         'cpu', 'CPU', (), (), 'test-fixture')
    return solve_graph(graph_sources(frames), edges, config)


def test_selected_graph_renders_original_subpixel_samples_and_geometry_once():
    from stmviewer.graph_application import apply_graph_to_movie

    originals = original_frames()
    graph = candidate(originals)
    result = apply_graph_to_movie(originals, graph)

    assert [f.shift_xy for f in result.frames] == [(0., 0.), (1.25, -.25)]
    assert result.frames[1].image.data[1, 2] == 6.25
    assert result.frames[1].original_rect == (1.25, .75, 4, 3)
    assert result.canvas_shape == (4, 6)
    assert result.padding_ltrb == (0, 1, 2, 0)
    assert result.frames[1].valid_mask.sum() == 6
    assert np.isnan(result.frames[1].image.data[~result.frames[1].valid_mask]).all()
    assert result.frames[1].original is originals[1]
    np.testing.assert_array_equal(originals[1].data, originals[0].data)
    assert result.frames[1].image.size_x_nm == 6 * result.pixel_size_nm[0]
    assert result.frames[1].image.size_y_nm == 4 * result.pixel_size_nm[1]
    assert not result.frames[1].image.data.flags.writeable
    assert result.graph_application.graph is graph
    assert result.graph_application.positions == graph.positions
    assert result.predecessor is None
    assert result.corrections == ()
    assert [f.quality_score for f in result.frames] == [None, None]


def test_incomplete_stale_or_numerically_invalid_candidates_have_an_explicit_refusal():
    from stmviewer.graph_application import apply_graph_to_movie, graph_application_reason
    from stmviewer.registration import RegistrationError

    originals = original_frames()
    graph = candidate(originals)
    disconnected = candidate(originals, (GraphEdge(0, 1, None, 'missing', 'no texture'),))
    changed_pixels = (originals[0], replace(originals[1], data=originals[1].data + 1))
    changed_shape = (originals[0], replace(originals[1], data=originals[1].data[:, :-1]))
    invalid = [
        (originals, disconnected),
        (originals, replace(graph, positions=None)),
        (originals, replace(graph, positions=((0., 0.), (2., 0.)))),
        (originals, replace(graph, positions=((0., 0.), (float('nan'), 0.)))),
        (originals, replace(graph, edges=())),
        (originals, replace(graph, edges=(replace(graph.edges[0], status='cancelled'),))),
        (originals, replace(graph, edges=(replace(graph.edges[0], quality_score=float('nan')),))),
        (originals, replace(graph, config=replace(graph.config, settings_version=99))),
        (originals[::-1], graph),
        (changed_pixels, graph),
        (changed_shape, graph),
        (originals[:1], graph),
    ]
    for frames, invalid_graph in invalid:
        assert graph_application_reason(frames, invalid_graph)
        with pytest.raises(RegistrationError):
            apply_graph_to_movie(frames, invalid_graph)
    assert graph_application_reason(originals, graph) is None


def test_only_explicitly_selected_converged_huber_variant_becomes_the_base():
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.graph_registration import graph_pairs
    from stmviewer.registration import RegistrationError
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig

    originals = original_frames(4)
    graph = candidate(originals, tuple(
        GraphEdge(i, j, (12., 16.) if (i, j) == (0, 3) else (0., 0.), 'ok')
        for i, j in graph_pairs(4, 3)))
    huber = solve_robust_graph(graph, RobustConfig(threshold_px=2.))
    candidate_graph = replace(graph, robust_trials=(huber,))
    result = apply_graph_to_movie(originals, candidate_graph, robust_revision=huber.revision)
    np.testing.assert_allclose([f.shift_xy for f in result.frames],
                               ((0, 0), (.6, .8), (.6, .8), (1.2, 1.6)), atol=1e-5)
    assert result.graph_application.robust_revision == huber.revision
    assert result.graph_application.solver == 'block-huber-irls-v1'
    ls = apply_graph_to_movie(originals, candidate_graph)
    np.testing.assert_allclose([f.shift_xy for f in ls.frames],
                               ((0, 0), (3, 4), (3, 4), (6, 8)), atol=1e-10)
    invalid_variants = (
        replace(huber, measurement_id='different'),
        replace(huber, gradient_inf=100.),
        replace(huber, status='iteration_limit', positions=None),
    )
    for invalid in invalid_variants:
        with pytest.raises(RegistrationError):
            apply_graph_to_movie(originals, replace(graph, robust_trials=(invalid,)),
                                 robust_revision=invalid.revision)
    with pytest.raises(RegistrationError):
        apply_graph_to_movie(originals, candidate_graph, robust_revision='missing-variant')


def test_manual_overrides_use_frozen_global_differences_and_survive_independent_undo():
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.manual_movie import (
        apply_movie_correction, movie_pair_trial, remove_movie_correction,
    )
    from stmviewer.manual_pair import ManualPairDraft
    from test_manual_movie import corrected_trial

    originals = original_frames(3)
    graph = candidate(originals, (GraphEdge(0, 1, (.5, 0.), 'ok'),
                                 GraphEdge(0, 2, (4., 0.), 'ok'),
                                 GraphEdge(1, 2, (.5, 0.), 'ok')))
    base = apply_graph_to_movie(originals, graph)
    assert movie_pair_trial(base, 1).shift_xy == (1.5, 0.)
    assert graph.edges[0].shift_xy == (.5, 0.)
    first = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    both = apply_movie_correction(first, corrected_trial(first, 2, 0, 1))
    assert both.graph_application is base.graph_application
    assert both.baseline == base.baseline
    assert [f.shift_xy for f in both.frames] == [(0., 0.), (2.5, 0.), (4., 1.)]
    assert len(both.corrections) == 2
    assert both.corrections[0].baseline_xy == (1.5, 0.)
    assert both.frames[2].inherited_uncertainty
    assert all(f.quality_score is None for f in both.frames)
    unchanged_trial = ManualPairDraft(originals[0], originals[1], movie_pair_trial(both, 1)).apply()
    assert apply_movie_correction(both, unchanged_trial) is both
    remaining = remove_movie_correction(both, 1)
    assert [f.shift_xy for f in remaining.frames] == [(0., 0.), (1.5, 0.), (3., 1.)]
    restored = remove_movie_correction(remaining, 2)
    assert [f.shift_xy for f in restored.frames] == [(0., 0.), (1.5, 0.), (3., 0.)]
    assert restored.graph_application is base.graph_application
    assert restored.corrections == ()
    for before, after in zip(base.frames, restored.frames, strict=True):
        np.testing.assert_array_equal(before.image.data, after.image.data)


def test_chain_with_manual_corrections_can_be_restored_exactly_without_pixels_in_snapshot():
    from dataclasses import fields, is_dataclass

    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.registration import render_registration, FrameOrigin
    from test_manual_movie import corrected_trial

    originals = original_frames(3)
    chain = render_registration(originals, ((0., 0.), (.5, -.25), (-.5, .75)),
                                ('ok', 'ok', 'low_confidence'), (.9, .8, .4),
                                (False, False, False),
                                reference=FrameOrigin(originals[0].source, 0),
                                method='Deep Matcher', device='CUDA')
    corrected = apply_movie_correction(chain, corrected_trial(chain, 1, 1, 0))
    graph = candidate(originals, (GraphEdge(0, 1, (.5, 0.), 'ok'),
                                 GraphEdge(0, 2, (4., 0.), 'ok'),
                                 GraphEdge(1, 2, (.5, 0.), 'ok')))
    applied = apply_graph_to_movie(originals, graph, previous=corrected)
    saved = applied.predecessor
    assert saved.final_positions == ((0., 0.), (1.5, -.25), (.5, .75))
    assert saved.baseline == corrected.baseline
    assert saved.corrections == corrected.corrections
    assert saved.method == 'Deep Matcher' and saved.device == 'CUDA'

    def contains_array(value):
        if isinstance(value, np.ndarray):
            return True
        if is_dataclass(value):
            return any(contains_array(getattr(value, item.name)) for item in fields(value))
        if isinstance(value, tuple):
            return any(contains_array(item) for item in value)
        return False

    assert not contains_array(saved)
    restored = restore_movie_result(originals, applied)
    assert restored.baseline == corrected.baseline
    assert restored.corrections == corrected.corrections
    assert restored.graph_application is None
    assert restored.method == corrected.method and restored.device == corrected.device
    assert restored.canvas_shape == corrected.canvas_shape
    assert restored.padding_ltrb == corrected.padding_ltrb
    assert restored.pixel_size_nm == corrected.pixel_size_nm
    assert restored.revision not in (corrected.revision, applied.revision)
    for expected, actual in zip(corrected.frames, restored.frames, strict=True):
        assert actual.shift_xy == expected.shift_xy
        assert actual.origin_xy == expected.origin_xy
        assert actual.status == expected.status
        assert actual.quality_score == expected.quality_score
        assert actual.inherited_uncertainty == expected.inherited_uncertainty
        np.testing.assert_array_equal(actual.image.data, expected.image.data)
        np.testing.assert_array_equal(actual.valid_mask, expected.valid_mask)
    graph_again = restore_movie_result(originals, restored)
    assert graph_again.graph_application == applied.graph_application
    assert graph_again.predecessor.graph_application is None
    for expected, actual in zip(applied.frames, graph_again.frames, strict=True):
        np.testing.assert_array_equal(actual.image.data, expected.image.data)


def test_restore_keeps_historical_canvas_of_a_result_with_deleted_extreme_frame():
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.manual_movie import movie_pair_trial
    from stmviewer.registration import FrameOrigin, RegistrationError, render_registration

    originals = original_frames(3)
    complete = render_registration(originals, ((0., 0.), (4., 0.), (1.25, -.25)),
                                   ('ok',) * 3, (1.,) * 3, (False,) * 3,
                                   reference=FrameOrigin(originals[0].source, 0),
                                   method='Deep Matcher', device='CPU')
    partial = complete.without_frame(1)
    surviving = tuple(item.original for item in partial.frames)
    applied = apply_graph_to_movie(surviving, candidate(surviving), previous=partial)
    assert applied.padding_ltrb == (0, 1, 2, 0)
    restored = restore_movie_result(surviving, applied)
    assert restored.padding_ltrb == (0, 1, 4, 0)
    assert restored.canvas_shape == (4, 8)
    assert not restored.corrections_editable
    assert restored.baseline == complete.baseline
    for before, after in zip(partial.frames, restored.frames, strict=True):
        np.testing.assert_array_equal(before.image.data, after.image.data)
        np.testing.assert_array_equal(before.valid_mask, after.valid_mask)
    with pytest.raises(RegistrationError, match='nową pełną rejestrację'):
        movie_pair_trial(restored, 1)


def test_cancelled_or_failed_application_and_restore_leave_the_entire_active_result_unchanged():
    from threading import Event

    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.registration import RegistrationCancelled, RegistrationError
    from test_manual_movie import corrected_trial

    originals = original_frames()
    graph = candidate(originals)
    base = apply_graph_to_movie(originals, graph)
    corrected = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    active = apply_graph_to_movie(originals, graph, previous=corrected)
    active = apply_movie_correction(active, corrected_trial(active, 1, 0, 1))
    old_images = tuple(item.image.data.copy() for item in active.frames)
    old_baseline, old_corrections = active.baseline, active.corrections
    old_predecessor, old_application = active.predecessor, active.graph_application
    for operation in (
            lambda **kwargs: apply_graph_to_movie(originals, graph, previous=active, **kwargs),
            lambda **kwargs: restore_movie_result(originals, active, **kwargs)):
        stop = Event()
        reports = []

        def cancel_after_first(done, total, description):
            reports.append((done, total))
            stop.set()

        with pytest.raises(RegistrationCancelled):
            operation(progress=cancel_after_first, cancelled=stop.is_set)
        assert reports == [(1, 2)]
    huge = candidate(originals, (GraphEdge(0, 1, (1e30, 0.), 'ok'),))
    with pytest.raises(RegistrationError, match='Aligned'):
        apply_graph_to_movie(originals, huge, previous=active)
    damaged = replace(active, predecessor=replace(active.predecessor, final_frames=(
        active.predecessor.final_frames[0],
        replace(active.predecessor.final_frames[1], shift_xy=(float('nan'), 0.)),
    )))
    with pytest.raises(RegistrationError):
        restore_movie_result(originals, damaged)
    assert active.baseline is old_baseline
    assert active.corrections is old_corrections
    assert active.predecessor is old_predecessor
    assert active.graph_application is old_application
    for image, before in zip(active.frames, old_images, strict=True):
        np.testing.assert_array_equal(image.image.data, before)


def test_switching_base_or_deleting_sources_invalidates_old_trials_and_restore_binding():
    from stmviewer.graph_application import (
        apply_graph_to_movie, restore_movie_result, restore_movie_reason,
    )
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.registration import RegistrationError
    from test_manual_movie import corrected_trial

    originals = original_frames()
    graph = candidate(originals)
    old = apply_graph_to_movie(originals, graph)
    manual_trial = corrected_trial(old, 1, 1, 0)
    active = apply_graph_to_movie(originals, graph, previous=old)
    for result in (active, restore_movie_result(originals, active)):
        with pytest.raises(RegistrationError, match='nieaktualna'):
            apply_movie_correction(result, manual_trial)
    deleted = active.without_frame(0)
    with pytest.raises(RegistrationError):
        apply_graph_to_movie(originals[1:], graph, previous=deleted)
    with pytest.raises(RegistrationError, match='nową pełną rejestrację'):
        movie_pair_trial(deleted, 1)
    invalid_frames = (originals[::-1], originals[:1],
                      (originals[0], replace(originals[1], data=originals[1].data + 1)),
                      (originals[0], replace(originals[1], size_x_nm=999.)))
    for changed in invalid_frames:
        assert restore_movie_reason(changed, active)
        with pytest.raises(RegistrationError):
            restore_movie_result(changed, active)


def test_restore_preserves_unknown_physical_canvas_scale_after_calibration_outlier_is_deleted():
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.registration import FrameOrigin, render_registration

    first, second, third = original_frames(3)
    originals = (first, replace(second, size_x_nm=999.), third)
    complete = render_registration(originals, ((0., 0.), (0., 0.), (1.25, -.25)),
                                   ('ok',) * 3, (1.,) * 3, (False,) * 3,
                                   reference=FrameOrigin(first.source, 0),
                                   method='Deep Matcher', device='CPU')
    assert complete.pixel_size_nm is None
    partial = complete.without_frame(1)
    surviving = (first, third)
    applied = apply_graph_to_movie(surviving, candidate(surviving), previous=partial)
    assert applied.pixel_size_nm is not None
    restored = restore_movie_result(surviving, applied)
    assert restored.pixel_size_nm is None
    assert all(item.image.size_x_nm is None and item.image.size_y_nm is None
               for item in restored.frames)
    assert restored.frames[0].original.size_x_nm == first.size_x_nm
