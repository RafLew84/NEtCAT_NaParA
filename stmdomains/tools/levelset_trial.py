"""Predeclared paired comparison, no per-frame tuning or boundary accuracy claim."""

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic
from typing import Any

import numpy as np
import scipy

from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.geometry import measure_geometry
from stmdomains.analysis.geometry_calibration import calibration_from_header
from stmdomains.analysis.geometry_domains import segment_geometry
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.levelset_domains import segment_levelset
from stmdomains.analysis.levelset_settings import LevelSetSettings
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import ImportCandidate, prepare_import
from stmdomains.tools.geometry_domain_trial import score
from stmdomains.tools.levelset_demo import create_levelset_demo


def run(directory: Path, source: Path | None):
    paths = create_levelset_demo(directory/'demo')
    reference = json.loads(paths['reference'].read_text())
    extra_reference = json.loads(paths['extra_reference'].read_text())
    report: dict[str, Any] = {'protocol': 'experiment-26.md', 'generator': 'levelset_demo_v1',
        'numpy': np.__version__, 'scipy': scipy.__version__, 'geometry': asdict(GeometryDomainSettings()),
        'levelset': [asdict(LevelSetSettings(s)) for s in (0., .25, 1.)], 'sources': {},
        'controls': {}, 'extra': {}, 'ttmapp': {}}
    cases = [('controls', paths['series'], range(9), reference), ('extra', paths['extra'], range(2), extra_reference)]
    if source is not None:
        cases.append(('ttmapp', source.resolve(), range(258, 266), None))
    rng = np.random.default_rng(20261109)
    variants = [(method, strength, barrier) for barrier in ('default', 'off')
                for method, strength in [('geometry', None), ('levelset', 0.), ('levelset', .25), ('levelset', 1.)]]
    for section, path, indices, references in cases:
        imported = prepare_import(path)
        if not isinstance(imported, ImportCandidate):
            raise ValueError(imported.message)
        series = imported.series
        report['sources'][section] = {'path': str(path.resolve()), 'session_sha256': sha256(path.read_bytes()).hexdigest(),
                                      'series_id': series.identity, 'frame_shape': list(series.frame_shape)}
        presenter = FramePresenter(series)
        calibration = calibration_from_header(series.raw_header, series.frame_shape)
        for index in indices:
            data = presenter.analysis_input(index)
            started = monotonic()
            measured = measure_geometry(data, calibration=calibration)
            truth = references[str(index+1)]['labels'] if references is not None else None
            item: dict[str, Any] = {'name': references[str(index+1)]['name'] if references else f'TTMAPP{index+1}',
                'measurement_seconds': monotonic()-started, 'calibration': asdict(calibration),
                'measurement': dict(Counter(m.status for m in measured.molecules.values())), 'variants': {}}
            for variant in rng.permutation(len(variants)):
                method, strength, barrier = variants[variant]
                name = f'{method}_{strength}_{barrier}'
                print(section, index+1, name, flush=True)
                barriers = BarrierSettings() if barrier == 'default' else BarrierSettings(minimum_span_factor=100.)
                started = monotonic()
                try:
                    result = (segment_geometry(data, measured, barrier_settings=barriers) if method == 'geometry' else
                              segment_levelset(data, measured, settings=LevelSetSettings(float(strength)), barrier_settings=barriers))
                    seconds = monotonic()-started
                    if barrier == 'off' and result.barrier_mask is not None:
                        assert not result.barrier_mask.any(), 'Off control must have no barrier pixels.'
                    item['variants'][name] = {**score(result, data, truth), 'seconds': seconds,
                        'barrier_pixels': int(result.barrier_mask.sum()) if result.barrier_mask is not None else 0,
                        'solver': dict(result.metadata.get('levelset', {})), 'method_version': result.parameters['domain_method'],
                        'mask_sha256': sha256(result.domain_labels.tobytes()).hexdigest() if result.domain_labels is not None else None}
                except ValueError as error:
                    item['variants'][name] = {'error': str(error), 'seconds': monotonic()-started}
            report[section][str(index+1)] = item
            (directory/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-26'))
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    run(args.directory, args.source)


if __name__ == '__main__':
    main()
