"""Frozen SD-V4-18 comparison on the same controls and TTMAPP inputs as method 17."""

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from time import monotonic

from stmdomains.analysis import analyze_frame
from stmdomains.analysis.freud_domains import segment_freud
from stmdomains.analysis.freud_settings import FreudSettings
from stmdomains.analysis.geometry import measure_geometry
from stmdomains.analysis.geometry_calibration import calibration_from_header
from stmdomains.analysis.geometry_domains import segment_geometry
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import ImportCandidate, prepare_import
from stmdomains.tools.geometry_domain_demo import create_domain_geometry_demo
from stmdomains.tools.geometry_domain_trial import score

SETTINGS = {str(t): FreudSettings(tolerance=t) for t in (.12, .20, .30)}


def run(directory: Path, source: Path | None):
    paths = create_domain_geometry_demo(directory/'demo')
    reference = json.loads(paths['reference'].read_text())
    report = {'settings': {key: asdict(value) for key, value in SETTINGS.items()}, 'controls': {}, 'ttmapp': {}}
    cases = [('controls', paths['series'], range(9))]
    if source is not None:
        cases.append(('ttmapp', source, range(258, 266)))
    for section, path, indices in cases:
        imported = prepare_import(path)
        if not isinstance(imported, ImportCandidate):
            raise ValueError(imported.message)
        series = imported.series
        presenter = FramePresenter(series)
        calibration = calibration_from_header(series.raw_header, series.frame_shape)
        for index in indices:
            data = presenter.analysis_input(index)
            started = monotonic()
            measured = measure_geometry(data, calibration=calibration)
            truth = reference[str(index+1)]['labels'] if section == 'controls' else None
            item = {'measurement': dict(Counter(m.status for m in measured.molecules.values())),
                    'measurement_seconds': monotonic()-started, 'freud': {}}
            methods = {'baseline': lambda: analyze_frame(data, k=5), 'geometry': lambda: segment_geometry(data, measured)}
            for name, calculate in methods.items():
                started = monotonic()
                result = calculate()
                item[name] = {**score(result, data, truth), 'seconds': monotonic()-started}
            settings = dict(SETTINGS)
            if section == 'controls' and index in (0, 1):
                settings['0.2_rotation'] = FreudSettings(registration=True)
            for name, setting in settings.items():
                started = monotonic()
                print(section, index+1, name, flush=True)
                try:
                    result = segment_freud(data, measured, settings=setting)
                    item['freud'][name] = {**score(result, data, truth), 'classes': len(result.classes),
                        'complete_environments': sum(bool(m.provisional_class_id) for m in result.assignments.values()),
                        'seconds': monotonic()-started,
                        'library_version': result.metadata.get('environment_clustering', {}).get('version')}
                except ValueError as error:
                    item['freud'][name] = {'error': str(error), 'seconds': monotonic()-started}
            report[section][str(index+1)] = item
            (directory/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-18'))
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    run(args.directory, args.source)


if __name__ == '__main__':
    main()
