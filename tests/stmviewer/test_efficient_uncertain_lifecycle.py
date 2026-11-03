"""Weak model estimates remain explicit through application and portable storage."""
from dataclasses import replace

from stmviewer.correspondence_metadata import decode_correspondence, encode_correspondence
from test_efficient_session import evidence


def test_weak_correspondence_keeps_status_version_and_shift_when_reopened():
    diagnostic = replace(evidence(), status='low_confidence', settings_version=2,
                         reason='Mały udział zgodnych wektorów; sprawdź obraz.')
    restored = decode_correspondence(encode_correspondence(diagnostic))
    assert restored == diagnostic


def test_weak_estimate_reaches_the_application_without_a_numeric_confidence():
    from nanotrack.core import RegistrationFrameResult
    from stmviewer.registration import estimate_confidence
    result = RegistrationFrameResult(1, (2., -1.), 'efficient_loftr',
                                     status='low_confidence', quality_score=.8)
    assert estimate_confidence('efficient_loftr', result) == ('low_confidence', None)


def test_weak_graph_can_be_applied_corrected_and_reopened_with_its_warning(tmp_path):
    from test_efficient_session import efficient_graph
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState

    frames = tuple(frame.original for frame in cpu_result().frames)
    graph = efficient_graph(frames)
    first = graph.edges[0]
    diagnostic = replace(first.correspondence_diagnostics, status='low_confidence',
                         settings_version=2, reason='Poparcie skupione w małym obszarze.')
    graph = replace(graph, edges=(replace(first, status='low_confidence',
                                          correspondence_diagnostics=diagnostic),) + graph.edges[1:])
    applied = apply_graph_to_movie(frames, graph)
    corrected = apply_movie_correction(applied, corrected_trial(applied, 1, 1, 0))
    path = save_session(tmp_path / 'weak-model.stmsession', SessionState(frames, corrected, graph=graph))
    restored = load_session(path)
    assert restored.graph == graph
    assert restored.registration.graph_application.graph.edges[0].correspondence_diagnostics == diagnostic
    assert restored.registration.frames[1].shift_xy == (3., -1.)


class SequenceCorrespondenceEngine:
    """External model double: one weak pair followed by a well-supported pair."""

    def __init__(self, shape):
        self.shape = shape
        self.first_pair = True

    def match(self, reference, moving):
        import numpy as np
        height, width = self.shape
        grid = np.array([(x * width, y * height)
                         for y in (.15, .35, .6, .85) for x in (.15, .35, .6, .85)])
        p0, p1 = grid, grid - (2., -1.)
        if self.first_pair:
            rng = np.random.default_rng(124)
            p0 = np.vstack((p0, rng.uniform((3, 3), (width - 4, height - 4), (80, 2))))
            p1 = np.vstack((p1, rng.uniform((3, 3), (width - 4, height - 4), (80, 2))))
            self.first_pair = False
        return p0, p1

    def close(self):
        pass


def test_later_review_pair_cannot_hide_inherited_weakness_in_saved_chain(tmp_path, monkeypatch):
    from test_manual_movie import cpu_result
    from stmviewer.efficient_matcher import EfficientBackend
    from stmviewer.registration import register_series
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState

    frames = tuple(frame.original for frame in cpu_result().frames)
    engine = SequenceCorrespondenceEngine(frames[0].data.shape)
    backend = EfficientBackend(engine, device='CPU', provenance=())
    # Replace the optional external model loader; aggregation/rendering/storage stay real.
    monkeypatch.setattr('stmviewer.registration.load_efficient_backend', lambda *args, **kwargs: backend)
    result = register_series(frames, method='efficient_loftr')
    assert [frame.status for frame in result.frames] == ['ok', 'low_confidence', 'low_confidence']
    assert [d.status if d is not None else None for d in result.correspondence_diagnostics] == [
        None, 'low_confidence', 'manual_review']
    saved = save_session(tmp_path / 'weak-chain.stmsession', SessionState(frames, result))
    restored = load_session(saved).registration
    assert [frame.status for frame in restored.frames] == ['ok', 'low_confidence', 'low_confidence']
    assert restored.frames[2].inherited_uncertainty
    assert restored.correspondence_diagnostics == result.correspondence_diagnostics


def test_legacy_evidence_stays_readable_but_cannot_claim_the_new_warning_status():
    import pytest
    old = evidence()
    assert decode_correspondence(encode_correspondence(old)) == old
    with pytest.raises(ValueError, match='status'):
        encode_correspondence(replace(old, status='low_confidence'))


def test_graph_cannot_hide_a_weak_diagnostic_behind_a_review_status():
    import pytest
    from test_efficient_session import efficient_graph
    from test_manual_movie import cpu_result
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.registration import RegistrationError
    frames = tuple(frame.original for frame in cpu_result().frames)
    graph = efficient_graph(frames)
    first = graph.edges[0]
    diagnostic = replace(first.correspondence_diagnostics, status='low_confidence', settings_version=2)
    graph = replace(graph, edges=(replace(first, correspondence_diagnostics=diagnostic),) + graph.edges[1:])
    with pytest.raises(RegistrationError, match='pewności'):
        apply_graph_to_movie(frames, graph)


def test_weak_chain_mpp_keeps_evidence_before_and_after_manual_correction(tmp_path, monkeypatch):
    import numpy as np
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.efficient_matcher import EfficientBackend
    from stmviewer.registration import register_series
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.mpp import open_mpp_series
    from stmviewer.mpp_export import save_aligned_mpp

    frames = tuple(frame.original for frame in cpu_result().frames)
    backend = EfficientBackend(SequenceCorrespondenceEngine(frames[0].data.shape), device='CPU', provenance=())
    monkeypatch.setattr('stmviewer.registration.load_efficient_backend', lambda *args, **kwargs: backend)
    original = register_series(frames, method='efficient_loftr')
    corrected = apply_movie_correction(original, corrected_trial(original, 1, 1, 0))
    for name, result in (('automatic', original), ('corrected', corrected)):
        path = save_aligned_mpp(tmp_path / f'{name}.mpp', result, wsxm_compatible=True)
        loaded = open_mpp_series(path, check_cancelled=lambda: None)
        for actual, expected in zip(loaded, result.frames, strict=True):
            np.testing.assert_array_equal(actual.data, expected.image.data)
            assert actual.alignment.status == expected.status
            assert actual.alignment.quality_score == expected.quality_score
        assert loaded[1].alignment.correspondence == original.correspondence_diagnostics[1]
        assert loaded[1].alignment.correspondence.status == 'low_confidence'
        if name == 'corrected':
            assert loaded[1].alignment.manual_movie.baseline[1].status == 'low_confidence'
