"""Evaluate the predeclared SD-V4-17 settings; no fitted thresholds or fake accuracy."""

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from stmdomains.analysis import analyze_frame
from stmdomains.analysis.geometry import measure_geometry
from stmdomains.analysis.geometry_calibration import calibration_from_header
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.geometry_domains import geometry_distance, segment_geometry
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import ImportCandidate, prepare_import
from stmdomains.tools.geometry_domain_demo import create_domain_geometry_demo


SETTINGS = {'default': GeometryDomainSettings(), 'strict': GeometryDomainSettings(6., 8., .85, 12),
            'loose': GeometryDomainSettings(20., 25., .75, 10)}


def score(result, data, truth=None):
    record = {'assigned': result.assigned_count, 'active': result.active_count, 'domains': result.domain_count,
              'refusals': dict(Counter(a.rejection_reason for a in result.assignments.values() if not a.domain_local_id)),
              'input_sha256': result.metadata.get('input_sha256'), 'wrong_merges': None, 'split_regions': None,
              'missed_regions': None, 'cross_boundary_pairs_joined': None, 'false_2d_assignments': None}
    if truth is None or set(truth.values()) == {-1}:
        return record
    groups = [{truth[key] for key, a in result.assignments.items() if a.domain_local_id == domain}
              for domain in sorted({a.domain_local_id for a in result.assignments.values()} - {0})]
    regions = {label for label in truth.values() if label > 0}
    represented = [{a.domain_local_id for key, a in result.assignments.items()
                    if truth[key] == label and a.domain_local_id} for label in regions]
    record.update(wrong_merges=sum(len(g - {0, -1}) > 1 for g in groups),
                  split_regions=sum(len(g) > 1 for g in represented),
                  missed_regions=sum(not g for g in represented),
                  false_2d_assignments=sum(truth[k] == 0 and a.domain_local_id > 0 for k, a in result.assignments.items()))
    detections = data.annotations.detections
    points = np.array([d.center_xy for d in detections])
    if len(points) > 1:
        tree = cKDTree(points)
        spacing = float(np.median(np.asarray(tree.query(points, k=2)[0])[:, 1]))
        pairs = sorted(tree.query_pairs(1.5*spacing))
        crossing = [(detections[a].detection_id, detections[b].detection_id) for a, b in pairs
                    if truth[detections[a].detection_id] > 0 and truth[detections[b].detection_id] > 0
                    and truth[detections[a].detection_id] != truth[detections[b].detection_id]]
        joined = refused = 0
        for a, b in crossing:
            da, db = result.assignments[a].domain_local_id, result.assignments[b].domain_local_id
            joined += bool(da and da == db)
            refused += not bool(da and db)
        record.update(cross_boundary_pairs=len(crossing), cross_boundary_pairs_joined=joined,
                      cross_boundary_pairs_with_refusal=refused,
                      cross_boundary_pairs_separated=len(crossing)-joined-refused)
    return record


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
            print(section, index+1, flush=True)
            measured = measure_geometry(data, calibration=calibration)
            truth = reference[str(index+1)]['labels'] if section == 'controls' else None
            item = {'measurement': dict(Counter(m.status for m in measured.molecules.values())),
                    'baseline': score(analyze_frame(data, k=5), data, truth), 'geometry': {}}
            for name, settings in SETTINGS.items():
                result = segment_geometry(data, measured, settings=settings)
                evaluated = score(result, data, truth)
                largest = 0.
                for domain in {m.domain_local_id for m in result.assignments.values()} - {0}:
                    members = [measured.molecules[k] for k, m in result.assignments.items() if m.domain_local_id == domain]
                    for i, a in enumerate(members):
                        largest = max(largest, max((geometry_distance(a, b, settings) for b in members[i+1:]), default=0.))
                evaluated['largest_normalized_region_disagreement'] = largest
                assert largest <= 1. + 1e-10
                item['geometry'][name] = evaluated
            report[section][str(index+1)] = item
            (directory/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-17'))
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    run(args.directory, args.source)


if __name__ == '__main__':
    main()
