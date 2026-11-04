"""Measure one original frame without fitting classes or changing domain memberships."""

from collections.abc import Callable
from dataclasses import replace

import numpy as np
from scipy.spatial import cKDTree
from threadpoolctl import threadpool_limits

from stmdomains.analysis.features import prepare_points
from stmdomains.analysis.geometry_spectrum import GeometrySettings, axial_difference, spectrum_axes
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput
from stmdomains.core.geometry import FrameGeometry, MoleculeGeometry, PixelCalibration, RowAxis


def measure_geometry(data: AnalysisInput, *, calibration: PixelCalibration = PixelCalibration(),
                     cancelled: Callable[[], bool] = lambda: False,
                     progress: Callable[[str], None] = lambda text: None) -> FrameGeometry:
    settings = GeometrySettings()
    def check():
        if cancelled():
            raise AnalysisCancelled()
    check()
    records = {d.detection_id: MoleculeGeometry(d.detection_id, d.center_xy, 'insufficient', 'Brak wystarczających danych.')
               for d in data.annotations.detections}
    base = FrameGeometry(data.series_id, data.frame.working_index, data.frame.source_index,
                         calibration, records, settings.parameters(), {})
    if (data.frame.image.size > 4194304 or len(records) > 3000 or
            data.annotations.detection_state != 'available'):
        return replace(base, message='Niedostępne oznaczenia lub przekroczony limit zasobów pomiaru.')
    # Duplicate handling must use the same metric as the measurement. Normalize
    # the smaller pixel size to one to avoid unit-dependent epsilon thresholds.
    ratio = np.array((calibration.x, calibration.y)) / min(calibration.x, calibration.y)
    metric_detections = tuple(replace(d, bbox_xyxy=tuple(np.asarray(d.bbox_xyxy)*np.tile(ratio, 2)))
                              for d in data.annotations.detections)
    h, w = data.frame.image.shape
    active_metric, _, _, excluded = prepare_points(metric_detections,
        (int(np.ceil(h*ratio[1])), int(np.ceil(w*ratio[0]))), check)
    original = {d.detection_id: d for d in data.annotations.detections}
    active = [original[d.detection_id] for d in active_metric]
    xy = np.asarray([d.center_xy for d in active], float).reshape(-1, 2)
    for key, (reason, _) in excluded.items():
        records[key] = replace(records[key], reason=reason)
    metric = xy * (calibration.x, -calibration.y)
    spacing = float(np.median(np.asarray(cKDTree(metric).query(metric, k=2)[0])[:, 1])) if len(metric) > 1 else 0.
    metadata = {'input_sha256': input_fingerprint(data), 'spacing': spacing,
                'interpretation': 'Bounded positional-order measurement; coherence is not a correctness probability.'}
    if len(metric) < settings.minimum_count or not spacing > 0:
        return replace(base, molecules=records, metadata=metadata, message='Za mało punktów do pomiaru geometrii.')
    normalized = metric / spacing
    tree = cKDTree(normalized)
    h, w = data.frame.image.shape
    with threadpool_limits(limits=1):
        for index, detection in enumerate(active):
            check()
            progress(f'Pomiar geometrii: {index+1}/{len(active)}')
            center = normalized[index]
            samples = []
            for factor in (1., 1-settings.radius_variation_fraction, 1+settings.radius_variation_fraction):
                ids = tree.query_ball_point(center, settings.radius_factor*factor)
                offsets = normalized[ids]-center
                axes, effective, reason = spectrum_axes(offsets, settings, check)
                samples.append((axes, len(ids), effective, reason))
            axes, count, effective, reason = samples[0]
            stable: list[RowAxis] = []
            angle_changes: list[float] = []
            period_changes: list[float] = []
            for axis in axes:
                matched = []
                for alternatives, _, _, _ in samples[1:]:
                    close = [candidate for candidate in alternatives
                             if axial_difference(axis['normal'], candidate['normal']) <= settings.maximum_angle_change_deg
                             and abs(axis['frequency']/candidate['frequency']-1) <= settings.maximum_period_change_fraction]
                    if close:
                        matched.append(min(close, key=lambda a: axial_difference(axis['normal'], a['normal'])))
                if len(matched) == 2:
                    stable.append(RowAxis((axis['normal']+90)%180, axis['normal'], spacing/axis['frequency'], axis['coherence']))
                    angle_changes.extend(axial_difference(axis['normal'], a['normal']) for a in matched)
                    period_changes.extend(abs(axis['frequency']/a['frequency']-1) for a in matched)
            stable.sort(key=lambda axis: (-round(axis.period, 3), axis.row_angle_deg))
            radius = settings.radius_factor*spacing
            x, y = detection.center_xy
            edge = min(x*calibration.x, (w-x)*calibration.x, y*calibration.y, (h-y)*calibration.y) < radius*1.1
            status = 'lattice_2d' if len(stable) == 2 else 'rows_1d' if stable else (
                'insufficient' if reason == 'insufficient_support' else 'unresolved')
            message = ('Za małe wsparcie pomiaru.' if status == 'insufficient' else
                       'Brak stabilnego kierunku w badanym zakresie częstości.' if status == 'unresolved' else
                       'Potwierdzono jeden kierunek; drugi nie został potwierdzony.' if status == 'rows_1d' else
                       'Dwa niezależne, stabilne kierunki periodyczności w tym otoczeniu.')
            records[detection.detection_id] = MoleculeGeometry(detection.detection_id, detection.center_xy,
                status, message, tuple(stable), count, effective, radius,
                max(angle_changes) if angle_changes else None, max(period_changes) if period_changes else None, edge)
    check()
    return replace(base, molecules=records, metadata=metadata, message='Pomiar geometrii zakończony.')
