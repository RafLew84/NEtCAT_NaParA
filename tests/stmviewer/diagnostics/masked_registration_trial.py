"""Opt-in REG-03 functional trial on fixed STM pairs and complete local movies.

The selected bands below are demonstration exclusions inspected on input images,
not validated optimal masks or independent registration-quality evidence.
"""

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from threading import Event
from time import perf_counter

import numpy as np

from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import RegistrationCancelled, RegistrationError, register_series
from stmviewer.registration_masks import FrameMask, MaskRectangle
from stmviewer.series import open_frame_series


# Source indices are one-based, coordinates are half-open original pixel edges.
BANDS = {
    'MOVIE_4': {3: ((94, 103),), 4: ((120, 128),),
                33: ((82, 91),), 34: ((80, 88),),
                120: ((128, 138),), 121: ((44, 53),)},
    'MOVIE_8': {1: ((151, 174), (375, 390)), 2: ((175, 193), (373, 390)),
                16: ((149, 167), (254, 271)), 17: ((148, 171), (374, 393)),
                56: ((348, 369),), 57: ((239, 260), (475, 493))},
}
PAIRS = {'MOVIE_4': (3, 33, 120), 'MOVIE_8': (1, 16, 56)}


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='Directory with MOVIE_4.mpp and MOVIE_8.mpp')
    parser.add_argument('output', type=Path, help='New local artifact directory')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    summary = {'purpose': 'Functional masks-off/on comparison; visual quality remains unverified', 'movies': {}}
    for name, source_pairs in PAIRS.items():
        path = args.data / f'{name}.mpp'
        source_hash = digest_file(path)
        complete = open_frame_series([path])
        frames = complete[2:] if name == 'MOVIE_4' else complete
        masks = tuple(FrameMask(tuple(MaskRectangle(0, y0, frame.data.shape[1], y1, 'omit')
                                    for y0, y1 in BANDS[name].get(frame.source_frame_index + 1, ())))
                      for frame in frames)
        records = {'source': str(path), 'sha256': source_hash, 'frame_count': len(frames),
                   'shape_yx': frames[0].data.shape, 'mask_rectangles_by_source': {
                       str(frame.source_frame_index + 1): [asdict(r) for r in mask.rectangles]
                       for frame, mask in zip(frames, masks) if mask.rectangles},
                   'pairs': [], 'full': {}}
        summary['movies'][name] = records
        by_source = {frame.source_frame_index + 1: mask for frame, mask in zip(frames, masks)}
        for source in source_pairs:
            reference, moving = complete[source - 1:source + 1]
            pair = {'source_pair': [source, source + 1]}
            for enabled in (False, True):
                started = perf_counter()
                try:
                    trial = estimate_pair(reference, moving, method='masked_correlation',
                                          reference_mask=by_source[source], moving_mask=by_source[source + 1],
                                          use_masks=enabled)
                    pair[str(enabled)] = {'xy': trial.shift_xy, 'status': trial.status,
                                          'quality': trial.quality_score, 'settings': trial.settings_text,
                                          'seconds': perf_counter() - started}
                except RegistrationError as error:
                    pair[str(enabled)] = {'error': str(error), 'seconds': perf_counter() - started}
            records['pairs'].append(pair)
        for enabled in (False, True):
            started = perf_counter()
            try:
                result = register_series(frames, method='masked_correlation', masks=masks, use_masks=enabled)
            except RegistrationError as error:
                records['full'][str(enabled)] = {'error': str(error), 'seconds': perf_counter() - started}
                continue
            run = {'seconds': perf_counter() - started, 'canvas_yx': result.canvas_shape,
                   'method': result.method, 'last_shift': result.frames[-1].shift_xy}
            records['full'][str(enabled)] = run
            if enabled:
                subset = replace(result, frames=result.frames[:3])
                exported = save_aligned_mpp(args.output / f'{name}-masked-first3.mpp', subset, wsxm_compatible=True)
                reopened = open_frame_series([exported])
                for actual, expected in zip(reopened, subset.frames, strict=True):
                    np.testing.assert_array_equal(actual.data, expected.image.data)
                    np.testing.assert_array_equal(np.isfinite(actual.data), expected.valid_mask)
                    assert actual.alignment.method == result.method
                run['mpp_roundtrip'] = 'PASS: exact samples, validity, method and geometry'
                presentation = MoviePresentation(pixel_proportions=True, background=128)
                plan = prepare_avi(tuple(f.image for f in subset.frames), fps=7, codec='FFV1', presentation=presentation)
                save_avi(args.output / f'{name}-masked-first3.avi', plan)
                run['avi'] = 'Saved FFV1: first 3 frames, 7 FPS; no VLC acceptance'
                cancelled = Event()
                checkpoints = []
                def progress(done, total, description):
                    if description.startswith('Aligned:'):
                        checkpoints.append((done, total))
                        if len(checkpoints) == 2:
                            cancelled.set()
                try:
                    register_series(frames, method='masked_correlation', masks=masks, use_masks=True,
                                    progress=progress, cancelled=cancelled.is_set)
                except RegistrationCancelled:
                    run['cancel'] = {'result': 'PASS', 'last_checkpoint': checkpoints[-1]}
                else:
                    raise AssertionError('Cancellation did not interrupt the full result')
                empty = FrameMask((MaskRectangle(0, 0, frames[1].data.shape[1], frames[1].data.shape[0], 'omit'),))
                bad_masks = (masks[0], empty, *masks[2:])
                try:
                    register_series(frames, method='masked_correlation', masks=bad_masks)
                except RegistrationError as error:
                    run['empty_mask_refusal'] = str(error)
                else:
                    raise AssertionError('An empty selection silently registered')
            del result
        assert digest_file(path) == source_hash
        records['source_unchanged'] = True
        (args.output / 'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
        print(name, json.dumps(records['full'], ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
