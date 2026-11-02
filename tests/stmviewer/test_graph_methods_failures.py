"""Native computation failures must not turn into missing graph edges."""

import pytest
import skimage.registration

from test_graph_methods import FIXTURE
from stmviewer.graph_registration import register_graph
from stmviewer.registration import RegistrationError
from stmviewer.series import open_frame_series


@pytest.mark.parametrize('failure', [MemoryError('native allocation failed'),
                                     RuntimeError('native device failed'),
                                     (float('nan'), 0.), (0., 0., 0.)])
def test_tile_native_failure_aborts_instead_of_disappearing(monkeypatch, failure):
    import nanotrack.registration.tile_correlation as tile_module

    def fail(*args, **kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure, 0., 0.

    # Patch the external skimage function, including the shared backend's imported alias.
    monkeypatch.setattr(skimage.registration, 'phase_cross_correlation', fail)
    monkeypatch.setattr(tile_module, 'phase_cross_correlation', fail)
    with pytest.raises(RegistrationError):
        register_graph(open_frame_series([FIXTURE]), method='tile_correlation_ransac')
