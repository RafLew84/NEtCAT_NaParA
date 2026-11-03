"""Applied graph plus manual edits exports the active pixels through public APIs."""
import numpy as np
import pytest

from make_registration_fixtures import frames_with_data
from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.graph_provenance import graph_sources
from stmviewer.graph_registration import solve_graph
from stmviewer.graph_types import GraphConfig, GraphEdge
from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
from test_avi_export import decode
from test_manual_movie import corrected_trial


def marker_movie():
    samples = np.zeros((48, 64), dtype=np.float64)
    samples[8:24, 10:26] = 4
    samples[30:40, 45:55] = 4
    frames = frames_with_data(*(samples.copy() for _ in range(3)))
    config = GraphConfig(3, '/absent/model.ckpt', 'a' * 64, 'cpu', 'CPU', (), (), 'known-supplied')
    # Analytic LS is G=[(0,0),(2,0),(1,0)], distinct from raw d01=(3,0).
    graph = solve_graph(graph_sources(frames), (
        GraphEdge(0, 1, (3., 0.), 'ok'), GraphEdge(0, 2, (0., 0.), 'ok'),
        GraphEdge(1, 2, (0., 0.), 'ok'),
    ), config)
    return frames, graph


@pytest.mark.parametrize('codec', ['FFV1', 'MJPG'])
def test_applied_graph_manual_suffix_exports_active_pixels_without_diagnostics(tmp_path, codec):
    from stmviewer.graph_application import apply_graph_to_movie

    frames, graph = marker_movie()
    original_bytes = tuple(frame.data.tobytes() for frame in frames)
    applied = apply_graph_to_movie(frames, graph)
    np.testing.assert_allclose(movie_pair_trial(applied, 1).shift_xy, (2, 0), atol=1e-12)
    corrected = apply_movie_correction(applied, corrected_trial(applied, 1, 1, 0))
    assert corrected.graph_application == applied.graph_application
    np.testing.assert_allclose([f.shift_xy for f in corrected.frames], [(0, 0), (3, 0), (2, 0)], atol=1e-12)
    plan = prepare_avi(tuple(f.image for f in corrected.frames), fps=11, codec=codec,
                       presentation=MoviePresentation(pixel_proportions=True, background=128))
    path = save_avi(tmp_path / 'graph-corrected.avi', plan)
    fps, decoded = decode(path)
    assert fps == 11 and len(decoded) == 3
    for raster, shift in zip(decoded, (0, 3, 2), strict=True):
        expected = np.full((48, 68, 3), 128, dtype=np.uint8)
        expected[:, shift:shift + 64] = 0
        expected[8:24, 10 + shift:26 + shift] = 255
        expected[30:40, 45 + shift:55 + shift] = 255
        assert raster.shape == expected.shape
        error = np.abs(raster.astype(int) - expected.astype(int))
        assert (error.max() <= 1) if codec == 'FFV1' else (error.mean() < 5)
    assert tuple(frame.data.tobytes() for frame in frames) == original_bytes
