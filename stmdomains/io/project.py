"""Read and save one self-contained STM Domains work document."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import zipfile

from nanotrack.io.mpp_loader import load_mpp_sequence
from stmdomains.core.immutable import plain_metadata
from stmdomains.core.project import ProjectSnapshot
from stmdomains.io.moltrack_import import _series_from_source
from stmdomains.io.project_validation import validate_project_state
from stmdomains.io.project_results import save_analysis, load_analysis
from stmdomains.io.project_archive import (ProjectCancelled, ProjectError, atomic_archive, checkpoint,
    extract_checked, json_bytes, put_bytes, put_source, read_json)


def save_project(path: Path, snapshot: ProjectSnapshot, *, cancelled: Callable[[], bool] = lambda: False,
                 progress: Callable[[str], None] = lambda text: None) -> None:
    target = Path(path).resolve()
    series = snapshot.series
    if target in (series.source_path.resolve(), series.session_path.resolve()) and target.suffix.lower() != '.stmdomains':
        raise ProjectError('Nie można nadpisać źródłowego MPP ani zapisu wejściowego.')
    def check() -> None:
        checkpoint(cancelled)
    check()
    validate_project_state(snapshot.view, snapshot.draft, series.frame_count)
    payload = {key: series.raw_payload[key] for key in ('schema_version', 'source', 'working_series',
               'registration', 'molecular_detections', 'molecular_segmentations', 'ui') if key in series.raw_payload}
    record: dict = {'source_frame_indices': series.source_frame_indices, 'diagnostics': series.diagnostics,
              'frame_keys': [f'{series.source_sha256}:{index}' for index in series.source_frame_indices],
              'provenance': series.provenance, 'view': plain_metadata(snapshot.view),
              'draft': plain_metadata(snapshot.draft), 'analysis': None}
    with atomic_archive(target, check) as archive:
        entries: dict = {}
        progress('Kopiowanie oryginalnego MPP…')
        put_source(archive, entries, series.source_path, series.source_sha256, check)
        put_bytes(archive, entries, 'input.json', json.dumps(payload, ensure_ascii=False).encode())
        if snapshot.analysis is not None:
            progress("Zapisywanie wybranego wyniku…")
            record["analysis"] = save_analysis(archive, entries, snapshot.analysis, series, check)
        put_bytes(archive, entries, 'project.json', json_bytes(record))
        put_bytes(archive, {}, 'manifest.json', json_bytes({
            'format': 'stmdomains', 'version': 1, 'application': 'STM Domains SD-V4-13',
            'saved_at': datetime.now(timezone.utc).isoformat(), 'entries': entries,
        }))
        check()
    progress('Zapisano projekt.')


def open_project(path: Path, *, cancelled: Callable[[], bool] = lambda: False,
                 progress: Callable[[str], None] = lambda text: None) -> ProjectSnapshot:
    path = Path(path).resolve()
    cache = TemporaryDirectory(prefix='stmdomains-project-')
    def check() -> None:
        checkpoint(cancelled)
    try:
        check()
        progress('Weryfikacja integralności projektu…')
        root = Path(cache.name)
        manifest = extract_checked(path, root, check)
        payload, record = read_json(root / 'input.json'), read_json(root / 'project.json')
        source = root / 'source.mpp'
        progress('Odczyt osadzonego MPP…')
        sequence = load_mpp_sequence(str(source), reverse_frame_order=False)
        check()
        series = _series_from_source(path, source, payload, sequence)
        indices = record['source_frame_indices']
        if (indices != payload['working_series']['source_frame_indices'] or not indices or
                any(type(i) is not int or not 0 <= i < len(sequence.raw_frames) for i in indices) or
                len(set(indices)) != len(indices)):
            raise ProjectError('Niezgodna mapa klatek projektu.')
        source_hash = manifest['entries']['source.mpp']['sha256']
        if (record['frame_keys'] != [f'{source_hash}:{index}' for index in indices] or
                record['provenance'].get('source_sha256_at_import') != source_hash):
            raise ProjectError('Niezgodna tożsamość źródła lub klatek projektu.')
        series = replace(series, source_cache=cache, source_sha256=manifest['entries']['source.mpp']['sha256'],
                         diagnostics=tuple(record['diagnostics']), provenance=record['provenance'])
        check()
        validate_project_state(record['view'], record['draft'], series.frame_count)
        analysis = load_analysis(record['analysis'], root, series, manifest['entries'], check)
        return ProjectSnapshot(series, record['view'], record['draft'], analysis)
    except ProjectCancelled:
        cache.cleanup()
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, zipfile.BadZipFile) as error:
        cache.cleanup()
        raise ProjectError(f'Nie można otworzyć projektu: {error}') from error
