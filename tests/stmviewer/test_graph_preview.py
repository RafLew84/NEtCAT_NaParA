"""On-demand graph movie rasters share geometry and original contrast."""
from dataclasses import replace

import numpy as np
import pytest

from test_pair_comparison import frame
from stmviewer.graph_preview import GraphMoviePreview


def test_variants_share_canvas_brightness_and_signed_translation():
    first = frame([[0, 25, 50], [75, 100, 25]])
    second = replace(first, source_frame_index=1)
    preview = GraphMoviePreview((first, second), {
        'graph': ((0, 0), (-1, 1)), 'chain': ((0, 0), (2, -1)),
    })
    graph = preview.render(1, 'graph')
    chain = preview.render(1, 'chain')
    assert preview.canvas_shape == (4, 6)
    assert graph.rgba.shape == chain.rgba.shape == (4, 6, 4)
    np.testing.assert_array_equal(graph.rgba[2:, :3, 0], [[0, 63, 127], [191, 255, 63]])
    np.testing.assert_array_equal(chain.rgba[:2, 3:, 0], graph.rgba[2:, :3, 0])
    assert np.count_nonzero(graph.rgba[:, :, 3]) == 6
    assert np.count_nonzero(chain.rgba[:, :, 3]) == 6
    np.testing.assert_array_equal(first.data, [[0, 25, 50], [75, 100, 25]])
    assert not graph.rgba.flags.writeable


def test_fractional_shift_keeps_original_levels_and_physical_aspect():
    first = replace(frame([[0, 50, 100], [0, 50, 100]]), size_x_nm=6, size_y_nm=2)
    preview = GraphMoviePreview((first, first), {
        'graph': ((0, 0), (.5, 0)), 'chain': ((0, 0), (0, 0)),
    })
    shifted = preview.render(1, 'graph')
    np.testing.assert_array_equal(shifted.rgba[:, 1:3, 0], [[63, 191], [63, 191]])
    assert shifted.aspect == 4  # Four output pixels, with X scale twice Y.
    assert preview.render(1, 'chain', pixel_proportions=True).aspect == 2
    assert preview.render(1, 'graph', gamma=2).rgba[0, 1, 0] > shifted.rgba[0, 1, 0]
    assert not shifted.rgba[:, 0, 3].any()


def test_incompatible_positions_and_excessive_canvas_are_refused():
    first = frame(np.zeros((4, 4)))
    with pytest.raises(ValueError, match='przesuni'):
        GraphMoviePreview((first, first), {'graph': ((0, 0),)})
    with pytest.raises(ValueError, match='duży'):
        GraphMoviePreview((first, first), {'graph': ((0, 0), (1e10, 0))})
