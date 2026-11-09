"""Public adapter: measured lattice features → level sets → seeded domain components."""

from collections.abc import Callable
from dataclasses import asdict

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.domain_measurements import measured_domain_provenance, measurement_refusal, validate_measurement
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.levelset_features import feature_scales, initial_prototypes, paired_features, spatial_support
from stmdomains.analysis.levelset_settings import LevelSetSettings
from stmdomains.analysis.levelset_solver import evolve
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis, MoleculeAssignment
from stmdomains.core.geometry import FrameGeometry


def _seeded_components(labels, points, eligible, minimum, check):
    regions = np.zeros(labels.shape, np.int32)
    groups = []
    seeds = np.rint(points).astype(int)
    seeds[:, 0] = np.clip(seeds[:, 0], 0, labels.shape[1]-1)
    seeds[:, 1] = np.clip(seeds[:, 1], 0, labels.shape[0]-1)
    for model in np.unique(labels[labels >= 0]):
        check()
        components, _ = ndi.label(labels == model, structure=np.ones((3, 3)))
        at_points = components[seeds[:, 1], seeds[:, 0]]
        for component in np.unique(at_points[eligible]):
            check()
            members = np.flatnonzero((at_points == component) & eligible)
            if component and len(members) >= minimum:
                temporary = len(groups)+1
                regions[components == component] = temporary
                groups.append((members, temporary))
    groups.sort(key=lambda item: (points[item[0], 1].mean(), points[item[0], 0].mean()))
    remap = np.zeros(len(groups)+1, np.int32)
    ids = np.zeros(len(points), np.int32)
    for number, (members, temporary) in enumerate(groups, 1):
        ids[members] = number
        remap[temporary] = number
    return ids, remap[regions]


def segment_levelset(data: AnalysisInput, geometry: FrameGeometry, *,
                     settings: LevelSetSettings = LevelSetSettings(),
                     geometry_settings: GeometryDomainSettings = GeometryDomainSettings(),
                     constraints: DomainSettings = DomainSettings(),
                     barrier_settings: BarrierSettings = BarrierSettings(),
                     cancelled: Callable[[], bool] = lambda: False,
                     progress: Callable[[str], None] = lambda text: None) -> FrameAnalysis:
    def check():
        if cancelled():
            raise AnalysisCancelled()
    check()
    fingerprint = validate_measurement(data, geometry)
    parameters, metadata = measured_domain_provenance(geometry, fingerprint, geometry_settings, constraints, barrier_settings)
    parameters.update(settings.parameters())
    parameters.pop('edge_distance_factor')  # Graph linking is not part of this method.
    records = sorted(geometry.molecules.values(), key=lambda r: (*r.center_xy[::-1], r.detection_id))
    reasons = {r.detection_id: measurement_refusal(r, geometry_settings) for r in records}
    active = [r for r in records if reasons[r.detection_id] not in ('outside_field', 'suppressed_duplicate')]
    assignments = {r.detection_id: MoleculeAssignment(r.detection_id,
        status=reasons[r.detection_id] if reasons[r.detection_id] in ('outside_field', 'suppressed_duplicate') else 'unassigned',
        rejection_reason=reasons[r.detection_id], metadata={'geometry': asdict(r)}) for r in records}
    spacing = float(geometry.metadata.get('spacing', 0))
    if not active or not spacing > 0 or data.annotations.detection_state != 'available':
        return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index,
            'no_annotations' if not records else 'insufficient_data', geometry.message or 'Brak pomiarów.',
            assignments, parameters=parameters, metadata=metadata)
    points = np.array([r.center_xy for r in active], float)
    scale = (geometry.calibration.x, geometry.calibration.y)
    spacing_px = float(np.median(np.asarray(cKDTree(points).query(points, k=2)[0])[:, 1])) if len(points) > 1 else 1.
    barrier, barrier_metadata = image_barriers(np.asarray(data.frame.image, float), spacing_px, check, settings=barrier_settings)
    eligible = np.array([not reasons[r.detection_id] for r in active], bool)
    nearest, valid = spatial_support(points, eligible, scale, spacing, constraints.raster_radius_factor,
                                    barrier | ~np.isfinite(data.frame.image), check)
    supported_records = [r for r, yes in zip(active, eligible) if yes]
    prototypes = initial_prototypes(supported_records, geometry_settings, check)
    values = np.zeros((len(active), 2, 3), float)
    values[eligible] = paired_features(supported_records)
    labels, solver_metadata = evolve(values[nearest[valid]], prototypes, feature_scales(geometry_settings), valid,
                                     (scale[1]/spacing, scale[0]/spacing), settings, check, progress)
    ids, regions = _seeded_components(labels, points, eligible, constraints.minimum_domain_size, check)
    for record, domain in zip(active, ids):
        reason = reasons[record.detection_id] or ('levelset_no_component' if not domain else '')
        assignments[record.detection_id] = MoleculeAssignment(record.detection_id, int(domain),
            status='domain' if domain else 'unassigned', rejection_reason=reason,
            metadata={'geometry': asdict(record), 'phase_boundary_tested': False})
    check()
    return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index, 'complete',
        'Level set: metoda eksperymentalna, typ nieznany. Nie sprawdza granic przesunięcia fazowego.',
        assignments, parameters={**parameters, 'spacing_px': spacing_px, 'spacing_metric': spacing},
        metadata={**metadata, 'barriers': barrier_metadata, 'levelset': solver_metadata,
                  'domain_construction': {'final_domains': int(ids.max(initial=0)), 'valid_pixels': int(valid.sum()),
                                          'removed_by_component_support': int(np.sum(eligible & (ids == 0)))}},
        domain_labels=regions, barrier_mask=barrier)
