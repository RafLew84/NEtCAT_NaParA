"""Registration boundary: local LoFTR loading and device reporting without downloads."""

from pathlib import Path

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series

FIXTURE = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


@pytest.fixture
def local_model(monkeypatch, tmp_path):
    """Controlled Kornia boundary; real Torch loading/tensors and NanoTrack consensus."""
    import torch
    import kornia.feature

    class ControlledLoFTR(torch.nn.Module):
        def __init__(self, pretrained):
            super().__init__()
            assert pretrained is None
            self.scale = torch.nn.Parameter(torch.ones(1))

        def forward(self, images):
            assert not self.training and not torch.is_grad_enabled()
            assert images['image0'].device == self.scale.device
            assert images['image0'].shape == (1, 1, 80, 80)
            assert images['image0'].min() == 0 and images['image0'].max() == 1
            points = torch.tensor([[10, 10], [20, 10], [30, 10], [40, 10],
                                   [10, 30], [20, 30], [30, 30], [40, 30]],
                                  dtype=torch.float32, device=self.scale.device)
            return {'keypoints0': points, 'keypoints1': points - points.new_tensor([2, -1]),
                    'confidence': torch.ones(8, device=self.scale.device)}

    def forbidden(*args, **kwargs):
        pytest.fail('A registration path attempted a download')

    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', forbidden)
    monkeypatch.setattr(torch.hub, 'download_url_to_file', forbidden)
    monkeypatch.setattr(kornia.feature, 'LoFTR', ControlledLoFTR)
    path = tmp_path / 'local.ckpt'
    torch.save({'state_dict': {'scale': torch.ones(1)}}, path)
    return path


def test_local_weights_create_complete_deep_result_without_network(local_model):
    frames = open_frame_series([FIXTURE])
    result = register_series(frames, method='deep_matcher_translation',
                             deep_options=DeepMatcherOptions(local_model, 'cpu'))
    assert result.method == 'Deep Matcher'
    assert result.device == 'CPU'
    assert [f.shift_xy for f in result.frames] == [(0, 0), (2, -1), (4, -2)]
    assert result.canvas_shape == (82, 84)
    assert all(f.status == 'ok' and f.valid_mask.any() for f in result.frames)
    assert result.without_frame(0).device == 'CPU'
    assert all(np.isnan(f.image.data[~f.valid_mask]).all() for f in result.frames)


@pytest.mark.parametrize('case,reason', [
    ('missing', 'Wskaż lokalny plik wag'), ('absent', 'Nie znaleziono'),
    ('corrupt', 'wag'), ('incompatible', 'wag'),
    ('cuda', 'CUDA'), ('device', 'urządzenie'),
])
def test_unusable_weights_or_device_fail_without_substitution(local_model, monkeypatch, tmp_path, case, reason):
    import torch
    from stmviewer.registration import RegistrationError
    weights, device = local_model, 'cpu'
    if case == 'missing':
        weights = None
    elif case == 'absent':
        weights = tmp_path / 'absent.ckpt'
    elif case == 'corrupt':
        local_model.write_bytes(b'not a checkpoint')
    elif case == 'incompatible':
        torch.save({'state_dict': {'other': torch.ones(2)}}, local_model)
    elif case == 'cuda':
        monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
        device = 'cuda'
    elif case == 'device':
        device = 'not-a-device'
    with pytest.raises(RegistrationError, match=reason):
        register_series(open_frame_series([FIXTURE]), method='deep_matcher_translation',
                        deep_options=DeepMatcherOptions(weights, device))


def test_cancel_during_model_preparation_discards_the_attempt(local_model):
    from threading import Event
    from stmviewer.registration import RegistrationCancelled
    stopped = Event()
    def progress(done, total, text):
        if 'Wczytywanie wag' in text:
            stopped.set()
    with pytest.raises(RegistrationCancelled):
        register_series(open_frame_series([FIXTURE]), method='deep_matcher_translation',
                        deep_options=DeepMatcherOptions(local_model, 'cpu'),
                        progress=progress, cancelled=stopped.is_set)


def test_auto_reports_cpu_when_cuda_is_unavailable(local_model, monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    result = register_series(open_frame_series([FIXTURE]), method='deep_matcher_translation',
                             deep_options=DeepMatcherOptions(local_model, 'auto'))
    assert result.device == 'CPU'


@pytest.mark.parametrize('device', ['cuda', 'auto'])
def test_cuda_execution_error_does_not_silently_fall_back_to_cpu(local_model, monkeypatch, device):
    import torch
    from stmviewer.registration import RegistrationError
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'current_device', lambda: 0)
    real_ones = torch.ones
    def fail_cuda(*args, **kwargs):
        if str(kwargs.get('device', '')).startswith('cuda'):
            raise RuntimeError('CUDA out of memory (controlled)')
        return real_ones(*args, **kwargs)
    monkeypatch.setattr(torch, 'ones', fail_cuda)
    with pytest.raises(RegistrationError, match='CUDA out of memory'):
        register_series(open_frame_series([FIXTURE]), method='deep_matcher_translation',
                        deep_options=DeepMatcherOptions(local_model, device))


@pytest.mark.parametrize('missing', ['torch', 'kornia.feature'])
def test_broken_optional_library_reports_its_reason(local_model, monkeypatch, missing):
    import builtins
    from stmviewer.registration import RegistrationError
    original = builtins.__import__
    def without(name, *args, **kwargs):
        if name == missing:
            raise ImportError('Broken library: ' + missing)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without)
    with pytest.raises(RegistrationError, match='Broken library: ' + missing):
        register_series(open_frame_series([FIXTURE]), method='deep_matcher_translation',
                        deep_options=DeepMatcherOptions(local_model, 'cpu'))
