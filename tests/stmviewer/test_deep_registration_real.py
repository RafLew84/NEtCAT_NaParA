"""Opt-in real checkpoint execution, distinct from controlled matcher integration."""

import os
from pathlib import Path
import urllib.request

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series


@pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_LOFTR_WEIGHTS'),
                    reason='Provide an existing local LoFTR outdoor checkpoint; never downloads it')
@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_real_local_loftr_checkpoint_produces_aligned_without_network(device, monkeypatch):
    import torch
    if device == 'cuda' and not torch.cuda.is_available():
        pytest.skip('CUDA unavailable in this Torch runtime')
    def forbidden(*args, **kwargs):
        pytest.fail('Real model attempted a download')
    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', forbidden)
    monkeypatch.setattr(torch.hub, 'download_url_to_file', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    frames = open_frame_series([Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'])
    result = register_series(frames, method='deep_matcher_translation', deep_options=DeepMatcherOptions(
        Path(os.environ['STMVIEWER_TEST_LOFTR_WEIGHTS']), device))
    assert result.device.startswith(device.upper())
    assert result.method == 'Deep Matcher'
    np.testing.assert_allclose([f.shift_xy for f in result.frames], [(0, 0), (2, -1), (-1, 1)], atol=0.75)
    assert all(f.valid_mask.any() for f in result.frames)
