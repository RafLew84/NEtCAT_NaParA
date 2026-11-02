"""AKAZE uses the same public measurement in a pair and an adjacent movie."""
from dataclasses import replace
from pathlib import Path
import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import register_series
from test_akaze_backend import texture


def frames():
    base = texture()
    return tuple(ImageFrame(Path('akaze-known.mpp'), np.roll(base, (y, x), (0, 1)), {},
                            'Topography', 'nm', 288., 192., 0., 0., None, None, None,
                            source_frame_index=i, measurement_time_s=float(i))
                 for i, (x, y) in enumerate(((0, 0), (7, -5), (-3, 4))))


def test_pair_and_movie_share_original_pixel_measurement():
    originals = frames()
    before = tuple(f.data.tobytes() for f in originals)
    pair = estimate_pair(originals[0], originals[1], method='akaze')
    movie = register_series(originals, method='akaze')
    np.testing.assert_allclose([f.shift_xy for f in movie.frames],
                               [(0, 0), (-7, 5), (3, -4)], atol=.3)
    assert movie.method == pair.label == 'AKAZE'
    assert pair.device == movie.device == 'CPU'
    assert pair.quality_score is None
    assert pair.correspondence == movie.correspondence_diagnostics[1]
    assert tuple(f.data.tobytes() for f in originals) == before


def test_graph_has_same_measurements_and_local_refusals():
    from stmviewer.graph_registration import register_graph
    from stmviewer.robust_graph import solve_robust_graph
    originals = frames()
    graph = register_graph(originals, method='akaze')
    pair = estimate_pair(originals[0], originals[1], method='akaze')
    assert graph.config.method == 'akaze'
    assert graph.config.weights_path is None
    assert graph.config.requested_device == 'cpu'
    assert dict(graph.config.backend_settings)['adapter_version'] == 'akaze-mldb-crosscheck-v1'
    assert graph.edges[0].correspondence_diagnostics == pair.correspondence
    assert graph.edges[0].quality_score is None
    np.testing.assert_allclose(graph.positions, [(0,0),(-7,5),(3,-4)], atol=.3)
    robust = solve_robust_graph(graph)
    np.testing.assert_allclose(robust.positions, graph.positions, atol=.1)
    blank = replace(originals[1], data=np.ones_like(originals[1].data))
    incomplete = register_graph((originals[0], blank, originals[2]), method='akaze')
    assert incomplete.positions is None
    assert len(incomplete.components) == 2
    assert [e.shift_xy is None for e in incomplete.edges] == [True, False, True]
    assert incomplete.edges[0].correspondence_diagnostics.final_shift_xy is None

def test_real_akaze_pair_movie_graph_need_no_torch_or_network(tmp_path):
    import os
    import subprocess
    import sys
    script = """
import socket, sys
for name in ('torch', 'kornia', 'torchvision', 'lightglue'):
    sys.modules[name] = None
def blocked(*args, **kwargs):
    raise AssertionError('AKAZE attempted a network connection')
socket.socket.connect = blocked
socket.create_connection = blocked
from test_akaze_integration import frames
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import register_series
from stmviewer.graph_registration import register_graph
images = frames()
assert estimate_pair(images[0], images[1], method='akaze').device == 'CPU'
assert register_series(images, method='akaze').device == 'CPU'
assert register_graph(images, method='akaze').positions is not None
assert all(sys.modules[name] is None for name in ('torch','kornia','torchvision','lightglue'))
"""
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=os.pathsep.join((str(root), str(root/'tests/stmviewer'))))
    subprocess.run([sys.executable, '-c', script], env=env, check=True, capture_output=True, text=True)
