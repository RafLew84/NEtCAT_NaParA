"""Opt-in CPU comparison on identical known-motion and interference fixtures.

RoMa, EfficientLoFTR and MatchAnything use translation-consensus-v2. Historical Deep is a
complete-estimator comparison. Results are model support, never a physical
validation of STM drift. Inputs remain unchanged; reports live outside Git.
"""
import argparse
from dataclasses import asdict, replace
import gc
from hashlib import file_digest
import json
import os
from pathlib import Path
import platform
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deep-weights', type=Path)
    parser.add_argument('--methods', nargs='+',
                        choices=('roma_v2', 'efficient_loftr', 'matchanything_eloftr'),
                        default=['roma_v2', 'efficient_loftr'])
    parser.add_argument('--preset', choices=('turbo', 'fast', 'base', 'precise'), default='turbo')
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    from stmviewer.correspondence_types import CorrespondenceRefusal
    from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
    from stmviewer.efficient_matcher import default_efficient_options, load_efficient_backend
    from stmviewer.roma_matcher import default_roma_options, load_roma_backend
    from stmviewer.matchanything_matcher import default_matchanything_options, load_matchanything_backend
    from stmviewer.registration import estimate_confidence
    from stmviewer.series import open_frame_series
    import numpy as np
    import torch

    torch.set_num_threads(4)
    manifest = json.loads((args.directory / 'manifest.json').read_text())
    cpu = Path(__file__).resolve().parents[1] / 'fixtures/registration/cpu.mpp'
    known_cpu = {'adjacent_xy': [[2., -1.], [-3., 2.]],
                 'expected': 'Known translated image; this fixture uses periodic edge wrapping.'}
    names = ('translation', 'stationary-artifact', 'one-band', 'split-motion', 'periodic', 'noisy')
    paths = [cpu] + [args.directory / f'{name}.mpp' for name in names]
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'python': platform.python_version(), 'torch_parent': str(torch.__version__),
              'requested_device': 'cpu', 'threads_parent': 4,
              'sign': 'XY applied to moving original to match reference.',
              'limitations': 'Estimator comparison; no independent physical STM or GPU acceptance.',
              'methods': {}}

    def save():
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    methods = list(args.methods)
    if args.deep_weights is not None:
        methods.append('deep_matcher_translation')
    for method in methods:
        started = perf_counter()
        if method == 'roma_v2':
            backend = load_roma_backend(replace(default_roma_options(), device='cpu', preset=args.preset))
            device, provenance = backend.device, dict(backend.provenance)
        elif method == 'matchanything_eloftr':
            backend = load_matchanything_backend(replace(default_matchanything_options(), device='cpu'))
            device, provenance = backend.device, dict(backend.provenance)
        elif method == 'efficient_loftr':
            backend = load_efficient_backend(replace(default_efficient_options(), device='cpu'))
            device, provenance = backend.device, dict(backend.provenance)
        else:
            loaded = load_deep_backend(DeepMatcherOptions(args.deep_weights, 'cpu'))
            backend, device = loaded.backend, loaded.device
            with args.deep_weights.open('rb') as stream:
                weights_hash = file_digest(stream, 'sha256').hexdigest()
            provenance = {'weights_path': str(args.deep_weights), 'weights_sha256': weights_hash,
                          'estimator': 'historical Deep Matcher', 'config': asdict(backend.config)}
        record = {'device': device, 'provenance': provenance,
                  'load_seconds': perf_counter() - started, 'attempts': []}
        report['methods'][method] = record
        try:
            for path in paths:
                frames = open_frame_series([path])
                known = known_cpu if path == cpu else manifest['movies'][path.name]
                with path.open('rb') as stream:
                    digest = file_digest(stream, 'sha256').hexdigest()
                for i in range(1, len(frames)):
                    expected = known['adjacent_xy'][i - 1] if 'adjacent_xy' in known else known.get('scene_xy')
                    attempt = {'file': str(path), 'sha256': digest, 'pair_1based': [i, i + 1],
                               'shape_yx': list(frames[0].data.shape), 'known': known,
                               'expected_scene_xy': expected}
                    record['attempts'].append(attempt)
                    started = perf_counter()
                    try:
                        result = backend.estimate(frames[i - 1].data, frames[i].data, moving_frame_index=i)
                        status, score = estimate_confidence(method, result)
                        attempt.update(outcome='result', shift_xy=[float(v) for v in result.shift_xy],
                                       status=status, quality_score=score)
                        if expected is not None:
                            attempt['error_from_scene_xy'] = (np.asarray(result.shift_xy) - expected).tolist()
                    except CorrespondenceRefusal as error:
                        attempt.update(outcome='refusal', reason=str(error))
                    except Exception as error:
                        attempt.update(outcome='error', reason=f'{type(error).__name__}: {error}')
                    finally:
                        attempt['estimation_seconds'] = perf_counter() - started
                        diagnostic = getattr(backend, 'last_diagnostics', None)
                        if diagnostic is not None:
                            attempt['diagnostics'] = asdict(diagnostic)
                        attempt['worker_metrics'] = getattr(backend, 'last_metrics', {})
                        save()
                        print(method, path.name, f'{i}->{i + 1}', attempt['outcome'],
                              attempt.get('shift_xy', attempt.get('reason')), flush=True)
        finally:
            close = getattr(backend, 'close', None)
            if close is not None:
                close()
            del backend
            if method == 'deep_matcher_translation':
                del loaded
            gc.collect()
    import resource
    report['parent_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    save()


if __name__ == '__main__':
    main()
