"""Partition existing domain support without growing it or drawing bridges."""

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree
from scipy import ndimage as ndi

from stmdomains.core.analysis_result import MoleculeAssignment
from stmdomains.core.annotations import Detection


def split_labels(labels: NDArray[np.int32] | None, detections: tuple[Detection, ...],
                 assignments: Mapping[str, MoleculeAssignment], source: int, target: int,
                 selected: set[str]) -> NDArray[np.int32] | None:
    """Each existing source pixel follows its nearest source member in raw px.

    Both children inherit support, even a single member's cell. A point-only
    parent remains point-only. Other domains and empty space are unchanged.
    """
    if labels is None:
        return None
    result = labels.copy()
    members = sorted((d for d in detections if assignments[d.detection_id].domain_local_id == source),
                     key=lambda d: d.detection_id)
    tree = cKDTree([d.center_xy for d in members])
    values = np.asarray([target if d.detection_id in selected else source for d in members], dtype=np.int32)
    yy, xx = np.nonzero(labels == source)
    for start in range(0, len(xx), 65536):
        rows, columns = yy[start:start+65536], xx[start:start+65536]
        nearest = tree.query(np.column_stack((columns, rows)))[1]
        result[rows, columns] = values[nearest]
    return result


def merge_labels(labels: NDArray[np.int32] | None, domains: set[int], target: int,
                 detections: tuple[Detection, ...], assignments: Mapping[str, MoleculeAssignment]) -> NDArray[np.int32]:
    """The unmodified union must be one 8-connected supported component."""
    if labels is None or not domains <= set(np.unique(labels)):
        raise ValueError('Nie można połączyć: co najmniej jedna domena nie ma obszaru wspierającego jej członków.')
    union = np.isin(labels, sorted(domains))
    components = np.zeros(labels.shape, np.int32)
    count = ndi.label(union, structure=np.ones((3, 3), dtype=bool), output=components)
    if count != 1:
        raise ValueError('Nie można połączyć: obszary rozdziela przerwa lub mają rozłączne fragmenty. '
                         'Scalenie nie dorysowuje mostu przez przerwę.')
    height, width = labels.shape
    for detection in detections:
        domain = assignments[detection.detection_id].domain_local_id
        if domain in domains:
            x, y = np.rint(detection.center_xy).astype(int)
            x, y = np.clip(x, 0, width - 1), np.clip(y, 0, height - 1)
            if labels[y, x] != domain:
                raise ValueError('Nie można połączyć: obszar nie wspiera wszystkich centrów wybranych domen.')
    result = labels.copy()
    result[union] = target
    return result
