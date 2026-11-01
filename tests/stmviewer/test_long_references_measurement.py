"""Long relations at the real local model boundary, retaining all old measurements."""
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_registration import register_graph
from stmviewer.series import open_frame_series
from test_deep_registration import FIXTURE

pytest_plugins = ['test_deep_registration']


def six_frames():
    frame = open_frame_series([FIXTURE])[0]
    return tuple(replace(frame, source_frame_index=i) for i in range(6))


def test_extend_measures_only_planned_new_pairs_and_records_actual_provenance(local_model, monkeypatch):
    import kornia.feature
    from stmviewer.long_references import extend_graph
    frames = six_frames()
    options = DeepMatcherOptions(local_model, 'cpu')
    base = register_graph(frames, deep_options=options)
    forward = kornia.feature.LoFTR.forward
    calls = []
    def count_call(self, images):
        calls.append(1)
        return forward(self, images)
    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', count_call)
    result = extend_graph(frames, base, references=(5, 0, 0), target_start=0, target_end=5,
                          deep_options=options)
    assert len(calls) == result.measured_pairs == 3
    assert result.reused_pairs == len(base.edges)
    assert result.extension.base is base
    assert result.extension.references == (0, 5)
    assert result.extension.measurement_config.pair_code_version.startswith('sha256:')
    assert result.config == base.config
    assert result.positions is not None
    assert len(result.edges) == len(base.edges) + 3
    old = {(edge.i, edge.j): replace(edge, residual_xy=None) for edge in base.edges}
    assert {key: replace(edge, residual_xy=None) for edge in result.edges
            if (key := (edge.i, edge.j)) in old} == old
    np.testing.assert_array_equal(frames[0].data, open_frame_series([FIXTURE])[0].data)


@pytest.mark.parametrize('case', ['legacy', 'changed_model', 'unknown_code', 'changed_code', 'changed_pixels'])
def test_extension_checks_identity_and_accepts_only_audited_legacy_migration(local_model, monkeypatch, case):
    import kornia.feature
    from stmviewer.long_references import extend_graph
    frames = six_frames()
    base = register_graph(frames, deep_options=DeepMatcherOptions(local_model, 'cpu'))
    legacy = 'sha256:df02b29bb7e6c42ed6687999a5da783f55a1f9c40d4ce03402919c5cee959982'
    if case == 'legacy':
        base = replace(base, config=replace(base.config, code_version=legacy, pair_code_version=None))
    elif case == 'changed_model':
        base = replace(base, config=replace(base.config, weights_sha256='0' * 64))
    elif case == 'unknown_code':
        base = replace(base, config=replace(base.config, code_version='sha256:' + '0' * 64, pair_code_version=None))
    elif case == 'changed_code':
        base = replace(base, config=replace(base.config, pair_code_version='sha256:' + '0' * 64))
    else:
        frames = (replace(frames[0], data=frames[0].data + 1), *frames[1:])
    if case != 'legacy':
        def forbidden(self, images):
            pytest.fail('Changed baseline must fail before measuring any new pairs')
        monkeypatch.setattr(kornia.feature.LoFTR, 'forward', forbidden)
        with pytest.raises((ValueError, RuntimeError), match='Dalsze odniesienia'):
            extend_graph(frames, base, references=(0,), target_start=5, target_end=5)
    else:
        result = extend_graph(frames, base, references=(0,), target_start=5, target_end=5)
        assert result.measured_pairs == 1
        assert result.config.pair_code_version is None
        assert result.extension.measurement_config.pair_code_version.startswith('sha256:')
        assert result.extension.measurement_config.code_version != base.config.code_version


@pytest.mark.parametrize('failure', ['missing', 'error', 'cancel'])
def test_new_pair_failure_or_cancellation_preserves_baseline(local_model, monkeypatch, failure):
    import kornia.feature
    from threading import Event
    from stmviewer.long_references import extend_graph
    from stmviewer.registration import RegistrationError, RegistrationCancelled
    frames = six_frames()
    base = register_graph(frames, deep_options=DeepMatcherOptions(local_model, 'cpu'))
    saved_edges, saved_positions = base.edges, base.positions
    stopped = Event()
    forward = kornia.feature.LoFTR.forward
    def response(self, images):
        if failure == 'error':
            raise MemoryError('Controlled memory failure')
        output = forward(self, images)
        if failure == 'missing':
            return {key: value[:0] for key, value in output.items()}
        stopped.set()
        return output
    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', response)
    if failure == 'missing':
        result = extend_graph(frames, base, references=(0,), target_start=5, target_end=5)
        new = next(e for e in result.edges if (e.i, e.j) == (0, 5))
        assert new.status == 'missing' and new.reason
        np.testing.assert_allclose(result.positions, base.positions, atol=1e-12)
    else:
        with pytest.raises(RegistrationCancelled if failure == 'cancel' else RegistrationError):
            extend_graph(frames, base, references=(0,), target_start=5, target_end=5,
                         cancelled=stopped.is_set)
    assert base.edges is saved_edges and base.positions is saved_positions
    assert base.extension is None


def test_reverse_selected_reference_still_uses_correct_originals_and_j_onto_i_direction(local_model, monkeypatch):
    import kornia.feature
    from stmviewer.long_references import extend_graph
    frames = []
    for i, frame in enumerate(six_frames()):
        image = np.asarray(frame.data).copy()
        image = (image - image.min()) / (image.max() - image.min())
        image[0, :3] = (i / 8, 0, 1)
        frames.append(replace(frame, data=image))
    original_forward = kornia.feature.LoFTR.forward
    calls = []
    def tagged(self, images):
        i = round(float(images['image0'][0, 0, 0, 0]) * 8)
        j = round(float(images['image1'][0, 0, 0, 0]) * 8)
        calls.append((i, j))
        output = original_forward(self, images)
        points = output['keypoints0']
        output['keypoints1'] = points - points.new_tensor([2 * (j - i), -(j - i)])
        return output
    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', tagged)
    frames = tuple(frames)
    base = register_graph(frames, deep_options=DeepMatcherOptions(local_model, 'cpu'))
    calls.clear()
    result = extend_graph(frames, base, references=(5,), target_start=0, target_end=2)
    assert calls == [(0, 5), (1, 5)]
    assert {(e.i, e.j): e.shift_xy for e in result.edges if e.j - e.i > 3} == {
        (0, 5): (10., -5.), (1, 5): (8., -4.)}
    np.testing.assert_allclose(result.positions, [(2 * i, -i) for i in range(6)], atol=1e-12)
