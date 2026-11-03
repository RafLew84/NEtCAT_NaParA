"""REG-15 bounded profile trials; run with PYTHONPATH=.:tests/stmviewer."""
import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from stmviewer.akaze_matcher import AkazeBackend
from stmviewer.correspondence_types import CorrespondenceRefusal
from stmviewer.lightglue_matcher import default_lightglue_options, load_lightglue_backend
from stmviewer.method_parameters import AkazeParameters, LightGlueParameters, ContrastParameters
from stmviewer.mpp_export import save_original_mpp
from stmviewer.pair_comparison import PairImages
from stmviewer.series import open_frame_series


def digest(data):
    return sha256(np.asarray(data, dtype='<f8').tobytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('data'))
    parser.add_argument('--output', type=Path, default=Path('data/registration-reg15'))
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--fixtures-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from test_akaze_integration import frames
    from test_matchanything_real_integration import original_frames
    for name, values in (('known-akaze.mpp', frames()), ('known-lightglue.mpp', original_frames((137, 219)))):
        target = args.output / name
        if not target.exists():
            save_original_mpp(target, values)
    if args.fixtures_only:
        return
    movie4 = open_frame_series([args.data/'MOVIE_4.mpp'])[2:]
    movie8 = open_frame_series([args.data/'MOVIE_8.mpp'])
    cases = [('MOVIE_4', number, movie4[number-1], movie4[number]) for number in (1, 29, 160)]
    cases += [('MOVIE_8', 1, movie8[0], movie8[1])]
    configurations = [
        ('akaze-default', AkazeParameters()),
        ('akaze-threshold', AkazeParameters(threshold=.0001)),
        ('akaze-percentiles', AkazeParameters(contrast=ContrastParameters(mode='percentiles'))),
        ('lightglue-default', LightGlueParameters()),
        ('lightglue-filter', LightGlueParameters(filter_threshold=.05)),
        ('lightglue-percentiles', LightGlueParameters(contrast=ContrastParameters(mode='percentiles'))),
    ]
    attempts = []
    for name, parameters in configurations:
        backend = (AkazeBackend(parameters=parameters) if isinstance(parameters, AkazeParameters)
                   else load_lightglue_backend(replace(default_lightglue_options(), device=args.device),
                                               parameters=parameters))
        try:
            for movie, number, reference, moving in cases:
                before = (digest(reference.data), digest(moving.data))
                record = dict(variant=name, file=movie, pair_1based=[number, number+1],
                              source_pair_1based=[reference.source_frame_index+1, moving.source_frame_index+1],
                              parameters=asdict(parameters), device=backend.device,
                              frame_sha256=before)
                started = perf_counter()
                try:
                    result = backend.estimate(reference.data, moving.data, moving_frame_index=number)
                    record.update(outcome='result', shift_xy=result.shift_xy, status=result.status)
                except CorrespondenceRefusal as error:
                    record.update(outcome='refusal', error=str(error))
                record['seconds'] = perf_counter()-started
                record['diagnostics'] = asdict(backend.last_diagnostics)
                assert before == (digest(reference.data), digest(moving.data))
                preview = PairImages(reference, moving)
                rasters = [preview.render(layer='reference'), preview.render(layer='moving'),
                           preview.render(layer='overlay')]
                if record['outcome'] == 'result':
                    rasters.append(preview.render(tuple(record['shift_xy']), layer='overlay'))
                array = np.concatenate([r.rgba for r in rasters], axis=1)
                path = args.output/f'{movie}-{number:03d}-{name}.png'
                Image.fromarray(array).save(path)
                record['preview'] = path.name
                attempts.append(record)
                (args.output/'attempts.json').write_text(json.dumps(attempts, indent=2, allow_nan=False))
                print(movie, number, name, record['outcome'], record.get('shift_xy'), flush=True)
        finally:
            backend.close()


if __name__ == '__main__':
    main()
