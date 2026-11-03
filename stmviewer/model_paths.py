"""Find complete local model layouts without scanning disks or executing code."""
from __future__ import annotations

import os
from pathlib import Path
import sys

# These marker files only locate a layout. Model loaders still verify code/weights.
_MODEL_FILES = {
    'loftr': ('weights/loftr_outdoor.ckpt',),
    'efficientloftr': ('source/src/loftr/loftr.py', 'weights/eloftr_outdoor.ckpt'),
    'lightglue': ('source/lightglue/__init__.py', 'weights/superpoint_lightglue.pth',
                  'weights/superpoint_v1.pth'),
    'matchanything': ('source/src/loftr/loftr.py', 'weights/matchanything_eloftr.ckpt'),
    'romav2': ('dinov3/hubconf.py', 'dinov3/dinov3/__init__.py', 'weights/romav2.0.1.pt'),
}
_ROMA_ENV_NAMES = ('stmviewer-roma', 'netcat-romav2')


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def find_model_root(name: str) -> Path | None:
    """Prefer the running application's bundle, then the user's existing cache."""
    roots = (Path(__file__).resolve().parent.parent / 'models' / name,
             Path.home() / '.cache' / 'stmviewer' / name)
    for root in roots:
        if all(_is_file(root / relative) for relative in _MODEL_FILES[name]):
            return root
    return None


def default_model_root(name: str) -> Path:
    """Keep the historical editable cache suggestion when no complete layout exists."""
    return find_model_root(name) or Path.home() / '.cache' / 'stmviewer' / name


def default_loftr_weights() -> Path | None:
    """An explicitly configured path wins even if missing; do not silently replace it."""
    explicit = os.environ.get('STMVIEWER_LOFTR_WEIGHTS', '').strip()
    if explicit:
        return Path(explicit).expanduser()
    root = find_model_root('loftr')
    return root / 'weights/loftr_outdoor.ckpt' if root is not None else None


def _registered_environments(home: Path) -> list[Path]:
    try:
        lines = (home / '.conda' / 'environments.txt').read_text(encoding='utf-8-sig').splitlines()
    except (OSError, UnicodeError):
        return []
    return [path for line in lines if line.strip()
            and (path := Path(line.strip())).is_absolute()
            and path.name.casefold() in _ROMA_ENV_NAMES]


def default_roma_interpreter() -> Path:
    """Inspect named conda environments only; never run Python to discover its packages."""
    home, prefix = Path.home(), Path(sys.prefix)
    env_dirs = []
    if prefix.parent.name.casefold() == 'envs':
        env_dirs.append(prefix.parent)
    env_dirs.extend(home / installation / 'envs'
                    for installation in ('miniforge3', 'miniconda3', 'anaconda3', '.conda'))
    registered = _registered_environments(home)
    suffix = 'python.exe' if sys.platform == 'win32' else 'bin/python'
    for name in _ROMA_ENV_NAMES:
        candidates = [directory / name for directory in env_dirs]
        candidates.extend(path for path in registered if path.name.casefold() == name)
        for candidate in dict.fromkeys(candidates):
            if candidate.resolve() != prefix.resolve() and _is_file(candidate / suffix):
                return candidate / suffix
    # Missing environments remain visible as an editable suggestion, as before.
    return home / 'miniconda3' / 'envs' / 'netcat-romav2' / suffix
