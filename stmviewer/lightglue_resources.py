"""Pinned public LightGlue/SuperPoint artifacts and auditable input contract."""

from collections.abc import Callable
import hashlib
from pathlib import Path

SOURCE_COMMIT = '5a650c444718caffc2669dc0094cde908f42dd73'
SOURCE_SHA256 = '31a9fe6f54373931339e8eb3d69931bc590768f2377ecc2e15213fec0a142d44'
MATCHER_SHA256 = '6ff7040d0a497fc6639337946d7538dae07428c18f77a067a0b5a960e7cc551a'
EXTRACTOR_SHA256 = '52b6708629640ca883673b5d5c097c4ddad37d8048b33f09c8ca0d69db12c40e'
MATCHER_BYTES = 47500279
EXTRACTOR_BYTES = 5206086
MAX_KEYPOINTS = 2048
EXTRACTOR_CONFIG = ('SuperPoint; max_num_keypoints=2048; detection_threshold=0.0005; '
                    'nms_radius=4; remove_borders=4; descriptor_dim=256')
MODEL_CONFIG = ('LightGlue; features=superpoint; n_layers=9; filter_threshold=0.1; '
                'depth_confidence=0.95; width_confidence=0.99; flash=True; mp=False; compile=False')
PREPROCESSING = 'minmax-float32-v1; native; no padding'
COORDINATE_MAPPING = 'upstream-original-pixels; resize=None'
PRECISION = 'FP32 parameters/input; FlashAttention FP16 on CUDA; mp=False'


def validate_resources(source: Path, weights: Path, extractor_weights: Path,
                       report: Callable[[str], None]) -> None:
    """Verify the complete pinned source and both checkpoints before loading code."""
    digest = hashlib.sha256()
    for file in sorted((path for path in source.rglob('*') if path.is_file()
                        and '__pycache__' not in path.parts and '.git' not in path.parts),
                       key=lambda path: path.relative_to(source).as_posix()):
        report('LightGlue + SuperPoint: sprawdzanie kodu')
        relative = file.relative_to(source).as_posix()
        with file.open('rb') as stream:
            file_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        digest.update(f'{file_digest}  {relative}\n'.encode('utf-8'))
    if digest.hexdigest() != SOURCE_SHA256:
        raise ValueError(f'Niezgodny kod LightGlue; wymagany commit {SOURCE_COMMIT}.')
    for path, expected, label in ((weights, MATCHER_SHA256, 'LightGlue'),
                                  (extractor_weights, EXTRACTOR_SHA256, 'SuperPoint')):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                report(f'LightGlue + SuperPoint: sprawdzanie SHA-256 wag {label}')
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError(f'Niezgodna suma SHA-256 wag {label}.')
