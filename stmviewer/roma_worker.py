"""Standalone RoMa process. Invoked by absolute Python -I -B, never imported by Qt."""

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any
import urllib.request

VERSION = 1
WEIGHTS_SHA256 = '1557dec0d21b62366465f7ff4d5fdf228cc695d0582e196ad2b80e05230828b7'
ROMA_SHA256 = '198779ceb8d2a02e112c2f346456c37477f7bc3ac61dff3d19aec58038d2ab21'
DINO_SHA256 = '28b1bf84669bdc32c4491c4296a98a3dbfd0a4a9b082514f0ae7f2d6541abc26'
DINO_COMMIT = 'adc254450203739c8149213a7a69d8d905b4fcfa'
WEIGHTS_URL = 'https://github.com/Parskatt/RoMaV2/releases/download/v2.0.1/romav2.0.1.pt'


def _source_digest(root: Path, *, package: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*.py')):
        digest.update(path.relative_to(root.parent if package else root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def _blocked(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError('RoMa v2 działa offline; połączenie sieciowe jest zabronione.')


def _peak_rss_mib() -> float:
    if sys.platform == 'win32':
        # Windows peak working set, avoiding an optional psutil dependency.
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return float(counters.PeakWorkingSetSize / 2 ** 20)
        return 0.
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(value / (2 ** 20 if sys.platform == 'darwin' else 1024))


class Worker:
    def __init__(self, config: dict[str, Any], report: Any) -> None:
        self.config = config
        requested = config['device']
        if requested not in ('cpu', 'cuda', 'auto'):
            raise ValueError('Nieprawidłowe urządzenie RoMa.')
        if requested == 'cpu':
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
        if config['preset'] not in ('turbo', 'fast', 'base', 'precise'):
            raise ValueError('Nieprawidłowy preset RoMa.')
        if (type(config['samples']) is not int or not 8 <= config['samples'] <= 10000
                or type(config['seed']) is not int or not 0 <= config['seed'] <= 2 ** 31 - 1):
            raise ValueError('Nieprawidłowe parametry próbkowania RoMa.')
        report('RoMa v2: sprawdzanie lokalnego kodu i bibliotek')
        source, weights = Path(config['source']), Path(config['weights'])
        spec = util.find_spec('romav2')
        if spec is None or spec.origin is None or metadata.version('romav2') != '2.0.1':
            raise ValueError('Brak wymaganego pakietu romav2==2.0.1 w wybranym interpreterze.')
        if _source_digest(Path(spec.origin).parent, package=True) != ROMA_SHA256:
            raise ValueError('Niezgodna suma kodu pakietu RoMa v2.')
        if _source_digest(source) != DINO_SHA256:
            raise ValueError('Niezgodny kod DINOv3; wymagany commit ' + DINO_COMMIT)
        report('RoMa v2: sprawdzanie SHA-256 wag')
        with weights.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != WEIGHTS_SHA256:
                raise ValueError('Niezgodna suma SHA-256 wag RoMa v2.')
        socket.socket.connect = _blocked  # type: ignore[method-assign]
        socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
        urllib.request.urlopen = _blocked
        urllib.request.urlretrieve = _blocked
        import torch
        self.torch = torch
        torch.set_num_threads(4)
        torch.manual_seed(config['seed'])
        torch.set_float32_matmul_precision('highest')
        device = 'cuda' if requested == 'auto' and torch.cuda.is_available() else requested
        if device == 'auto':
            device = 'cpu'
        if device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA jest niedostępna w środowisku RoMa.')
        original_load = torch.hub.load

        def checkpoint(url: str, *args: Any, **kwargs: Any) -> Any:
            if url != WEIGHTS_URL:
                raise ValueError('Nieoczekiwane wagi żądane przez RoMa.')
            return torch.load(weights, map_location='cpu', weights_only=True, mmap=True)

        def backbone(repo_or_dir: str, model: str, *args: Any, **kwargs: Any) -> Any:
            if (repo_or_dir != 'facebookresearch/dinov3:' + DINO_COMMIT or model != 'dinov3_vitl16'
                    or kwargs.get('pretrained') is not False):
                raise ValueError('Nieoczekiwany model DINOv3.')
            return original_load(str(source), model, source='local', pretrained=False)

        torch.hub.load_state_dict_from_url = checkpoint
        torch.hub.load = backbone
        torch.hub.download_url_to_file = _blocked
        report('RoMa v2: ładowanie modelu na ' + device.upper())
        from importlib import import_module
        roma = import_module('romav2')
        started = time.monotonic()
        self.model = roma.RoMaV2(roma.RoMaV2.Cfg(setting=config['preset']))
        self.load_s = time.monotonic() - started
        actual = str(next(self.model.parameters()).device)
        if actual.split(':')[0] != device:
            raise ValueError('RoMa uruchomiło się na innym urządzeniu niż wskazane: ' + actual)
        self.device = ('CUDA:0 — ' + torch.cuda.get_device_name() if device == 'cuda' else 'CPU')
        self.provenance = {
            'model': 'RoMa v2', 'source_path': str(source.resolve()), 'source_commit': DINO_COMMIT,
            'source_sha256': DINO_SHA256, 'roma_source_sha256': ROMA_SHA256,
            'source_license': 'RoMa MIT; DINOv3 custom license',
            'weights_path': str(weights.resolve()), 'weights_sha256': WEIGHTS_SHA256,
            'weights_variant': 'romav2.0.1.pt', 'requested_device': requested,
            'actual_device': self.device, 'interpreter_path': sys.executable,
            'preset': config['preset'], 'samples': str(config['samples']), 'seed': str(config['seed']),
            'sampling': 'roma-density-balanced-v1; dual-grid8x8-cap-v1',
            'sampling_version': '1', 'spatial_cell_cap': str(max(1, (config['samples'] + 63) // 64)),
            'precision': 'RoMa defaults: FP32 parameters, BF16 AMP',
            'model_config': 'RoMaV2.Cfg; eval; compile=False',
            'preprocessing': 'minmax-float32-rgb-v1; bicubic antialias align_corners=False; no padding',
            'model_low_shape': f'{self.model.H_lr}x{self.model.W_lr}',
            'model_high_shape': f'{self.model.H_hr}x{self.model.W_hr}',
            'aggregation': 'translation-consensus-v2',
        }
        for name in ('romav2', 'torch', 'torchvision', 'numpy', 'einops', 'pillow', 'rich', 'tqdm'):
            self.provenance['library_' + name] = metadata.version(name)
        try:
            self.provenance['library_fused-local-corr'] = metadata.version('fused-local-corr')
        except metadata.PackageNotFoundError:
            self.provenance['library_fused-local-corr'] = 'unavailable'

    def match(self, root: Path) -> dict[str, Any]:
        import numpy as np
        reference = np.load(root / 'reference.npy', allow_pickle=False)
        moving = np.load(root / 'moving.npy', allow_pickle=False)
        for array in (reference, moving):
            if (array.ndim != 2 or min(array.shape) < 1 or array.dtype != np.float32
                    or not np.isfinite(array).all() or array.min() < 0 or array.max() > 1):
                raise ValueError('Nieprawidłowy obraz wejściowy RoMa.')
        torch = self.torch
        torch.manual_seed(self.config['seed'])
        if self.device.startswith('CUDA'):
            torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        prediction = self.model.match(np.repeat(reference[..., None], 3, axis=2),
                                      np.repeat(moving[..., None], 3, axis=2))
        matches, _, _, _ = self.model.sample(prediction, self.config['samples'])
        points = matches.detach().cpu().numpy().astype(np.float64)
        metrics = {'inference_s': time.monotonic() - started, 'model_load_s': self.load_s,
                   'worker_peak_rss_mib': _peak_rss_mib(),
                   'cuda_peak_allocated_mib': (torch.cuda.max_memory_allocated() / 2 ** 20
                                               if self.device.startswith('CUDA') else 0.)}
        del prediction, matches
        np.savez(root / 'points.npz', reference=points[:, :2], moving=points[:, 2:])
        return {'kind': 'matched', 'reference_shape': list(reference.shape),
                'moving_shape': list(moving.shape), 'metrics': metrics}


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    worker: Worker | None = None
    output = sys.stdout
    for line in sys.stdin:
        sequence = 0
        try:
            if len(line) > 65536:
                raise ValueError('Zbyt duży komunikat wejściowy.')
            request = json.loads(line)
            if request.get('version') != VERSION or type(request.get('id')) is not int:
                raise ValueError('Niezgodny protokół RoMa.')
            sequence = request['id']

            def send(value: dict[str, Any]) -> None:
                output.write(json.dumps({'version': VERSION, 'id': sequence, **value}, allow_nan=False) + '\n')
                output.flush()

            with redirect_stdout(sys.stderr):
                if request['kind'] == 'initialize' and worker is None:
                    worker = Worker(request['configuration'], lambda message: send({'kind': 'progress', 'message': message}))
                    response = {'kind': 'ready', 'device': worker.device, 'provenance': worker.provenance}
                elif request['kind'] == 'match' and worker is not None:
                    response = worker.match(root)
                else:
                    raise ValueError('Nieprawidłowe polecenie RoMa.')
            send(response)
        except Exception as error:
            output.write(json.dumps({'version': VERSION, 'id': sequence, 'kind': 'error',
                                            'message': str(error) or type(error).__name__}) + '\n')
            output.flush()
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
