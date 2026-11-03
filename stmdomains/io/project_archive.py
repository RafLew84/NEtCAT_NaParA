"""Atomic, checksummed containers; never execute objects or extract arbitrary paths."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import zipfile

MAX_JSON = 64 * 1024**2
MAX_TOTAL = 16 * 1024**3
BLOCK = 1024 * 1024


class ProjectError(ValueError):
    pass


class ProjectCancelled(Exception):
    pass


def checkpoint(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise ProjectCancelled()


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')


def read_json(path: Path) -> Any:
    if path.stat().st_size > MAX_JSON:
        raise ProjectError('Przekroczono limit metadanych projektu (64 MiB).')
    return json.loads(path.read_bytes())


@contextmanager
def atomic_archive(target: Path, check: Callable[[], None]) -> Iterator[zipfile.ZipFile]:
    handle, temporary = tempfile.mkstemp(prefix='.' + target.name + '-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(handle, 'w+b') as stream:
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
                yield archive
            stream.flush()
            os.fsync(stream.fileno())
        check()
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def put_bytes(archive: zipfile.ZipFile, entries: dict, name: str, content: bytes) -> None:
    if name.endswith('.json') and len(content) > MAX_JSON:
        raise ProjectError('Przekroczono limit metadanych projektu (64 MiB).')
    if sum(item['size'] for item in entries.values()) + len(content) > MAX_TOTAL:
        raise ProjectError('Projekt przekracza limit 16 GiB.')
    archive.writestr(name, content)
    entries[name] = {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}


def put_source(archive: zipfile.ZipFile, entries: dict, path: Path, expected: str, check: Callable[[], None]) -> None:
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as source, archive.open('source.mpp', 'w', force_zip64=True) as destination:
        while chunk := source.read(BLOCK):
            check()
            count += len(chunk)
            if count > MAX_TOTAL:
                raise ProjectError('MPP przekracza limit projektu 16 GiB.')
            destination.write(chunk)
            digest.update(chunk)
    if not expected or digest.hexdigest() != expected:
        raise ProjectError('MPP zmienił się od importu. Poprzedni projekt pozostaje zachowany; otwórz źródło ponownie.')
    entries['source.mpp'] = {'size': count, 'sha256': digest.hexdigest()}


def extract_checked(path: Path, directory: Path, check: Callable[[], None]) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or 'manifest.json' not in names or len(names) > 50000:
            raise ProjectError('Niepoprawna lista części projektu.')
        if archive.getinfo('manifest.json').file_size > MAX_JSON:
            raise ProjectError('Manifest projektu jest zbyt duży.')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 'stmdomains' or type(manifest.get('version')) is not int or manifest['version'] != 1:
            raise ProjectError('Nieobsługiwana wersja formatu STM Domains.')
        entries = manifest['entries']
        if set(entries) != set(names) - {'manifest.json'} or not {'source.mpp', 'input.json', 'project.json'} <= set(entries):
            raise ProjectError('Brak wymaganych części projektu lub niezgodny manifest.')
        if sum(info.file_size for info in archive.infolist()) > MAX_TOTAL:
            raise ProjectError('Projekt przekracza limit 16 GiB.')
        pattern = r'(source\.mpp|input\.json|project\.json|catalogues/[0-9a-f]{64}\.json|frames/[0-9]+\.(json|npy))'
        for name, entry in entries.items():
            check()
            if not re.fullmatch(pattern, name) or archive.getinfo(name).file_size != entry['size']:
                raise ProjectError('Niepoprawna nazwa lub rozmiar części projektu.')
            if name.endswith('.json') and entry['size'] > MAX_JSON:
                raise ProjectError('Przekroczono limit metadanych projektu (64 MiB).')
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(name) as source, target.open('wb') as output:
                while chunk := source.read(BLOCK):
                    check()
                    output.write(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != entry['sha256']:
                raise ProjectError(f'Niezgodna suma kontrolna: {name}.')
        return manifest
