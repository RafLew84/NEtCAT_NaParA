"""Opt-in real-data functional probe for explicit manual movie corrections.

The deliberate +1 px edit tests propagation, not registration quality. No source
file is modified. Outputs are large local artifacts, never Git fixtures.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from threading import Event
from time import perf_counter

import numpy as np

from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.avi_sources import aligned_movie_frames
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial, remove_movie_correction
from stmviewer.manual_pair import ManualPairDraft
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.registration import RegistrationCancelled, RegistrationError, register_series
from stmviewer.series import open_frame_series


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest_arrays(frames):
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(memoryview(np.ascontiguousarray(frame.data)).cast('B'))
    return digest.hexdigest()


def manual_trial(result, index, dx, dy):
    draft = ManualPairDraft(result.frames[index - 1].original, result.frames[index].original,
                            start=movie_pair_trial(result, index))
    draft.nudge(dx, dy)
    return draft.apply()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, help='New local output directory')
    parser.add_argument('--drop-first', type=int, default=2)
    parser.add_argument('--moving-frame', type=int, default=30, help='1-based index after dropping')
    parser.add_argument('--method', default='deep_matcher_translation')
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--device', choices=['cpu', 'cuda', 'auto'], default='cuda')
    parser.add_argument('--fallback', default='phase_no_normalization', help='Explicit functional fallback')
    parser.add_argument('--avi', action='store_true', help='Export/decode a 7-frame neighborhood as FFV1')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve()
    report = dict(source=str(source), source_sha256=digest_file(source),
                  function_only='Deliberate +1 X tests propagation, not visual quality',
                  requested_method=args.method, requested_device=args.device,
                  weights=str(args.weights) if args.weights else None,
                  drop_first=args.drop_first, moving_frame_after_drop=args.moving_frame)

    def save():
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    save()
    frames = open_frame_series([source])[args.drop_first:]
    index = args.moving_frame - 1
    if not 1 <= index < len(frames):
        raise ValueError('Pair is outside the remaining series.')
    original_digest = digest_arrays(frames)
    report.update(frame_count=len(frames), shape_yx=frames[0].data.shape,
                  source_pair_1based=[frames[index - 1].source_frame_index + 1,
                                      frames[index].source_frame_index + 1])
    started = perf_counter()
    last = 0

    def progress(done, total, text):
        nonlocal last
        if done == total or done >= last + 50:
            print(f'{done}/{total} {text}', flush=True)
            last = done

    try:
        result = register_series(frames, method=args.method,
                                 deep_options=DeepMatcherOptions(args.weights, args.device),
                                 progress=progress)
    except RegistrationError as error:
        report['requested_method_error'] = str(error)
        report['requested_method_seconds'] = perf_counter() - started
        save()
        print(f'Requested method failed: {error}; explicit fallback {args.fallback}', flush=True)
        started = perf_counter()
        result = register_series(frames, method=args.fallback, progress=progress)
    report.update(actual_method=result.method, actual_device=result.device,
                  registration_seconds=perf_counter() - started,
                  base_canvas_yx=result.canvas_shape,
                  base_pair_xy=movie_pair_trial(result, index).shift_xy)
    save()
    baseline_xy = [f.shift_xy for f in result.frames]
    trial = manual_trial(result, index, 1, 0)
    started = perf_counter()
    corrected = apply_movie_correction(result, trial, progress=progress)
    report['correction_seconds'] = perf_counter() - started
    report['corrected_canvas_yx'] = corrected.canvas_shape
    report['correction'] = asdict(corrected.corrections[0])
    for i, frame in enumerate(corrected.frames):
        expected = baseline_xy[i] if i < index else (baseline_xy[i][0] + 1, baseline_xy[i][1])
        np.testing.assert_allclose(frame.shift_xy, expected, rtol=0, atol=1e-10)
        assert frame.original is frames[i]
        if i >= index:
            assert frame.quality_score is None and frame.status == 'manual_review'
    assert not result.corrections
    assert [f.shift_xy for f in result.frames] == baseline_xy
    report['propagation_originals_previous_result'] = 'PASS'
    save()

    cancellation = Event()
    checkpoints = []
    second_trial = manual_trial(corrected, index, 0, 1)

    def cancel_after_render(done, total, text):
        checkpoints.append((done, total, text))
        if done >= min(10, len(frames)):
            cancellation.set()

    try:
        apply_movie_correction(corrected, second_trial, progress=cancel_after_render,
                               cancelled=cancellation.is_set)
    except RegistrationCancelled:
        report['cancellation'] = dict(result='PASS', final_checkpoint=checkpoints[-1])
    else:
        raise AssertionError('Rebuild finished instead of acknowledging cancellation')
    assert len(corrected.corrections) == 1
    assert corrected.corrections[0].shift_xy == trial.shift_xy
    save()
    started = perf_counter()
    restored = remove_movie_correction(corrected, index)
    assert not restored.corrections and restored.canvas_shape == result.canvas_shape
    for original, recovered in zip(result.frames, restored.frames, strict=True):
        np.testing.assert_array_equal(original.image.data, recovered.image.data)
        np.testing.assert_array_equal(original.valid_mask, recovered.valid_mask)
        assert original.shift_xy == recovered.shift_xy
        assert original.quality_score == recovered.quality_score
    report['restore'] = dict(result='PASS', seconds=perf_counter() - started)
    del restored, result
    save()

    started = perf_counter()
    mpp = args.output / 'corrected-aligned.mpp'
    save_aligned_mpp(mpp, corrected, wsxm_compatible=True, progress=progress)
    report['mpp_export_seconds'] = perf_counter() - started
    started = perf_counter()
    reopened = open_frame_series([mpp])
    assert len(reopened) == len(corrected.frames)
    for got, expected in zip(reopened, corrected.frames, strict=True):
        np.testing.assert_array_equal(got.data, expected.image.data)
        assert got.alignment is not None
        assert got.alignment.canvas_shape == corrected.canvas_shape
        assert got.alignment.shift_xy == expected.shift_xy
        assert got.alignment.quality_score == expected.quality_score
        assert got.alignment.manual_movie is not None
        assert got.alignment.manual_movie.corrections == corrected.corrections
    report['mpp_reopen'] = dict(result='PASS', seconds=perf_counter() - started,
                                bytes=mpp.stat().st_size,
                                metadata_bytes=Path(str(mpp) + '.stmviewer.json').stat().st_size)
    del reopened
    save()
    if args.avi:
        import cv2
        images = aligned_movie_frames(frames, corrected)
        assert images is not None
        start, end = max(1, index - 2), min(len(images), index + 4)
        plan = prepare_avi(images, start=start, end=end, fps=7, codec='FFV1',
                           presentation=MoviePresentation(pixel_proportions=True))
        avi = args.output / 'corrected-neighborhood.avi'
        started = perf_counter()
        save_avi(avi, plan)
        capture = cv2.VideoCapture(str(avi))
        assert capture.isOpened()
        fps = capture.get(cv2.CAP_PROP_FPS)
        count = 0
        while True:
            success, raster = capture.read()
            if not success:
                break
            np.testing.assert_array_equal(raster, plan.render_frame(count))
            count += 1
        capture.release()
        assert fps == 7 and count == end - start + 1
        report['avi'] = dict(result='PASS', frames=count, fps=fps, seconds=perf_counter() - started,
                             bytes=avi.stat().st_size, range_1based=[start, end],
                             note='Automatic decode; not VLC or human visual acceptance')
        save()
    assert digest_arrays(frames) == original_digest
    assert digest_file(source) == report['source_sha256']
    report['source_unchanged'] = 'PASS'
    save()
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
