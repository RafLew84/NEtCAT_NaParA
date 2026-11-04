"""Environment similarity classes followed by spatial, orientation-aware domains."""

from collections.abc import Callable
import colorsys
from dataclasses import asdict

import numpy as np
from scipy.spatial import cKDTree

from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.freud_adapter import compare_environments, require_freud, MAX_POINTS, TIME_LIMIT_SECONDS
from stmdomains.analysis.freud_neighbors import prepare_environments
from stmdomains.analysis.freud_settings import FreudSettings
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.geometry_domains import geometry_distance
from stmdomains.analysis.geometry_regions import geometry_regions
from stmdomains.analysis.domain_measurements import measurement_refusal, validate_measurement
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.geometry import FrameGeometry

WARNING = ('Próba freud: klasy podobnych otoczeń w tej klatce, nie typy struktur. '
           'Domeny wymagają także spójności i zgodnej orientacji. Zgodność fazy nie jest sprawdzana.')


def _color(index: int) -> str:
    rgb = colorsys.hsv_to_rgb((index*.61803398875) % 1., .58, .92)
    return '#' + ''.join(f'{round(c*255):02x}' for c in rgb)


def segment_freud(data: AnalysisInput, geometry: FrameGeometry, *, settings: FreudSettings = FreudSettings(),
                  geometry_settings: GeometryDomainSettings = GeometryDomainSettings(),
                  constraints: DomainSettings = DomainSettings(), barrier_settings: BarrierSettings = BarrierSettings(),
                  cancelled: Callable[[], bool] = lambda: False,
                  progress: Callable[[str], None] = lambda text: None) -> FrameAnalysis:
    def check():
        if cancelled():
            raise AnalysisCancelled()
    check()
    require_freud()
    fingerprint = validate_measurement(data, geometry)
    parameters = {**geometry_settings.parameters(), **settings.parameters(), **barrier_settings.parameters(),
                  'minimum_domain_size': constraints.minimum_domain_size,
                  'edge_distance_factor': constraints.edge_distance_factor,
                  'raster_radius_factor': constraints.raster_radius_factor,
                  'measurement_parameters': geometry.parameters, 'calibration': asdict(geometry.calibration)}
    metadata = {'input_sha256': fingerprint, 'phase_boundary_tested': False, 'structural_type': 'unknown',
                'measurement_message': geometry.message}
    records = sorted(geometry.molecules.values(), key=lambda r: (*r.center_xy[::-1], r.detection_id))
    active = [r for r in records if r.reason not in ('outside_field', 'suppressed_duplicate')]
    if len(active) > MAX_POINTS:
        raise ValueError(f'Próba freud obsługuje maksymalnie {MAX_POINTS} aktywnych molekuł w klatce.')
    assignments = {r.detection_id: MoleculeAssignment(r.detection_id,
        status=r.reason if r.reason in ('outside_field', 'suppressed_duplicate') else 'unassigned',
        rejection_reason=r.reason, metadata={'geometry': asdict(r)}) for r in records}
    spacing = float(geometry.metadata.get('spacing', 0))
    if not active or not spacing > 0 or data.annotations.detection_state != 'available':
        return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index,
            'no_annotations' if not records else 'insufficient_data', geometry.message or 'Brak pomiarów.',
            assignments, parameters=parameters, metadata=metadata)
    points = np.array([r.center_xy for r in active], float)
    scale = (geometry.calibration.x, geometry.calibration.y)
    environments = prepare_environments(points, data.frame.image.shape, scale, spacing, settings, check)
    progress(f'Freud: porównanie {len(environments.eligible)} pełnych otoczeń; limit {TIME_LIMIT_SECONDS:g} s…')
    labels, version = compare_environments(environments, settings, cancelled)
    spacing_px = float(np.median(np.asarray(cKDTree(points).query(points, k=2)[0])[:, 1])) if len(points) > 1 else 1.
    progress('Freud: tworzenie spójnych domen z klas i orientacji…')
    barrier, barrier_metadata = image_barriers(np.asarray(data.frame.image, float), spacing_px, check, settings=barrier_settings)
    reasons = [env['reason'] or measurement_refusal(r, geometry_settings) for env, r in zip(environments.details, active)]
    eligible = np.array([not reason for reason in reasons], bool)
    ids, regions, construction = geometry_regions(points, scale, spacing, eligible,
        lambda a, b: geometry_distance(active[a], active[b], geometry_settings) if labels[a] == labels[b] else float('inf'),
        barrier, constraints, check)
    for record, label, domain, reason, env in zip(active, labels, ids, reasons, environments.details):
        details = {**env, 'neighbor_ids': [active[n].detection_id for n in env['neighbors']],
                   'neighbor_centers': [active[n].center_xy for n in env['neighbors']]}
        reason = reason or ('small_or_fragmented_component' if not domain else '')
        assignments[record.detection_id] = MoleculeAssignment(record.detection_id, int(domain),
            class_id=str(label) if domain else '', provisional_class_id=str(label) if label else '',
            status='domain' if domain else 'unassigned', rejection_reason=reason,
            metadata={'geometry': asdict(record), 'freud_environment': details, 'phase_boundary_tested': False})
    check()
    classes = tuple(ResultClass(str(i), _color(i)) for i in range(1, int(labels.max(initial=0))+1))
    return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index, 'complete', WARNING,
        assignments, classes, {**parameters, 'spacing_px': spacing_px, 'spacing_metric': spacing},
        {**metadata, 'barriers': barrier_metadata, 'domain_construction': construction,
         'environment_clustering': {'engine': 'freud.EnvironmentCluster', 'version': version, 'periodic': False,
            'units': 'frame_median_nearest_neighbor', 'complete_environments': len(environments.eligible),
            'environment_classes': len(classes), 'pair_scope': 'all_complete_environments',
            'registration': settings.registration, 'time_limit_seconds': TIME_LIMIT_SECONDS}},
        domain_labels=regions, barrier_mask=barrier)
