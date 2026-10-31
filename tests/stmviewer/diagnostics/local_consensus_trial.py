"""Opt-in REG-05 probes with local weights and the public pair/series APIs.

Full-series attempts stop at the first refused pair; no fallback or skipped
frames. Pair probes are independent and retain local evidence after refusal.
Outputs are local research artifacts, not a verdict on physical STM drift.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import urllib.request


METHODS = ['deep_matcher_translation', 'deep_local_consensus']


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def peak_process_rss_bytes():
    """Process-lifetime high-water RSS, not an isolated peak of this attempt."""
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == 'darwin' else value * 1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, help='New local directory; existing directories are refused')
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--pair', action='append', type=int,
                        help='1-based MOVING position after dropping; repeat for independent pair trials')
    parser.add_argument('--method', action='append', choices=METHODS)
    parser.add_argument('--export', action='store_true', help='Save complete full-series aligned MPP+metadata')
    args = parser.parse_args()
    if args.drop_first < 0 or (args.pair and min(args.pair) < 2):
        parser.error('Nonnegative --drop-first and --pair >= 2 required.')
    if args.export and args.pair:
        parser.error('--export requires a full-series attempt, without --pair.')
    args.output.mkdir(parents=True, exist_ok=False)

    # Lazy imports let --help work without model libraries or application setup.
    import numpy as np
    import torch
    import kornia

    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.local_consensus import LocalConsensusError
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import RegistrationCancelled, register_series
    from stmviewer.series import open_frame_series

    def no_download(*values, **options):
        raise RuntimeError('REG-05 diagnostics forbids downloading models or data.')

    torch.hub.load_state_dict_from_url = no_download
    torch.hub.download_url_to_file = no_download
    urllib.request.urlopen = no_download
    torch.set_num_threads(4)
    frames = open_frame_series([args.source])[args.drop_first:]
    if len(frames) < 2 or (args.pair and max(args.pair) > len(frames)):
        raise ValueError('Requested series/pair is empty or out of range.')
    report = dict(
        source=str(args.source.resolve()), source_sha256=digest(args.source),
        weights=str(args.weights.resolve()), weights_sha256=digest(args.weights),
        requested_device=args.device, python=platform.python_version(),
        torch=str(torch.__version__), kornia=str(kornia.__version__),
        frame_count=len(frames), shape_yx=frames[0].data.shape,
        source_frames_1based=[f.source_frame_index + 1 if f.source_frame_index is not None else None
                             for f in frames],
        drop_first=args.drop_first, mode='pairs' if args.pair else 'full-series',
        note='Local evidence is estimator support, not independent physical-drift or visual-quality validation.',
        resources_note=('seconds includes model loading, estimation and rendering; export_seconds is separate. '
                        'RSS is process-lifetime high-water, CUDA peaks are Torch allocations/reservations, '
                        'not total device usage or proof of operation on 8 GB VRAM.'),
        attempts=[],
    )

    def save():
        (args.output / 'report.json').write_text(json.dumps(
            report, indent=2, default=str, allow_nan=False) + '\n', encoding='utf-8')

    save()
    options = DeepMatcherOptions(args.weights, args.device)
    stopped = False
    for method in args.method or METHODS:
        for moving in args.pair or [None]:
            attempt = dict(method=method, moving_position=moving, complete=False,
                           cancelled=False, error=None, export_complete=None)
            report['attempts'].append(attempt)
            if moving is not None:
                pair = frames[moving - 2:moving]
                attempt['source_pair_1based'] = [
                    f.source_frame_index + 1 if f.source_frame_index is not None else None for f in pair]
            save()
            previous = 0
            started = perf_counter()
            has_cuda = args.device == 'cuda' and torch.cuda.is_available()

            def progress(done, total, text):
                nonlocal previous
                attempt['last_progress'] = [done, total, text]
                if done >= previous + 50 or done == total:
                    previous = done
                    print(f'{method} {done}/{total}: {text}', flush=True)
                    save()

            try:
                if has_cuda:
                    torch.cuda.reset_peak_memory_stats()
                if moving is None:
                    result = register_series(frames, method=method, deep_options=options, progress=progress)
                    attempt.update(complete=True, label=result.method, device=result.device,
                                   canvas_shape=result.canvas_shape,
                                   cumulative_xy=[f.shift_xy for f in result.frames],
                                   statuses=[f.status for f in result.frames],
                                   local_diagnostics=[asdict(d) if d is not None else None
                                                      for d in result.local_diagnostics])
                else:
                    trial = estimate_pair(*pair, method=method, deep_options=options,
                                          progress=lambda text: attempt.update(last_stage=text))
                    attempt.update(complete=True, trial=asdict(trial))
                if has_cuda:
                    torch.cuda.synchronize()
                attempt['seconds'] = perf_counter() - started
                if args.export:
                    path = args.output / f'{method}-aligned.mpp'
                    export_started = perf_counter()
                    try:
                        save_aligned_mpp(path, result)
                        attempt.update(mpp=str(path), export_complete=True)
                    except Exception as error:
                        attempt.update(export_complete=False,
                                       export_error=f'{type(error).__name__}: {error}')
                    finally:
                        attempt['export_seconds'] = perf_counter() - export_started
            except LocalConsensusError as error:
                attempt.update(complete=False, error=f'{type(error).__name__}: {error}',
                               refused_local_diagnostics=asdict(error.diagnostics))
            except (RegistrationCancelled, KeyboardInterrupt) as error:
                attempt.update(complete=False, cancelled=True,
                               error=f'{type(error).__name__}: {error}')
                stopped = True
            except Exception as error:
                attempt.update(complete=False, error=f'{type(error).__name__}: {error}')
            finally:
                attempt.setdefault('seconds', perf_counter() - started)
                attempt['peak_process_rss_bytes'] = peak_process_rss_bytes()
                if has_cuda:
                    try:
                        attempt['peak_cuda_allocated_bytes'] = torch.cuda.max_memory_allocated()
                        attempt['peak_cuda_reserved_bytes'] = torch.cuda.max_memory_reserved()
                    except Exception as error:
                        attempt['resource_error'] = f'{type(error).__name__}: {error}'
                save()
                print(json.dumps({key: attempt[key] for key in (
                    'method', 'moving_position', 'complete', 'cancelled', 'seconds', 'error',
                    'export_complete')}, ensure_ascii=False), flush=True)
            if stopped:
                break
        if stopped:
            break
    report['sources_finite'] = all(np.isfinite(f.data).all() for f in frames)
    save()
    return 0 if all(a['complete'] and a['export_complete'] is not False for a in report['attempts']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
