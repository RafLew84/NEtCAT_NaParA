"""MatchAnything external-inference boundary and common original-pixel consensus."""

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions


def test_missing_matchanything_files_are_unavailable_without_loading_model(tmp_path):
    from stmviewer.matchanything_matcher import matchanything_unavailable_reason
    missing = tmp_path / 'missing'
    reason = matchanything_unavailable_reason(DeepMatcherOptions(missing / 'weights.ckpt', 'cpu', missing))
    assert reason is not None and 'kod' in reason.lower()

class ExternalEngine:
    """External model stand-in with independently specified correspondences."""
    closed = False

    def match(self, reference, moving, *, reference_shape, moving_shape):
        assert reference.shape == moving.shape == (640, 640)
        assert reference_shape == moving_shape == (480, 640)
        assert reference[480:, :].max() == 0
        points = np.array([(x, y) for y in (80., 160., 280., 400.) for x in (40., 180., 320., 520.)])
        padding = np.tile([555., 600.], (40, 1))
        return np.vstack((points, padding)), np.vstack((points - (-9.536423841059603, 29.58904109589041), padding))

    def close(self):
        self.closed = True


def test_known_translation_ignores_padding_and_keeps_model_identity():
    from stmviewer.matchanything_matcher import MatchAnythingBackend
    from stmviewer.correspondence_consensus import CorrespondenceConfig
    engine = ExternalEngine()
    backend = MatchAnythingBackend(engine, device='CPU', provenance=(('model', 'MatchAnything-ELoFTR'),))
    image = np.arange(73 * 151, dtype=np.float64).reshape(73, 151)
    result = backend.estimate(image, image + 5., moving_frame_index=3)
    np.testing.assert_allclose(result.shift_xy, [-2.25, 4.5])
    assert result.method == 'matchanything_eloftr' and result.frame_index == 3
    assert backend.config == CorrespondenceConfig()
    evidence = backend.last_diagnostics
    assert evidence.preparation[0].padding_ltrb == (0, 0, 0, 160)
    assert evidence.preparation[1].value_range == (5., 11027.)
    assert evidence.model_provenance == backend.provenance
    backend.close()
    assert engine.closed


def test_unverified_code_and_checkpoint_are_rejected_before_execution(tmp_path):
    from stmviewer.matchanything_matcher import load_matchanything_backend, WEIGHTS_BYTES
    from stmviewer.registration import RegistrationError
    source = tmp_path / 'source'
    (source / 'src/loftr').mkdir(parents=True)
    (source / 'src/loftr/loftr.py').write_text('raise AssertionError("unverified source executed")\n')
    weights = tmp_path / 'weights.ckpt'
    weights.write_bytes(b'bad')
    options = DeepMatcherOptions(weights, 'cpu', source)
    with pytest.raises(RegistrationError, match='rozmiar wag'):
        load_matchanything_backend(options)
    with weights.open('r+b') as stream:
        stream.truncate(WEIGHTS_BYTES)
    with pytest.raises(RegistrationError, match='Niezgodny kod'):
        load_matchanything_backend(options)


def test_model_allocation_failure_closes_runtime_and_discards_stale_evidence():
    from stmviewer.matchanything_matcher import MatchAnythingBackend
    from stmviewer.registration import RegistrationError
    class FailingEngine(ExternalEngine):
        def match(self, reference, moving, **geometry):
            raise MemoryError('CUDA out of memory')
    engine = FailingEngine()
    backend = MatchAnythingBackend(engine, device='CUDA:0', provenance=())
    image = np.zeros((73, 151))
    with pytest.raises(RegistrationError, match='out of memory') as failure:
        backend.estimate(image, image, moving_frame_index=1)
    assert isinstance(failure.value.__cause__, MemoryError)
    assert backend.last_diagnostics is None
    assert engine.closed


def test_cancellation_during_inference_closes_runtime_without_partial_evidence():
    from stmviewer.matchanything_matcher import MatchAnythingBackend
    from stmviewer.registration import RegistrationCancelled
    cancelled = False
    class CancellingEngine(ExternalEngine):
        def match(self, reference, moving, **geometry):
            nonlocal cancelled
            result = super().match(reference, moving, **geometry)
            cancelled = True
            return result
    engine = CancellingEngine()
    backend = MatchAnythingBackend(engine, device='CPU', provenance=(), cancelled=lambda: cancelled)
    image = np.zeros((73, 151))
    with pytest.raises(RegistrationCancelled):
        backend.estimate(image, image, moving_frame_index=1)
    assert backend.last_diagnostics is None and engine.closed


def test_local_refusal_retains_evidence_and_allows_next_graph_pair():
    from stmviewer.matchanything_matcher import MatchAnythingBackend
    from stmviewer.correspondence_types import CorrespondenceRefusal
    class SparseEngine(ExternalEngine):
        sparse = True
        def match(self, reference, moving, **geometry):
            if self.sparse:
                return np.empty((0, 2)), np.empty((0, 2))
            return super().match(reference, moving, **geometry)
    engine = SparseEngine()
    backend = MatchAnythingBackend(engine, device='CPU', provenance=(('model', 'MatchAnything-ELoFTR'),))
    image = np.zeros((73, 151))
    with pytest.raises(CorrespondenceRefusal) as failure:
        backend.estimate(image, image, moving_frame_index=1)
    assert failure.value.diagnostics is backend.last_diagnostics
    assert backend.last_diagnostics.final_shift_xy is None
    assert len(backend.last_diagnostics.preparation) == 2 and not engine.closed
    engine.sparse = False
    result = backend.estimate(image, image, moving_frame_index=2)
    np.testing.assert_allclose(result.shift_xy, [-2.25, 4.5])
    backend.close()


def test_author_preset_records_resize_padding_and_half_pixel_mapping():
    from stmviewer.matchanything_matcher import prepare_matchanything_image, matchanything_points_to_original
    image = np.linspace(2e-9, 9e-9, 100 * 200).reshape(100, 200)
    prepared, geometry = prepare_matchanything_image(image)
    assert prepared.shape == (640, 640)
    assert geometry.model_shape == (640, 640)
    assert geometry.original_shape == (100, 200)
    assert geometry.scale_xy == (3.2, 4.8)
    assert geometry.padding_ltrb == (0, 0, 0, 160)
    assert geometry.normalization == 'minmax-uint8-demo-gray-v1'
    assert np.count_nonzero(prepared[480:]) == 0
    # Independently worked pixel-centre examples: 10→33.1 at scale3.2, 20→97.9 at4.8.
    points = matchanything_points_to_original(np.array([[33.1, 97.9], [161.1, 193.9]]), geometry)
    np.testing.assert_allclose(points, [[10., 20.], [50., 40.]])
