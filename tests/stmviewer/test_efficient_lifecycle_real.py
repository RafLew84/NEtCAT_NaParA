"""Opt-in real checkpoint -> editable movie -> portable session and both exports."""
from dataclasses import replace
import os
from pathlib import Path

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState
from test_efficient_real_integration import original_frames
from test_manual_movie import corrected_trial

pytestmark = pytest.mark.skipif(
    not os.environ.get('STMVIEWER_TEST_EFFICIENT_ROOT'),
    reason='Requires explicitly prepared local EfficientLoFTR code and checkpoint',
)


@pytest.mark.parametrize('mode', ['chain', 'graph'])
def test_real_model_session_manual_edit_and_exports_preserve_pixels(tmp_path, monkeypatch, mode):
    import torch
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.graph_registration import register_graph
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.registration import register_series
    from stmviewer.mpp import open_mpp_series
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from test_avi_export import decode

    torch.set_num_threads(4)
    root = Path(os.environ['STMVIEWER_TEST_EFFICIENT_ROOT'])
    options = DeepMatcherOptions(root / 'weights/eloftr_outdoor.ckpt', 'cpu', root / 'source')
    frames = original_frames()
    graph = None
    if mode == 'chain':
        result = register_series(frames, method='efficient_loftr', deep_options=options)
    else:
        graph = register_graph(frames, method='efficient_loftr', deep_options=options)
        result = apply_graph_to_movie(frames, graph)
    old_positions = np.asarray([item.shift_xy for item in result.frames])
    corrected = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    expected_positions = old_positions + np.array([[0, 0], [1, 0], [1, 0]])
    np.testing.assert_allclose([item.shift_xy for item in corrected.frames], expected_positions, atol=1e-12)
    candidate = None if graph is None else replace(graph, revision='unapplied-efficient-variant')
    session = save_session(tmp_path / f'{mode}.stmsession', SessionState(frames, corrected,
        SessionViewState(view='aligned', method='efficient_loftr', deep_weights=str(options.weights),
                         deep_device='cpu', deep_source=str(options.source)), graph=candidate))
    original_open = Path.open
    def without_model_access(path, *args, **kwargs):
        if path.is_relative_to(root):
            pytest.fail('Restoring a session tried to access model code or weights')
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as context:
        context.setattr(Path, 'open', without_model_access)
        restored = load_session(session)
    assert restored.registration.corrections == corrected.corrections
    assert restored.registration.correspondence_diagnostics == corrected.correspondence_diagnostics
    assert restored.graph == candidate
    if graph is not None:
        assert restored.registration.graph_application.graph == graph
    mpp = save_aligned_mpp(tmp_path / f'{mode}.mpp', restored.registration, wsxm_compatible=True)
    reopened = open_mpp_series(mpp, check_cancelled=lambda: None)
    for expected, actual in zip(corrected.frames, reopened, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.shift_xy == expected.shift_xy
    if mode == 'chain':
        assert reopened[1].alignment.correspondence == corrected.correspondence_diagnostics[1]
    else:
        config = reopened[0].alignment.manual_movie.graph_provenance.config
        assert config.weights_sha256 == graph.config.weights_sha256
        assert dict(config.backend_settings)['source_commit'] == '07e9c1401e71e9c556b1fda9d86d060af36ba176'
    plan = prepare_avi(tuple(item.image for item in restored.registration.frames), fps=7, codec='FFV1',
                       presentation=MoviePresentation(pixel_proportions=True, background=255))
    avi = save_avi(tmp_path / f'{mode}.avi', plan)
    fps, decoded = decode(avi)
    assert fps == 7 and len(decoded) == 3
    assert all(image.shape[:2] == plan.geometry.output_size[::-1] for image in decoded)
    assert all(np.ptp(image) > 0 for image in decoded)
