"""Opt-in CPU comparison of EfficientLoFTR and historical Deep on known fixtures.

Generate inputs first with make_local_consensus_fixtures.py --output DIR.
The same original pairs and the existing estimators are used unchanged.
This checks complete estimators, not model-only quality or physical STM drift.
"""

import argparse
from dataclasses import asdict, replace
import gc
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--deep-weights', type=Path, required=True)
    args = parser.parse_args()
    from stmviewer.correspondence_types import CorrespondenceRefusal
    from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
    from stmviewer.efficient_matcher import default_efficient_options, load_efficient_backend
    from stmviewer.series import open_frame_series
    import torch
    import numpy as np

    torch.set_num_threads(4)
    manifest = json.loads((args.directory / 'manifest.json').read_text())
    cpu = Path(__file__).resolve().parents[1] / 'fixtures/registration/cpu.mpp'
    known_cpu = {'adjacent_xy': [[2., -1.], [-3., 2.]],
                 'expected': 'Known translated image; initial fixture uses periodic edge wrapping.'}
    paths = [cpu] + [args.directory / f'{name}.mpp' for name in
                    ('translation', 'stationary-artifact', 'one-band', 'split-motion', 'periodic')]
    report = {'python': platform.python_version(), 'torch': str(torch.__version__),
              'requested_device': 'cpu', 'sign': 'XY applied to moving original to match reference.',
              'limitations': 'Complete estimator comparison; no independent STM quality or GPU acceptance.',
              'methods': {}}

    def save():
        (args.directory / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    for method in ('efficient_loftr', 'deep_matcher_translation'):
        started = perf_counter()
        if method == 'efficient_loftr':
            backend = load_efficient_backend(replace(default_efficient_options(), device='cpu'))
            device = backend.device
            provenance = dict(backend.provenance)
        else:
            loaded = load_deep_backend(DeepMatcherOptions(args.deep_weights, 'cpu'))
            backend, device = loaded.backend, loaded.device
            with args.deep_weights.open('rb') as stream:
                weights_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
            provenance = {'weights_path': str(args.deep_weights), 'weights_sha256': weights_hash,
                          'estimator': 'historical Deep Matcher', 'config': asdict(backend.config)}
        records = {'device': device, 'provenance': provenance,
                   'load_seconds': perf_counter() - started, 'attempts': []}
        report['methods'][method] = records
        try:
            for path in paths:
                frames = open_frame_series([path])
                known = known_cpu if path == cpu else manifest['movies'][path.name]
                for i in range(1, len(frames)):
                    expected = known['adjacent_xy'][i - 1] if 'adjacent_xy' in known else known.get('scene_xy')
                    record = {'file': str(path), 'pair_1based': [i, i + 1],
                              'shape_yx': list(frames[0].data.shape), 'known': known,
                              'expected_scene_xy': expected}
                    records['attempts'].append(record)
                    started = perf_counter()
                    try:
                        result = backend.estimate(frames[i - 1].data, frames[i].data, moving_frame_index=i)
                        record.update(outcome='result', shift_xy=[float(v) for v in result.shift_xy],
                                      status=result.status, quality_score=result.quality_score)
                        if expected is not None:
                            record['error_from_scene_xy'] = (np.asarray(result.shift_xy) - expected).tolist()
                    except CorrespondenceRefusal as error:
                        record.update(outcome='refusal', reason=str(error))
                    except Exception as error:
                        record.update(outcome='error', reason=f'{type(error).__name__}: {error}')
                    finally:
                        record['estimation_seconds'] = perf_counter() - started
                        if method == 'efficient_loftr' and backend.last_diagnostics is not None:
                            record['diagnostics'] = asdict(backend.last_diagnostics)
                        save()
                        print(method, path.name, f'{i}->{i+1}', record['outcome'],
                              record.get('shift_xy', record.get('reason')), flush=True)
        finally:
            if method == 'efficient_loftr':
                backend.close()
            del backend
            if method == 'deep_matcher_translation':
                del loaded
            gc.collect()
    try:
        import resource
        report['process_peak_rss_bytes'] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                                               (1 if sys.platform == 'darwin' else 1024))
    except ImportError:
        report['process_peak_rss_bytes'] = None
    save()


if __name__ == '__main__':
    main()
