"""Native runtime paths and portable historical source text in session metadata."""
from pathlib import Path


def native_path(source: str) -> Path:
    """A path is metadata on load; constructing it never accesses a source file."""
    return Path(source)


def _source(value: object) -> dict[str, object]:
    from stmviewer.metadata_values import source_provenance
    source = source_provenance(value)
    return {'source': str(native_path(source.source)), 'source_frame_index': source.source_frame_index}


def _items(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError('Sesja: nieprawidłowa lista historii źródeł.')
    return list(value)


def _history(value: object) -> dict[str, object]:
    from stmviewer.metadata_values import json_object
    record = json_object(value)
    baseline = []
    for item in _items(record.get('baseline')):
        frame = json_object(item)
        baseline.append({**frame, 'source': _source(frame.get('source'))})
    corrections = []
    for item in _items(record.get('corrections')):
        correction = json_object(item)
        corrections.append({**correction, 'reference': _source(correction.get('reference')),
                            'moving': _source(correction.get('moving'))})
    return {**record, 'baseline': baseline, 'corrections': corrections}


def _alignment(value: object, active_index: int | None, *, current: bool = False,
               depth: int = 0) -> dict[str, object] | None:
    from stmviewer.metadata_values import json_object
    if value is None:
        return None
    if depth >= 32:
        raise ValueError('Historia rejestracji przekracza 32 etapy.')
    record = json_object(value)
    if current or (active_index is not None and record.get('manual_result') == active_index):
        record['reference'] = _source(record.get('reference'))
    if 'previous' in record:
        record['previous'] = _alignment(record['previous'], active_index, depth=depth + 1)
    return record


def _frames(value: object, active_index: int | None, *, current: bool = False) -> list[dict[str, object]]:
    from stmviewer.metadata_values import json_object
    records = []
    for item in _items(value):
        record = json_object(item)
        records.append({**record, 'alignment': _alignment(record['alignment'], active_index, current=current)})
    return records


def normalize_active_sources(root: dict[str, object]) -> dict[str, object]:
    """Adapt runtime identities to native pathlib while retaining historical provenance.

    Windows changes POSIX separators when constructing a Path. The active manual
    baseline must use that same spelling, because later editing identifies frames
    by str(frame.source). Prior imported histories and frame.provenance remain text.
    The caller's manifest is never mutated.
    """
    from stmviewer.metadata_values import json_object
    if root['registration'] is None:
        return root
    registration = json_object(root['registration'])
    histories = _items(root['manual_histories'])
    index = registration.get('manual_state')
    active_index = index if type(index) is int and 0 <= index < len(histories) else None
    if active_index is not None:
        histories[active_index] = _history(histories[active_index])
    registration['reference'] = _source(registration.get('reference'))
    registration['frames'] = _frames(registration.get('frames'), active_index, current=True)
    registration['image_alignments'] = [
        _alignment(item, active_index) for item in _items(registration.get('image_alignments'))
    ]
    return {**root, 'registration': registration, 'manual_histories': histories,
            'frames': _frames(root['frames'], active_index)}
