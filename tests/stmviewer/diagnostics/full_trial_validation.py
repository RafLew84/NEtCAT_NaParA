"""Opt-in REG-07 acceptance on real sources; outputs remain local.

Run each model in a fresh process for comparable lifetime peak RSS. The compare
subcommand blocks torch/kornia imports and reconstructs both complete movies
frame by frame; it does not load weights or create aligned stacks. None of these
checks determines the physical correctness of STM drift or replaces GUI/VLC.
"""

import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
from time import perf_counter

import numpy as np


METHODS = ('deep_matcher_translation', 'deep_matcher_ecc', 'deep_local_consensus')


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def peak_rss():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == 'darwin' else rss * 1024)


def write_report(path, report):
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
                    encoding='utf-8')


def shifts(document):
    payload = document.payload
    if payload['kind'] != 'series' or payload['outcome'] != 'complete':
        raise ValueError('Comparison requires a complete series, not a partial diagnostic.')
    return tuple(tuple(record['cumulative_xy']) for record in payload['records'])


def roundtrip_document(path, document, frames):
    from stmviewer.trial_document import load_trial, save_trial

    start = perf_counter()
    saved = save_trial(path, document, frames)
    save_seconds = perf_counter() - start
    start = perf_counter()
    loaded = load_trial(path, frames)
    assert loaded == saved
    return loaded, {'result': 'PASS', 'save_seconds': save_seconds,
                    'load_seconds': perf_counter() - start, 'bytes': path.stat().st_size}


def verify_render(document, frames, registration):
    from stmviewer.trial_comparison import FullTrialComparison

    start = perf_counter()
    xy = shifts(document)
    comparison = FullTrialComparison(frames, xy, xy)
    assert comparison.canvas_shape == registration.canvas_shape
    for index, aligned in enumerate(registration.frames):
        image = comparison.render(index, 'A')
        np.testing.assert_array_equal(image.data, aligned.image.data)
        assert comparison.original_rect(index, 'A') == aligned.original_rect
        assert not image.data.flags.writeable
    return {'result': 'PASS', 'frames': len(frames), 'seconds': perf_counter() - start,
            'canvas_shape': comparison.canvas_shape}


def verify_manual(output, frames, registration):
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.trial_capture import from_pair, from_registration, pair_from_document

    first, second = (29, 35) if len(frames) > 100 else (15, 55)
    if len(frames) <= second:
        first, second = 1, 2
    baseline_xy = [frame.shift_xy for frame in registration.frames]
    corrected = registration
    for index, step in ((first, (1, 0)), (second, (0, -1))):
        draft = ManualPairDraft(frames[index - 1], frames[index],
                                start=movie_pair_trial(corrected, index))
        draft.nudge(*step)
        pair = draft.apply()
        if index == first:
            loaded, pair_report = roundtrip_document(
                output / 'manual-pair.stmtrial.json', from_pair(pair, frames), frames)
            restored = pair_from_document(loaded, frames)
            assert restored.shift_xy == pair.shift_xy
            assert restored.manual == pair.manual
            assert restored.quality_score is None and restored.status == 'manual'
        corrected = apply_movie_correction(corrected, pair)
    assert len(corrected.corrections) == 2
    for index, frame in enumerate(corrected.frames):
        x, y = baseline_xy[index]
        expected = (x + (1 if index >= first else 0), y - (1 if index >= second else 0))
        np.testing.assert_allclose(frame.shift_xy, expected, rtol=0, atol=1e-10)
        if index >= first:
            assert frame.quality_score is None
    loaded, full_report = roundtrip_document(
        output / 'manual-series.stmtrial.json', from_registration(corrected), frames)
    assert len(loaded.payload['manual_movie']['corrections']) == 2
    full_report['render'] = verify_render(loaded, frames, corrected)
    assert not registration.corrections
    assert [frame.shift_xy for frame in registration.frames] == baseline_xy
    return {'pair': pair_report, 'series': full_report,
            'moving_positions_1based': [first + 1, second + 1],
            'note': 'Deliberate +1X and -1Y test propagation and persistence; not improved registration.'}


def verify_exports(output, frames, result):
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.avi_sources import aligned_movie_frames
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.series import open_frame_series
    import cv2

    started = perf_counter()
    path = output / 'aligned.mpp'
    save_aligned_mpp(path, result, wsxm_compatible=True)
    reopened = open_frame_series([path])
    assert len(reopened) == len(frames)
    for source, got, expected in zip(frames, reopened, result.frames, strict=True):
        np.testing.assert_array_equal(got.data, expected.image.data)
        np.testing.assert_array_equal(np.isfinite(got.data), expected.valid_mask)
        assert got.alignment.canvas_shape == result.canvas_shape
        assert got.alignment.shift_xy == expected.shift_xy
        assert got.alignment.origin_xy == expected.origin_xy
        assert got.provenance.source == str(source.source)
        assert got.provenance.source_frame_index == source.source_frame_index
    report = {'mpp': {'result': 'PASS', 'frames': len(reopened),
                       'seconds': perf_counter() - started, 'bytes': path.stat().st_size}}
    del reopened
    images = aligned_movie_frames(frames, result)
    assert images is not None
    started = perf_counter()
    plan = prepare_avi(images, fps=7, codec='FFV1',
                       presentation=MoviePresentation(pixel_proportions=True, background=255))
    path = output / 'aligned.avi'
    save_avi(path, plan)
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        assert capture.isOpened() and capture.get(cv2.CAP_PROP_FPS) == 7
        count = 0
        while True:
            ok, raster = capture.read()
            if not ok:
                break
            np.testing.assert_array_equal(raster, plan.render_frame(count))
            count += 1
        assert count == len(images)
    finally:
        capture.release()
    report['avi'] = {'result': 'PASS', 'frames': count, 'fps': 7,
                     'seconds': perf_counter() - started, 'bytes': path.stat().st_size,
                     'output_size': plan.geometry.output_size,
                     'note': 'Automatic FFmpeg decode, not VLC or manual viewing.'}
    return report


def run(args):
    import torch
    import kornia
    import urllib.request
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.registration import register_series
    from stmviewer.series import open_frame_series
    from stmviewer.trial_capture import AttemptCapture

    def no_download(*values, **options):
        raise RuntimeError('REG-07 forbids downloading models or data.')

    torch.hub.load_state_dict_from_url = no_download
    torch.hub.download_url_to_file = no_download
    urllib.request.urlopen = no_download
    torch.set_num_threads(4)
    frames = open_frame_series([args.source])[args.drop_first:]
    source_sha = digest_file(args.source)
    report = {'source': str(args.source.resolve()), 'source_sha256': source_sha,
              'frame_count': len(frames), 'shape_yx': frames[0].data.shape,
              'drop_first': args.drop_first, 'method': args.method,
              'python': platform.python_version(), 'torch': str(torch.__version__),
              'kornia': str(kornia.__version__), 'requested_device': args.device,
              'weights': str(args.weights.resolve()), 'weights_sha256': digest_file(args.weights),
              'note': 'Same original pixels/settings; no fallback or skipped failed pair. '
                      'Estimator status is not independent image-quality evidence.'}
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / 'report.json'
    write_report(report_path, report)
    capture = AttemptCapture(frames, args.method)
    previous = 0

    def progress(done, total, text):
        nonlocal previous
        if done >= previous + 50 or done == total:
            previous = done
            print(f'{args.method}: {done}/{total} {text}', flush=True)

    started = perf_counter()
    result = None
    try:
        if args.device == 'cuda':
            torch.cuda.reset_peak_memory_stats()
        result = register_series(frames, method=args.method,
                                 deep_options=DeepMatcherOptions(args.weights, args.device),
                                 progress=progress, capture=capture)
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
    report.update(seconds=perf_counter() - started, outcome=capture.payload['outcome'],
                  recorded_frames=len(capture.payload['records']),
                  successful_frames=sum(item['cumulative_xy'] is not None
                                        for item in capture.payload['records']),
                  registration_peak_rss_bytes=peak_rss())
    if args.device == 'cuda':
        report.update(peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
                      peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
    write_report(report_path, report)
    loaded, report['document'] = roundtrip_document(output / 'trial.stmtrial.json', capture.document, frames)
    report['status_counts'] = dict(Counter(item['status'] for item in loaded.payload['records']))
    if result is not None:
        report['render'] = verify_render(loaded, frames, result)
        if args.manual:
            report['manual'] = verify_manual(output, frames, result)
        write_report(report_path, report)
        if args.export:
            report['exports'] = verify_exports(output, frames, result)
    report['peak_rss_bytes'] = peak_rss()
    assert digest_file(args.source) == source_sha
    report['source_unchanged'] = 'PASS'
    write_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


def compare(args):
    # No dependency on installed model libraries or access to a CUDA device.
    sys.modules['torch'] = None
    sys.modules['kornia'] = None
    from stmviewer.series import open_frame_series
    from stmviewer.trial_document import load_trial
    from stmviewer.trial_comparison import FullTrialComparison
    import psutil

    frames = open_frame_series([args.source])[args.drop_first:]
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    a = load_trial(args.trial_a, frames)
    b = load_trial(args.trial_b, frames)
    comparison = FullTrialComparison(frames, shifts(a), shifts(b))
    assert all(a.payload['records'][i]['cumulative_xy'] is not None for i in range(len(frames)))
    for index in range(len(frames)):
        for side in ('A', 'B'):
            image = comparison.render(index, side)
            assert image.data.shape == comparison.canvas_shape
            del image
    full_seconds = perf_counter() - started
    process = psutil.Process()
    gc.collect()
    resident_before = process.memory_info().rss
    for _ in range(10):
        a = load_trial(args.trial_a, frames)
        b = load_trial(args.trial_b, frames)
        comparison = FullTrialComparison(frames, shifts(a), shifts(b))
        for index in (0, len(frames) // 2, len(frames) - 1):
            for side in ('A', 'B'):
                image = comparison.render(index, side)
                del image
    gc.collect()
    resident_after = process.memory_info().rss
    # Reopening only lightweight records should not retain copies of either movie.
    assert resident_after - resident_before < 64 * 1024 * 1024
    candidates = ([2, 30, 32, 36, 45, 46, 62, 95, 96, 97, 119, 152, 251, 351]
                  if len(frames) > 100 else [2, 17, 57, 41, 81])
    pairs = []
    for moving in candidates:
        if not 2 <= moving <= len(frames):
            continue
        index = moving - 1
        records = [document.payload['records'][index] for document in (a, b)]
        difference = np.asarray(records[1]['shift_xy']) - np.asarray(records[0]['shift_xy'])
        pairs.append({'difference_xy_b_minus_a': difference.tolist(),
                      'difference_length_px': float(np.linalg.norm(difference)),
                      'current_pair_1based': [moving - 1, moving],
                      'source_pair_1based': [frames[index - 1].source_frame_index + 1,
                                             frames[index].source_frame_index + 1],
                      'pair_xy_a': records[0]['shift_xy'], 'pair_xy_b': records[1]['shift_xy'],
                      'visual_decision': 'pending; physical truth unknown'})
    report = {'source': str(args.source.resolve()), 'trial_a': str(args.trial_a.resolve()),
              'trial_b': str(args.trial_b.resolve()), 'frame_count': len(frames),
              'rendered_images': 2 * len(frames), 'canvas_shape': comparison.canvas_shape,
              'full_load_render_seconds': full_seconds, 'model_imports_blocked': True,
              'reopen_cycles': 10, 'resident_before_bytes': resident_before,
              'resident_after_bytes': resident_after, 'peak_rss_bytes': peak_rss(),
              'fixed_and_additional_pairs': pairs,
              'note': 'New candidate pairs for manual review are not a new independent data set. '
                      'The 16GiB target is bounded by measured process RSS; this machine has more RAM.'}
    write_report(output / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    run_parser = modes.add_parser('run')
    run_parser.add_argument('source', type=Path)
    run_parser.add_argument('output', type=Path)
    run_parser.add_argument('--method', choices=METHODS, required=True)
    run_parser.add_argument('--weights', type=Path, required=True)
    run_parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    run_parser.add_argument('--export', action='store_true')
    run_parser.add_argument('--manual', action='store_true')
    compare_parser = modes.add_parser('compare')
    compare_parser.add_argument('source', type=Path)
    compare_parser.add_argument('trial_a', type=Path)
    compare_parser.add_argument('trial_b', type=Path)
    compare_parser.add_argument('output', type=Path)
    for command in (run_parser, compare_parser):
        command.add_argument('--drop-first', type=int, default=0)
    args = parser.parse_args()
    if args.drop_first < 0:
        parser.error('--drop-first must be nonnegative')
    (run if args.mode == 'run' else compare)(args)


if __name__ == '__main__':
    main()
