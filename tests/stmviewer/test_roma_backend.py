"""RoMa's public image/coordinate and model-execution boundaries."""

import numpy as np


def test_normalized_field_maps_separate_non_square_images_and_padding_to_original():
    from stmviewer.roma_matcher import normalized_points_to_original
    from stmviewer.correspondence_types import ImagePreparation

    preparation = ImagePreparation((40, 80), (64, 160), (1.5, 1.25), (4, 6, 36, 8), (0., 1.))
    # RoMa uses edge coordinates: (-1,-1) maps to (0,0), (1,1) to (W,H).
    points = np.array([[-.7625, -.03125], [.175, .359375]])
    np.testing.assert_allclose(normalized_points_to_original(points, preparation), [[10., 20.], [60., 30.]])


class NormalizedRuntime:
    def __init__(self, failure=None):
        self.failure = failure
        self.closed = False

    def match(self, reference, moving):
        if self.failure:
            raise self.failure
        points = np.array([(x, y) for y in (10., 25., 40., 60.) for x in (15., 45., 85., 130.)])
        return points / (151., 73.) * 2 - 1, (points - (-2.25, 4.5)) / (151., 73.) * 2 - 1

    def close(self):
        self.closed = True


def test_backend_returns_one_original_pixel_translation_and_rgb_preparation():
    from stmviewer.roma_matcher import RomaBackend
    engine = NormalizedRuntime()
    backend = RomaBackend(engine, device='CPU', provenance=(('model', 'RoMa v2'),), preset='turbo')
    image = np.arange(73 * 151, dtype=np.float64).reshape(73, 151)
    result = backend.estimate(image, image + 5, moving_frame_index=4)
    np.testing.assert_allclose(result.shift_xy, (-2.25, 4.5))
    assert result.frame_index == 4
    assert result.method == 'roma_v2'
    evidence = backend.last_diagnostics
    assert evidence.preparation[0].model_shape == (320, 320)
    assert evidence.preparation[0].channels == 3
    assert evidence.preparation[1].value_range == (5., 11027.)
    assert evidence.model_provenance == backend.provenance
    backend.close()
    assert engine.closed


def test_dense_wrong_cluster_in_one_cell_does_not_outvote_spread_matching_texture():
    from stmviewer.roma_matcher import RomaBackend
    correct = np.array([(x,y) for y in (20.,50.,80.,110.,140.,170.) for x in (20.,50.,80.,110.,140.,170.)])
    # 600 dense wrong vectors in a small artifact versus 36 dispersed true vectors.
    wrong = np.random.default_rng(4).uniform(1,8,(600,2))
    class DenseRuntime(NormalizedRuntime):
        def match(self,reference,moving):
            p0=np.concatenate((correct,wrong))
            p1=np.concatenate((correct-(2.25,-3.5),wrong+(30.,30.)))
            return p0/200.*2-1,p1/200.*2-1
    backend=RomaBackend(DenseRuntime(),device='CPU',provenance=())
    image=np.arange(40000,dtype=np.float64).reshape(200,200)
    result=backend.estimate(image,image,moving_frame_index=1)
    np.testing.assert_allclose(result.shift_xy,(2.25,-3.5))
    assert backend.last_diagnostics.input_count < 100


def test_missing_interpreter_is_reported_without_running_any_code(tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.roma_matcher import roma_unavailable_reason, load_roma_backend
    from stmviewer.registration import RegistrationError
    import pytest
    options=DeepMatcherOptions(interpreter=tmp_path/'missing-python')
    assert 'interpreter' in roma_unavailable_reason(options)
    with pytest.raises(RegistrationError,match='interpreter'):
        load_roma_backend(options)


def test_runtime_failure_never_retries_or_keeps_previous_diagnostics():
    from stmviewer.roma_matcher import RomaBackend
    from stmviewer.registration import RegistrationError
    import pytest
    runtime=NormalizedRuntime()
    backend=RomaBackend(runtime,device='CPU',provenance=())
    image=np.arange(73*151,dtype=np.float64).reshape(73,151)
    backend.estimate(image,image,moving_frame_index=1)
    assert backend.last_diagnostics is not None
    runtime.failure=MemoryError('CUDA out of memory')
    with pytest.raises(RegistrationError,match='out of memory') as failure:
        backend.estimate(image,image,moving_frame_index=2)
    assert isinstance(failure.value.__cause__,MemoryError)
    assert backend.last_diagnostics is None
    backend.close()
    assert runtime.closed


def test_too_few_points_remain_refusal_with_preparation_and_no_xy():
    from stmviewer.roma_matcher import RomaBackend
    from stmviewer.correspondence_types import CorrespondenceRefusal
    import pytest
    class Empty(NormalizedRuntime):
        def match(self,reference,moving):
            return np.empty((0,2)),np.empty((0,2))
    backend=RomaBackend(Empty(),device='CPU',provenance=(('model','RoMa v2'),))
    with pytest.raises(CorrespondenceRefusal) as failure:
        backend.estimate(np.ones((20,30)),np.ones((20,30)),moving_frame_index=1)
    assert failure.value.diagnostics is backend.last_diagnostics
    assert backend.last_diagnostics.final_shift_xy is None
    assert len(backend.last_diagnostics.preparation)==2
    backend.close()


def test_separate_image_shapes_keep_correct_subpixel_xy():
    from stmviewer.roma_matcher import RomaBackend
    points=np.array([(x,y) for y in (15.,25.,35.) for x in (15.,35.,55.,70.)])
    class DifferentShapes(NormalizedRuntime):
        def match(self,reference,moving):
            return points/(80.,50.)*2-1,(points-(1.25,-2.5))/(200.,120.)*2-1
    backend=RomaBackend(DifferentShapes(),device='CPU',provenance=(),preset='base')
    result=backend.estimate(np.ones((50,80)),np.ones((120,200)),moving_frame_index=1)
    np.testing.assert_allclose(result.shift_xy,(1.25,-2.5))
    assert backend.last_diagnostics.preparation[0].scale_xy==(8.,12.8)
    assert backend.last_diagnostics.preparation[1].scale_xy==(3.2,640/120)
    backend.close()
