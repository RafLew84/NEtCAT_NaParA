"""Local preparation/runtime boundary, no network or model required by unit tests."""

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.efficient_matcher import efficient_unavailable_reason


def test_missing_source_and_checkpoint_are_explicitly_unavailable(tmp_path):
    missing = tmp_path / 'missing'
    reason = efficient_unavailable_reason(DeepMatcherOptions(missing / 'weights.ckpt', 'cpu', missing))
    assert reason is not None and 'kod' in reason.lower()


def test_preparation_and_mapping_keep_non_square_original_pixels_and_units():
    import numpy as np
    from stmviewer.efficient_matcher import prepare_image, points_to_original

    raw = np.linspace(2e-9, 9e-9, 35 * 73).reshape(35, 73)
    prepared, metadata = prepare_image(raw)
    assert prepared.shape == (64, 96)
    assert metadata.original_shape == (35, 73)
    assert metadata.padding_ltrb == (0, 0, 23, 29)
    np.testing.assert_allclose(prepared[:35, :73].min(), 0)
    np.testing.assert_allclose(prepared[:35, :73].max(), 1)
    from stmviewer.correspondence_types import ImagePreparation
    mapping = ImagePreparation((40, 80), (64, 160), (1.5, 1.25), (4, 6, 36, 8), (0., 1.))
    points = points_to_original(np.array([[19., 31.], [94., 43.5]]), mapping)
    np.testing.assert_allclose(points, [[10., 20.], [60., 30.]])


class CorrespondenceEngine:
    """Stand-in for the external inference runtime; points are fixed ground truth."""
    def __init__(self, failure=None):
        self.failure = failure
        self.closed = False

    def match(self, reference, moving):
        import numpy as np
        if self.failure is not None:
            raise self.failure
        points = np.array([(x, y) for y in (15., 30., 48., 60.) for x in (20., 55., 95., 130.)])
        return points, points - (-2.25, 4.5)

    def close(self):
        self.closed = True


def test_backend_uses_original_xy_and_preserves_preparation_and_model_provenance():
    import numpy as np
    from stmviewer.efficient_matcher import EfficientBackend
    engine = CorrespondenceEngine()
    backend = EfficientBackend(engine, device='CPU', provenance=(('weights_sha256', 'a' * 64),))
    image = np.arange(73 * 151, dtype=np.float64).reshape(73, 151)
    result = backend.estimate(image, image + 5., moving_frame_index=3)
    np.testing.assert_allclose(result.shift_xy, (-2.25, 4.5))
    assert result.frame_index == 3
    assert result.status == 'manual_review'
    evidence = backend.last_diagnostics
    assert evidence.preparation[0].padding_ltrb == (0, 0, 9, 23)
    assert evidence.preparation[1].value_range == (5., 11027.)
    assert evidence.model_provenance == backend.provenance
    backend.close()
    assert engine.closed


def test_runtime_oom_aborts_without_retry_resize_or_stale_evidence():
    import numpy as np
    import pytest
    from stmviewer.efficient_matcher import EfficientBackend
    from stmviewer.registration import RegistrationError

    class FailingEngine(CorrespondenceEngine):
        def match(self, reference, moving):
            assert reference.shape == (96, 160)
            assert moving.shape == (96, 160)
            raise MemoryError('CUDA out of memory')
    engine = FailingEngine()
    backend = EfficientBackend(engine, device='CUDA:0', provenance=())
    image = np.arange(73 * 151, dtype=np.float64).reshape(73, 151)
    with pytest.raises(RegistrationError, match='out of memory') as failure:
        backend.estimate(image, image, moving_frame_index=1)
    assert isinstance(failure.value.__cause__, MemoryError)
    assert backend.last_diagnostics is None
    backend.close()
    assert engine.closed


def test_cancellation_during_inference_discards_the_result():
    import numpy as np
    import pytest
    from stmviewer.efficient_matcher import EfficientBackend
    from stmviewer.registration import RegistrationCancelled

    cancelled = False
    class CancellingEngine(CorrespondenceEngine):
        def match(self, reference, moving):
            nonlocal cancelled
            points = super().match(reference, moving)
            cancelled = True
            return points
    engine = CancellingEngine()
    backend = EfficientBackend(engine, device='CPU', provenance=(), cancelled=lambda: cancelled)
    image = np.arange(73 * 151, dtype=np.float64).reshape(73, 151)
    with pytest.raises(RegistrationCancelled):
        backend.estimate(image, image, moving_frame_index=1)
    assert backend.last_diagnostics is None
    backend.close()
    assert engine.closed


def test_refusal_retains_preparation_provenance_and_no_global_xy():
    import numpy as np
    import pytest
    from stmviewer.correspondence_types import CorrespondenceRefusal
    from stmviewer.efficient_matcher import EfficientBackend

    class EmptyEngine(CorrespondenceEngine):
        def match(self, reference, moving):
            return np.empty((0, 2)), np.empty((0, 2))
    backend = EfficientBackend(EmptyEngine(), device='CPU', provenance=(('source_commit', 'pinned'),))
    image = np.ones((73, 151))
    with pytest.raises(CorrespondenceRefusal) as failure:
        backend.estimate(image, image, moving_frame_index=1)
    assert failure.value.diagnostics is backend.last_diagnostics
    assert len(failure.value.diagnostics.preparation) == 2
    assert failure.value.diagnostics.model_provenance == backend.provenance
    assert failure.value.diagnostics.final_shift_xy is None
    backend.close()


def test_invalid_artifacts_are_rejected_before_external_code_runs(tmp_path):
    import pytest
    from stmviewer.efficient_matcher import load_efficient_backend, WEIGHTS_BYTES
    from stmviewer.registration import RegistrationError
    source = tmp_path / 'source'
    (source / 'src/loftr').mkdir(parents=True)
    (source / 'src/loftr/loftr.py').write_text('raise AssertionError("unverified code executed")\n')
    weights = tmp_path / 'wrong.ckpt'
    weights.write_bytes(b'wrong')
    options = DeepMatcherOptions(weights, 'cpu', source)
    with pytest.raises(RegistrationError, match='rozmiar wag'):
        load_efficient_backend(options)
    with weights.open('r+b') as stream:
        stream.truncate(WEIGHTS_BYTES)
    with pytest.raises(RegistrationError, match='Niezgodny kod'):
        load_efficient_backend(options)
