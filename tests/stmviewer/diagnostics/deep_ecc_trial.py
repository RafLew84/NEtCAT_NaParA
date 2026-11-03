"""Opt-in real-model REG-04 probes through the application's public interfaces.

Full-series attempts stop at the first failed pair, without fallback. Pair probes
are independent trials and report each failure. No downloads or source edits.
Large MPP outputs remain local and require --export explicitly.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from time import perf_counter
import urllib.request

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, help='New local output directory')
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--pair', action='append', type=int,
                        help='1-based MOVING position after dropping; repeat for independent pairs')
    parser.add_argument('--method', action='append',
                        choices=['deep_matcher_translation', 'deep_matcher_ecc'])
    parser.add_argument('--export', action='store_true', help='Save complete aligned as MPP+metadata')
    args = parser.parse_args()
    if args.drop_first < 0 or (args.pair and min(args.pair) < 2):
        parser.error('Nonnegative drop-first and pair >= 2 required.')
    args.output.mkdir(parents=True, exist_ok=False)
    import torch

    def no_download(*values, **options):
        raise RuntimeError('REG-04 diagnostics forbids downloading models or data.')

    torch.hub.load_state_dict_from_url = no_download
    torch.hub.download_url_to_file = no_download
    urllib.request.urlopen = no_download
    torch.set_num_threads(4)
    frames = open_frame_series([args.source])[args.drop_first:]
    if len(frames) < 2 or (args.pair and max(args.pair) > len(frames)):
        raise ValueError('Requested series/pair is empty or out of range.')
    with args.source.open('rb') as stream:
        source_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    with args.weights.open('rb') as stream:
        weights_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = dict(source=str(args.source.resolve()), source_sha256=source_digest,
                  weights=str(args.weights.resolve()), weights_sha256=weights_digest,
                  requested_device=args.device, torch=str(torch.__version__),
                  frame_count=len(frames), shape_yx=frames[0].data.shape,
                  drop_first=args.drop_first, mode='pairs' if args.pair else 'full-series',
                  note='Backend diagnostics are not independent physical-drift or visual-quality validation.',
                  attempts=[])

    def save():
        (args.output / 'report.json').write_text(json.dumps(
            report, indent=2, default=str, allow_nan=False) + '\n', encoding='utf-8')

    options = DeepMatcherOptions(args.weights, args.device)
    for method in args.method or ['deep_matcher_translation', 'deep_matcher_ecc']:
        for moving in args.pair or [None]:
            attempt = dict(method=method, moving_position=moving)
            report['attempts'].append(attempt)
            if moving is not None:
                pair = frames[moving - 2:moving]
                attempt['source_pair_1based'] = [
                    f.source_frame_index + 1 if f.source_frame_index is not None else None for f in pair]
            save()
            started = perf_counter()
            previous = 0
            if args.device == 'cuda':
                torch.cuda.reset_peak_memory_stats()

            def progress(done, total, text):
                nonlocal previous
                attempt['last_progress'] = [done, total, text]
                if done >= previous + 50 or done == total:
                    previous = done
                    print(f'{method} {done}/{total}: {text}', flush=True)
                    save()

            try:
                if moving is None:
                    result = register_series(frames, method=method, deep_options=options, progress=progress)
                    attempt.update(complete=True, label=result.method, device=result.device,
                                   canvas_shape=result.canvas_shape,
                                   cumulative_xy=[f.shift_xy for f in result.frames],
                                   statuses=[f.status for f in result.frames],
                                   pair_diagnostics=[asdict(d) if d is not None else None
                                                     for d in result.pair_diagnostics])
                    if args.export:
                        path = args.output / f'{method}-aligned.mpp'
                        save_aligned_mpp(path, result)
                        attempt['mpp'] = str(path)
                else:
                    trial = estimate_pair(*pair, method=method, deep_options=options)
                    attempt.update(complete=True, trial=asdict(trial))
            except Exception as error:
                attempt.update(complete=False, error=f'{type(error).__name__}: {error}')
            attempt['seconds'] = perf_counter() - started
            if args.device == 'cuda':
                attempt['peak_cuda_allocated_bytes'] = torch.cuda.max_memory_allocated()
            save()
            print(json.dumps({k: attempt[k] for k in ('method', 'moving_position', 'complete', 'seconds')}
                             | {'error': attempt.get('error')}, ensure_ascii=False), flush=True)
    assert all(np.isfinite(f.data).all() for f in frames), 'Unexpected source NaN/Inf in these probes.'


if __name__ == '__main__':
    main()
