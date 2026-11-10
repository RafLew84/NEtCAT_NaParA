"""One experimental domain method; independent of KMeans, explicitly phase-blind."""

from collections.abc import Callable
from dataclasses import asdict

import numpy as np

from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.geometry_regions import geometry_regions
from stmdomains.analysis.geometry_spectrum import axial_difference
from stmdomains.analysis.domain_measurements import measured_domain_provenance, measurement_refusal, validate_measurement
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis, MoleculeAssignment
from stmdomains.core.geometry import FrameGeometry, MoleculeGeometry


WARNING = 'Metoda eksperymentalna. Nie sprawdza przesunięcia fazowego sieci; typ struktury nieznany.'



def geometry_distance(a: MoleculeGeometry, b: MoleculeGeometry, settings: GeometryDomainSettings) -> float:
    """Worst normalized disagreement under one joint permutation of the two axes."""
    return min(max(max(axial_difference(first.row_angle_deg, second.row_angle_deg) / settings.angle_degrees,
                       100 * abs(first.period-second.period) / min(first.period, second.period) / settings.spacing_percent)
                   for first, second in zip(a.axes, axes)) for axes in (b.axes, b.axes[::-1]))


def segment_geometry(data: AnalysisInput, geometry: FrameGeometry, *,
                     settings: GeometryDomainSettings = GeometryDomainSettings(),
                     constraints: DomainSettings = DomainSettings(),
                     barrier_settings: BarrierSettings = BarrierSettings(),
                     cancelled: Callable[[], bool] = lambda: False,
                     progress: Callable[[str], None] = lambda text: None) -> FrameAnalysis:
    def check():
        if cancelled():
            raise AnalysisCancelled()
    check()
    fingerprint = validate_measurement(data, geometry)
    parameters, metadata = measured_domain_provenance(geometry, fingerprint, settings, constraints, barrier_settings)
    records = sorted(geometry.molecules.values(), key=lambda r: (*r.center_xy[::-1], r.detection_id))
    reasons = {r.detection_id: measurement_refusal(r, settings) for r in records}
    active = [r for r in records if reasons[r.detection_id] not in ('outside_field', 'suppressed_duplicate')]
    spacing = float(geometry.metadata.get('spacing', 0))
    assignments = {r.detection_id: MoleculeAssignment(r.detection_id,
        status=reasons[r.detection_id] if reasons[r.detection_id] in ('outside_field', 'suppressed_duplicate') else 'unassigned',
        rejection_reason=reasons[r.detection_id], metadata={'geometry': asdict(r)}) for r in records}
    if not active or not spacing > 0 or data.annotations.detection_state != 'available':
        return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index,
            'no_annotations' if not records else 'insufficient_data', geometry.message or 'Brak pomiarów.',
            assignments, parameters=parameters, metadata=metadata)
    points = np.array([r.center_xy for r in active], float)
    scale = (geometry.calibration.x, geometry.calibration.y)
    # The existing image-barrier detector operates in pixel units; the graph and
    # raster use the calibrated metric. This distinction is recorded explicitly.
    from scipy.spatial import cKDTree
    spacing_px = float(np.median(np.asarray(cKDTree(points).query(points, k=2)[0])[:, 1])) if len(points) > 1 else 1.
    progress('Tworzenie domen geometrycznych…')
    barrier, barrier_metadata = image_barriers(np.asarray(data.frame.image, float), spacing_px, check, settings=barrier_settings)
    eligible = np.array([not reasons[r.detection_id] for r in active], bool)
    ids, regions, construction = geometry_regions(points, scale, spacing, eligible,
        lambda a, b: geometry_distance(active[a], active[b], settings), barrier, constraints, check)
    for record, domain in zip(active, ids):
        reason = reasons[record.detection_id] or ('small_or_fragmented_component' if not domain else '')
        assignments[record.detection_id] = MoleculeAssignment(record.detection_id, int(domain),
            status='domain' if domain else 'unassigned', rejection_reason=reason,
            metadata={'geometry': asdict(record), 'phase_boundary_tested': False})
    check()
    return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index, 'complete', WARNING,
        assignments, parameters={**parameters, 'spacing_px': spacing_px, 'spacing_metric': spacing},
        metadata={**metadata, 'barriers': barrier_metadata, 'domain_construction': construction},
        domain_labels=regions, barrier_mask=barrier)
