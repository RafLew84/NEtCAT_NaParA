"""Standalone local-only SuperPoint/LightGlue worker, isolated from GUI Torch state."""

from __future__ import annotations

from contextlib import redirect_stdout
from importlib import metadata
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any, Callable
import urllib.request

# -I excludes the script directory. Only our installed checkout is added here;
# the separately verified upstream source is added after hash validation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stmviewer.lightglue_resources import (
    COORDINATE_MAPPING, EXTRACTOR_CONFIG, EXTRACTOR_SHA256, MATCHER_SHA256,
    MAX_KEYPOINTS, MODEL_CONFIG, PRECISION, PREPROCESSING, SOURCE_COMMIT,
    SOURCE_SHA256, validate_resources,
)
from stmviewer.method_parameters import LightGlueParameters, decode_profile
from stmviewer.feature_provenance import lightglue_identity
from dataclasses import asdict
from stmviewer.roma_worker import _peak_rss_mib

VERSION = 1
URL_BASE = 'https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv/'


def _blocked(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError('LightGlue + SuperPoint działa offline; połączenie sieciowe jest zabronione.')


class Worker:
    def __init__(self, config: dict[str, Any], report: Callable[[str], None]) -> None:
        requested = config['device']
        parameters = decode_profile('lightglue_superpoint', config.get('parameters', asdict(LightGlueParameters())))
        assert isinstance(parameters, LightGlueParameters)
        if requested not in ('cpu', 'cuda', 'auto') or config.get('samples') != parameters.max_keypoints:
            raise ValueError('Nieprawidłowa konfiguracja LightGlue + SuperPoint.')
        if requested == 'cpu':
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        source, weights, extractor_weights = (Path(config[name]) for name in
                                              ('source', 'weights', 'extractor_weights'))
        validate_resources(source, weights, extractor_weights, report)
        socket.socket.connect = _blocked  # type: ignore[method-assign]
        socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
        socket.create_connection = _blocked
        urllib.request.urlopen = _blocked
        urllib.request.urlretrieve = _blocked
        report('LightGlue + SuperPoint: sprawdzanie bibliotek i urządzenia')
        import torch
        self.torch = torch
        torch.set_num_threads(4)
        torch.manual_seed(20261102)
        torch.set_float32_matmul_precision('highest')
        device = 'cuda' if requested == 'auto' and torch.cuda.is_available() else requested
        if device == 'auto':
            device = 'cpu'
        if device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA jest niedostępna w środowisku LightGlue + SuperPoint.')
        self._device = device
        self.device = 'CUDA:0 — ' + torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'
        files = {URL_BASE + 'superpoint_v1.pth': extractor_weights,
                 URL_BASE + 'superpoint_lightglue.pth': weights}

        def checkpoint(url: str, *args: Any, **kwargs: Any) -> Any:
            if url not in files:
                raise ValueError('Nieoczekiwany checkpoint żądany przez LightGlue + SuperPoint.')
            return torch.load(files[url], map_location='cpu', weights_only=True)

        torch.hub.load_state_dict_from_url = checkpoint
        torch.hub.load = _blocked
        torch.hub.download_url_to_file = _blocked
        sys.path.insert(0, str(source))
        from importlib import import_module
        upstream = import_module('lightglue')
        self.rbd = import_module('lightglue.utils').rbd
        report('LightGlue + SuperPoint: wczytywanie obu lokalnych checkpointów')
        started = time.monotonic()
        self.extractor = upstream.SuperPoint(
            max_num_keypoints=parameters.max_keypoints, detection_threshold=parameters.detection_threshold,
            nms_radius=parameters.nms_radius).eval()
        depth, width = parameters.adaptive_thresholds
        self.matcher = upstream.LightGlue(
            features='superpoint', flash=True, mp=False, filter_threshold=parameters.filter_threshold,
            depth_confidence=depth, width_confidence=width).eval()
        self._validate_state(weights, extractor_weights)
        self.extractor = self.extractor.to(device)
        self.matcher = self.matcher.to(device)
        if device == 'cuda':
            torch.cuda.synchronize()
        self.load_s = time.monotonic() - started
        self.provenance = {
            'model': 'LightGlue + SuperPoint', 'source_path': str(source.resolve()),
            'source_commit': SOURCE_COMMIT, 'source_sha256': SOURCE_SHA256,
            'source_license': 'LightGlue Apache-2.0; SuperPoint separate research license',
            'weights_path': str(weights.resolve()), 'weights_sha256': MATCHER_SHA256,
            'weights_variant': 'superpoint_lightglue.pth', 'weights_license': 'Apache-2.0',
            'extractor_weights_path': str(extractor_weights.resolve()),
            'extractor_weights_sha256': EXTRACTOR_SHA256, 'extractor_weights_variant': 'superpoint_v1.pth',
            'extractor_weights_license': 'SuperPoint noncommercial internal research license',
            'requested_device': requested, 'actual_device': self.device, 'interpreter_path': sys.executable,
            'extractor_config': EXTRACTOR_CONFIG, 'model_config': MODEL_CONFIG,
            'max_keypoints': str(MAX_KEYPOINTS), 'coordinate_mapping': COORDINATE_MAPPING,
            'preprocessing': PREPROCESSING, 'aggregation': 'translation-consensus-v2', 'precision': PRECISION,
            'runtime': 'isolated same-interpreter process; local-only; eval; compile=False',
            'checkpoint_compatibility': 'legacy attention names; ignore exact log_assignment.0-8.r=[1]; generated confidence_thresholds; strict current state',
        }
        self.provenance.update(lightglue_identity(parameters))
        for name in ('torch', 'torchvision', 'numpy', 'kornia', 'opencv-python', 'matplotlib'):
            self.provenance['library_' + name] = metadata.version(name)
        report('LightGlue + SuperPoint: model gotowy na ' + self.device)

    def _validate_state(self, weights: Path, extractor_weights: Path) -> None:
        """Validate all learned tensors, not just upstream's permissive strict=False."""
        torch = self.torch
        self.extractor.load_state_dict(torch.load(extractor_weights, map_location='cpu', weights_only=True), strict=True)
        state = torch.load(weights, map_location='cpu', weights_only=True)
        if not isinstance(state, dict):
            raise ValueError('Nieprawidłowy checkpoint LightGlue.')
        for i in range(self.matcher.conf.n_layers):
            state = {k.replace(f'self_attn.{i}', f'transformers.{i}.self_attn'): v for k, v in state.items()}
            state = {k.replace(f'cross_attn.{i}', f'transformers.{i}.cross_attn'): v for k, v in state.items()}
        expected = self.matcher.state_dict()
        missing, extra = set(expected) - set(state), set(state) - set(expected)
        if extra != {f'log_assignment.{i}.r' for i in range(9)} or missing != {'confidence_thresholds'}:
            raise ValueError('Niezgodny zestaw parametrów checkpointu LightGlue.')
        for key in extra:
            if state[key].dtype != torch.float32 or not torch.equal(state[key], torch.ones(1)):
                raise ValueError('Niezgodna historyczna stała checkpointu LightGlue.')
            del state[key]
        if set(dict(self.matcher.named_parameters())) - set(state):
            raise ValueError('Brak uczonych parametrów LightGlue.')
        for key, value in state.items():
            if value.dtype != expected[key].dtype or not torch.equal(expected[key], value):
                raise ValueError('Niepełne wczytanie parametrów LightGlue.')
        state['confidence_thresholds'] = expected['confidence_thresholds']
        self.matcher.load_state_dict(state, strict=True)

    def match(self, root: Path) -> dict[str, Any]:
        import numpy as np
        reference = np.load(root / 'reference.npy', allow_pickle=False)
        moving = np.load(root / 'moving.npy', allow_pickle=False)
        for array in (reference, moving):
            if (array.ndim != 2 or min(array.shape) < 8 or array.dtype != np.float32
                    or not np.isfinite(array).all() or array.min() < 0 or array.max() > 1):
                raise ValueError('Nieprawidłowy obraz wejściowy LightGlue + SuperPoint.')
        torch = self.torch
        if self._device == 'cuda':
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        started = time.monotonic()
        with torch.inference_mode():
            inputs = [torch.from_numpy(image[None]).to(self._device) for image in (reference, moving)]
            features = [self.extractor.extract(image, resize=None) for image in inputs]
            if self._device == 'cuda':
                torch.cuda.synchronize()
            extraction_s = time.monotonic() - started
            match_start = time.monotonic()
            result = self.matcher({'image0': features[0], 'image1': features[1]})
            if self._device == 'cuda':
                torch.cuda.synchronize()
            matching_s = time.monotonic() - match_start
            first, second, result = [self.rbd(item) for item in (*features, result)]
            matches = result['matches']
            p0 = first['keypoints'][matches[:, 0]].cpu().numpy().astype(np.float64)
            p1 = second['keypoints'][matches[:, 1]].cpu().numpy().astype(np.float64)
        metrics = {'extraction_s': extraction_s, 'matching_s': matching_s,
                   'inference_s': time.monotonic() - started, 'model_load_s': self.load_s,
                   'worker_peak_rss_mib': _peak_rss_mib(),
                   'cuda_peak_allocated_mib': (torch.cuda.max_memory_allocated() / 2 ** 20
                                             if self._device == 'cuda' else 0.)}
        np.savez(root / 'points.npz', reference=p0, moving=p1)
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
                raise ValueError('Zbyt duży komunikat wejściowy LightGlue.')
            request = json.loads(line)
            if request.get('version') != VERSION or type(request.get('id')) is not int:
                raise ValueError('Niezgodny protokół LightGlue.')
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
                    raise ValueError('Nieprawidłowe polecenie LightGlue.')
            send(response)
        except Exception as error:
            output.write(json.dumps({'version': VERSION, 'id': sequence, 'kind': 'error',
                                     'message': str(error) or type(error).__name__}) + '\n')
            output.flush()
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
