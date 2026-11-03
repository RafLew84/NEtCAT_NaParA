"""Create disposable invalid sessions for the documented manual import checks."""
import argparse
import json
from pathlib import Path
import tempfile
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(tempfile.gettempdir()) / 'stmviewer-invalid-sessions')
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    damaged = output / 'damaged.stmsession'
    damaged.write_bytes(b'STM Viewer manual test: deliberately not a ZIP archive.\n')
    future = output / 'unsupported-version.stmsession'
    with zipfile.ZipFile(future, 'w') as archive:
        archive.writestr('manifest.json', json.dumps({
            'format': 'stmviewer-session', 'version': 999, 'state': {},
        }))
    print(f'Uszkodzony plik: {damaged.resolve()}')
    print(f'Nieobsługiwana wersja: {future.resolve()}')


if __name__ == '__main__':
    main()
