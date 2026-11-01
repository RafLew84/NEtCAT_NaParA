"""Original frames → current Deep estimates → graph, at the native model boundary."""

from pathlib import Path

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_registration import register_graph
from stmviewer.series import open_frame_series

FIXTURE = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


@pytest.fixture
def native_model(monkeypatch, tmp_path):
    import torch
    import kornia.feature

    state = {'loads': 0, 'calls': 0, 'responses': []}

    class ControlledLoFTR(torch.nn.Module):
        def __init__(self, pretrained):
            super().__init__()
            assert pretrained is None
            state['loads'] += 1
            self.scale = torch.nn.Parameter(torch.ones(1))

        def forward(self, images):
            assert not self.training and not torch.is_grad_enabled()
            assert images['image0'].shape == (1, 1, 80, 80)
            assert images['image0'].min() == 0 and images['image0'].max() == 1
            state['calls'] += 1
            response = state['responses'].pop(0) if state['responses'] else (2., -1.)
            if isinstance(response, Exception):
                raise response
            points = torch.tensor([[10, 10], [20, 10], [30, 10], [40, 10],
                                   [10, 30], [20, 30], [30, 30], [40, 30]], dtype=torch.float32)
            if response is None:
                points = points[:2]
                response = (0., 0.)
            return {'keypoints0': points, 'keypoints1': points - points.new_tensor(response),
                    'confidence': torch.ones(len(points))}

    def forbidden(*args, **kwargs):
        pytest.fail('Graph calculation attempted a model download')

    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', forbidden)
    monkeypatch.setattr(torch.hub, 'download_url_to_file', forbidden)
    monkeypatch.setattr(kornia.feature, 'LoFTR', ControlledLoFTR)
    path = tmp_path / 'local.ckpt'
    torch.save({'state_dict': {'scale': torch.ones(1)}}, path)
    return path, state


def test_original_series_matches_each_pair_once_with_current_deep_and_no_mutation(native_model):
    weights, model = native_model
    model['responses'] = [(3., -2.), (-2., 1.), (-5., 3.)]
    frames = open_frame_series([FIXTURE])
    originals = [f.data.copy() for f in frames]
    result = register_graph(frames, window=3, deep_options=DeepMatcherOptions(weights, 'cpu'))
    assert model['loads'] == 1 and model['calls'] == 3
    assert [(e.i, e.j) for e in result.edges] == [(0, 1), (0, 2), (1, 2)]
    np.testing.assert_allclose(result.positions, ((0., 0.), (3., -2.), (-2., 1.)), atol=1e-12)
    assert result.config.device == 'CPU'
    assert result.config.weights_path == str(weights)
    assert len(result.config.weights_sha256) == 64
    assert result.measured_pairs == 3 and result.reused_pairs == 0
    for original, frame in zip(originals, frames, strict=True):
        np.testing.assert_array_equal(original, frame.data)


def test_local_insufficient_matches_are_retained_as_missing_edges(native_model):
    weights, model = native_model
    model['responses'] = [None, (-2., 1.), (-5., 3.)]
    result = register_graph(open_frame_series([FIXTURE]), deep_options=DeepMatcherOptions(weights, 'cpu'))
    assert result.edges[0].shift_xy is None
    assert result.edges[0].status == 'missing'
    assert 'Only 2 feature matches' in result.edges[0].reason
    np.testing.assert_allclose(result.positions, ((0, 0), (3, -2), (-2, 1)), atol=1e-12)
    assert result.chain_positions is None


@pytest.mark.parametrize('failure', [RuntimeError('CUDA out of memory'), MemoryError('no memory'),
                                    OSError('device failure'), ValueError('model execution failed')])
def test_resource_system_and_model_errors_abort_whole_attempt(native_model, failure):
    from stmviewer.registration import RegistrationError
    weights, model = native_model
    frames = open_frame_series([FIXTURE])
    previous = register_graph(frames, deep_options=DeepMatcherOptions(weights, 'cpu'))
    old_edges = previous.edges
    model['responses'] = [(1., 0.), failure]
    with pytest.raises(RegistrationError, match=str(failure)):
        register_graph(frames, deep_options=DeepMatcherOptions(weights, 'cpu'))
    assert previous.edges == old_edges


def test_window_expansion_reuses_common_measurements_including_local_refusals(native_model):
    from dataclasses import replace
    weights, model = native_model
    originals = open_frame_series([FIXTURE])
    frames = tuple(replace(originals[i % 3], source_frame_index=i) for i in range(6))
    model['responses'] = [None]
    first = register_graph(frames, window=3, deep_options=DeepMatcherOptions(weights, 'cpu'))
    expanded = register_graph(frames, window=5, deep_options=DeepMatcherOptions(weights, 'cpu'), previous=first)
    assert len(first.edges) == 12 and len(expanded.edges) == 15
    assert model['calls'] == 15 and model['loads'] == 2
    assert expanded.measured_pairs == 3 and expanded.reused_pairs == 12
    assert expanded.edges[0].status == 'missing'
    assert [(e.i, e.j) for e in expanded.edges] == [
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 2), (1, 3), (1, 4),
        (1, 5), (2, 3), (2, 4), (2, 5), (3, 4), (3, 5), (4, 5)]


@pytest.mark.parametrize('change', ['pixels', 'source', 'index', 'weights', 'code', 'library', 'requested_device'])
def test_cache_never_reuses_different_sources_content_or_model_configuration(native_model, change):
    from dataclasses import replace
    import torch
    weights, model = native_model
    frames = open_frame_series([FIXTURE])
    previous = register_graph(frames, deep_options=DeepMatcherOptions(weights, 'cpu'))
    if change == 'pixels':
        pixels = frames[0].data.copy()
        pixels[0, 0] += .1
        frames = (replace(frames[0], data=pixels),) + frames[1:]
    elif change == 'source':
        frames = (replace(frames[0], source=Path('different.mpp')),) + frames[1:]
    elif change == 'index':
        frames = (replace(frames[0], source_frame_index=90),) + frames[1:]
    elif change == 'weights':
        torch.save({'state_dict': {'scale': torch.ones(1) * 2}}, weights)
    elif change == 'code':
        previous = replace(previous, config=replace(previous.config, code_version='previous-version'))
    elif change == 'library':
        previous = replace(previous, config=replace(previous.config, libraries=(('kornia', 'old'),)))
    else:
        previous = replace(previous, config=replace(previous.config, requested_device='auto'))
    result = register_graph(frames, deep_options=DeepMatcherOptions(weights, 'cpu'), previous=previous)
    assert result.reused_pairs == 0 and result.measured_pairs == 3
    assert model['calls'] == 6


@pytest.mark.parametrize('stage', ['Sprawdzanie oryginalnych', 'Wczytywanie wag', 'pair', 'Wyznaczanie wspólnych'])
def test_cancelled_attempt_never_returns_a_partial_graph(native_model, stage):
    from threading import Event
    from stmviewer.registration import RegistrationCancelled
    weights, model = native_model
    stopped = Event()
    def progress(done, total, text):
        if stage in text or (stage == 'pair' and done == 1):
            stopped.set()
    with pytest.raises(RegistrationCancelled):
        register_graph(open_frame_series([FIXTURE]), deep_options=DeepMatcherOptions(weights, 'cpu'),
                       progress=progress, cancelled=stopped.is_set)
    assert model['calls'] <= 3


def test_malformed_native_model_output_is_fatal_not_missing(native_model):
    from stmviewer.registration import RegistrationError
    weights, model = native_model
    model['responses'] = [(float('nan'), 0.)]
    with pytest.raises(RegistrationError, match='finite'):
        register_graph(open_frame_series([FIXTURE]), deep_options=DeepMatcherOptions(weights, 'cpu'))


def test_missing_checkpoint_never_uses_previous_cached_measurements(native_model):
    from stmviewer.registration import RegistrationError
    weights, _ = native_model
    frames = open_frame_series([FIXTURE])
    previous = register_graph(frames, deep_options=DeepMatcherOptions(weights, 'cpu'))
    weights.unlink()
    with pytest.raises(RegistrationError, match='Nie znaleziono'):
        register_graph(frames, deep_options=DeepMatcherOptions(weights, 'cpu'), previous=previous)
