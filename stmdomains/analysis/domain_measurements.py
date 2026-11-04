"""Validate the shared measurement input and support policy of methods 17 and 18."""

from math import isfinite

from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.core.analysis_result import AnalysisInput
from stmdomains.core.geometry import FrameGeometry, MoleculeGeometry


def measurement_refusal(record: MoleculeGeometry, settings: GeometryDomainSettings) -> str:
    if record.reason in ('outside_field', 'suppressed_duplicate'):
        return record.reason
    if record.status != 'lattice_2d' or len(record.axes) != 2:
        return 'geometry_not_2d'
    if any(not all(isfinite(v) for v in (a.row_angle_deg, a.period, a.coherence))
           or a.period <= 0 for a in record.axes):
        return 'geometry_invalid'
    if record.local_count < settings.minimum_local_count or record.effective_count < 8:
        return 'geometry_low_support'
    if min(a.coherence for a in record.axes) < settings.minimum_coherence:
        return 'geometry_low_quality'
    return ''



def validate_measurement(data: AnalysisInput, geometry: FrameGeometry) -> str:
    if data.frame.image.size > 4194304 or len(data.annotations.detections) > 3000:
        raise ValueError('Przekroczono limit zasobów analizy geometrii.')
    fingerprint = input_fingerprint(data)
    if ((geometry.series_id, geometry.working_index, geometry.source_index) !=
            (data.series_id, data.frame.working_index, data.frame.source_index)
            or geometry.metadata.get('input_sha256') != fingerprint
            or set(geometry.molecules) != {d.detection_id for d in data.annotations.detections}
            or any(geometry.molecules[d.detection_id].center_xy != d.center_xy for d in data.annotations.detections)):
        raise ValueError('Pomiary geometrii nie odpowiadają bieżącym danym. Pomierz ponownie.')
    return fingerprint
