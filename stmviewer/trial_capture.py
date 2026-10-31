"""Bounded scalar records of registration attempts, independent of image storage."""

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING, Any

from stmviewer.frame import ImageFrame

if TYPE_CHECKING:
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.pair_comparison import PairTrial
    from stmviewer.registration import RegistrationResult
    from stmviewer.trial_document import TrialDocument


def _plain(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    return value


@lru_cache(maxsize=1)
def code_revision() -> str:
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parent,
            text=True, stderr=subprocess.DEVNULL, timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return 'unknown'


@lru_cache(maxsize=1)
def code_dirty() -> bool:
    try:
        return bool(subprocess.check_output(
            ['git', 'status', '--porcelain', '--', 'stmviewer'],
            cwd=Path(__file__).resolve().parent.parent, text=True,
            stderr=subprocess.DEVNULL, timeout=2,
        ).strip())
    except (OSError, subprocess.SubprocessError):
        return True


@lru_cache(maxsize=8)
def _weights_sha256(path: str, size: int, modified_ns: int, changed_ns: int) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def backend_settings(backend: object, options: 'DeepMatcherOptions | None', device: str) -> dict[str, Any]:
    """Record the actual local implementation's full settings, not just its label."""
    settings: dict[str, Any] = {'reference_strategy': 'adjacent', 'registration_view': 'raw'}
    config = getattr(backend, 'config', None)
    if is_dataclass(config) and not isinstance(config, type):
        settings['config'] = _plain(config)
    stages = getattr(backend, 'trial_settings', None)
    if stages is not None:
        settings.update(_plain(stages))
    if options is not None:
        settings.update(weights=str(options.weights), requested_device=options.device, actual_device=device)
        if options.weights is not None:
            try:
                path = options.weights.resolve()
                stat = path.stat()
                settings['weights_sha256'] = _weights_sha256(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                settings['weights_hash_status'] = 'captured_after_model_load'
            except OSError:
                settings['weights_hash_status'] = 'unavailable'

    return settings


def _record(index: int, *, shift: tuple[float, float] | None = None,
            cumulative: tuple[float, float] | None = None, status: str = 'failed',
            quality: float | None = None, inherited: bool = False,
            hybrid: object = None, local: object = None, manual: object = None,
            pair_status: str | None = None, pair_quality: float | None = None) -> dict[str, Any]:
    return {'index': index, 'shift_xy': _plain(shift), 'cumulative_xy': _plain(cumulative),
            'status': status, 'quality_score': quality, 'inherited_uncertainty': inherited,
            'hybrid': _plain(hybrid), 'local': _plain(local), 'manual': _plain(manual),
            'pair_status': pair_status, 'pair_quality_score': pair_quality}


class AttemptCapture:
    """Observe scalar milestones; never retain frames, a model, or rendered images."""

    def __init__(self, frames: tuple[ImageFrame, ...], method: str, *, kind: str = 'series',
                 reference_index: int = 0, moving_index: int | None = None) -> None:
        from stmviewer.registration import REGISTRATION_METHODS
        self._moving_index = moving_index if moving_index is not None else reference_index + 1
        self._active_index: int | None = None
        self.payload: dict[str, Any] = {
            'kind': kind, 'outcome': 'failed', 'method': method,
            'label': REGISTRATION_METHODS.get(method, method), 'settings_text': '',
            'settings': {}, 'device': 'unknown', 'error': 'Nie rozpoczęto obliczeń.',
            'frame_count': len(frames), 'reference_index': reference_index, 'records': [],
            'manual_movie': None, 'code_revision': code_revision(), 'code_dirty': code_dirty(),
        }

    @property
    def document(self) -> 'TrialDocument':
        from stmviewer.trial_document import TrialDocument
        return TrialDocument(deepcopy(self.payload))

    def requested(self, options: 'DeepMatcherOptions | None') -> None:
        if options is not None:
            self.payload['settings'].update(weights=str(options.weights), requested_device=options.device)
            self.payload['settings_text'] = str(self.payload['settings'])

    def configured(self, backend: object, options: 'DeepMatcherOptions | None', device: str) -> None:
        settings = backend_settings(backend, options, device)
        self.payload.update(settings=settings, device=device,
                            settings_text=getattr(backend, 'settings_text', str(settings)))

    def started(self, index: int) -> None:
        self._active_index = self._moving_index if self.payload['kind'] == 'pair' else index

    def reference(self) -> None:
        self.payload['records'] = [_record(0, cumulative=(0.0, 0.0), status='ok', quality=1.0)]

    def pair_done(self, index: int, shift: tuple[float, float], cumulative: tuple[float, float],
                  status: str, quality: float | None, inherited: bool, backend: object, *,
                  pair_status: str, pair_quality: float | None) -> None:
        from stmviewer.deep_ecc import DeepEccBackend
        from stmviewer.local_registration import DeepLocalBackend
        self.payload['records'].append(_record(
            index, shift=shift, cumulative=cumulative, status=status, quality=quality, inherited=inherited,
            hybrid=backend.last_diagnostics if isinstance(backend, DeepEccBackend) else None,
            local=backend.last_diagnostics if isinstance(backend, DeepLocalBackend) else None,
            pair_status=pair_status, pair_quality=pair_quality,
        ))
        self._active_index = None

    def pair_failed(self, error: BaseException, backend: object) -> None:
        from stmviewer.deep_ecc import DeepEccBackend
        from stmviewer.local_registration import DeepLocalBackend
        if self._active_index is None:
            return
        hybrid = backend.last_failure if isinstance(backend, DeepEccBackend) else None
        local = backend.last_diagnostics if isinstance(backend, DeepLocalBackend) else None
        from stmviewer.registration import RegistrationCancelled
        status = 'cancelled' if isinstance(error, RegistrationCancelled) else 'failed'
        self.payload['records'].append(_record(self._active_index, hybrid=hybrid, local=local,
                                               status=status, pair_status=status))
        self._active_index = None

    def failed(self, error: BaseException) -> None:
        from stmviewer.registration import RegistrationCancelled
        cancelled = isinstance(error, RegistrationCancelled)
        self.payload.update(outcome='cancelled' if cancelled else 'failed',
                            error='Anulowano próbę.' if cancelled else str(error) or type(error).__name__)
        if self._active_index is not None:
            self.payload['records'].append(_record(self._active_index, pair_status='cancelled' if cancelled else 'failed'))
            self._active_index = None

    def finish_registration(self, result: 'RegistrationResult') -> None:
        complete = from_registration(result).payload
        complete['method'] = self.payload['method']
        self.payload = complete

    def finish_pair(self, trial: 'PairTrial') -> None:
        self.payload.update(outcome='complete', error=None, method=trial.method, label=trial.label,
                            settings_text=trial.settings_text, device=trial.device)
        self.payload['records'] = [_record(
            self._moving_index, shift=trial.shift_xy, status=trial.status, quality=trial.quality_score,
            hybrid=trial.hybrid, local=trial.local, manual=trial.manual,
            pair_status=trial.status, pair_quality=trial.quality_score,
        )]
        self._active_index = None


def from_registration(result: 'RegistrationResult') -> 'TrialDocument':
    """Snapshot a complete active result, including an applied manual history."""
    from stmviewer.registration import REGISTRATION_METHODS
    from stmviewer.trial_document import TrialDocument
    records = []
    for i, frame in enumerate(result.frames):
        previous = result.frames[i - 1].shift_xy if i else frame.shift_xy
        shift = (frame.shift_xy[0] - previous[0], frame.shift_xy[1] - previous[1]) if i else None
        # Deletion retains historical transforms. A diagnostic for B relative to A
        # cannot become evidence for B relative to a different surviving neighbor.
        source = (str(frame.original.source), frame.original.source_frame_index)
        baseline_index = next((j for j, base in enumerate(result.baseline)
                               if (base.source.source, base.source.source_frame_index) == source), None)
        adjacent = i > 0 and baseline_index is not None and baseline_index > 0
        if adjacent and baseline_index is not None:
            prior_source = result.baseline[baseline_index - 1].source
            previous_frame = result.frames[i - 1].original
            adjacent = (prior_source.source, prior_source.source_frame_index) == (
                str(previous_frame.source), previous_frame.source_frame_index)
        manual = next((item for item in result.corrections
                       if item.moving.source == str(frame.original.source)
                       and item.moving.source_frame_index == frame.original.source_frame_index), None) if adjacent else None
        estimate = result.pair_estimates[i] if adjacent and result.pair_estimates else None
        if estimate is not None and manual is None:
            shift = estimate.shift_xy
        records.append(_record(
            i, shift=shift, cumulative=frame.shift_xy, status=frame.status,
            quality=frame.quality_score, inherited=frame.inherited_uncertainty,
            hybrid=result.pair_diagnostics[i] if adjacent and result.pair_diagnostics else None,
            local=result.local_diagnostics[i] if adjacent and result.local_diagnostics else None, manual=manual,
            pair_status='manual' if manual else estimate.status if estimate else None,
            pair_quality=None if manual or estimate is None else estimate.quality_score,
        ))
    payload = {
        'kind': 'series', 'outcome': 'complete',
        'method': next((key for key, label in REGISTRATION_METHODS.items() if label == result.method), result.method),
        'label': result.method, 'settings_text': result.settings_text,
        'settings': _plain(result.settings), 'device': result.device, 'error': None,
        'frame_count': len(result.frames), 'reference_index': 0, 'records': records,
        'reference_origin': _plain(result.reference), 'code_revision': code_revision(), 'code_dirty': code_dirty(),
        'manual_movie': {'revision': result.revision, 'settings_version': result.settings_version,
                         'baseline': _plain(result.baseline), 'corrections': _plain(result.corrections)}
                        if result.corrections else None,
    }
    return TrialDocument(payload)


def from_pair(trial: 'PairTrial', frames: tuple[ImageFrame, ...]) -> 'TrialDocument':
    """Snapshot an approved pair; never the uncommitted manual draft."""
    def index(origin: object) -> int:
        from stmviewer.registration import FrameOrigin
        for i, frame in enumerate(frames):
            if FrameOrigin(frame.source, frame.source_frame_index) == origin:
                return i
        raise ValueError('Próba dotyczy innej serii źródłowej.')
    capture = AttemptCapture(frames, trial.method, kind='pair', reference_index=index(trial.reference),
                             moving_index=index(trial.moving))
    capture.payload['settings'] = _plain(trial.settings)
    capture.finish_pair(trial)
    return capture.document


def pair_from_document(document: 'TrialDocument', frames: tuple[ImageFrame, ...],
                       moving_index: int | None = None) -> 'PairTrial':
    """Reconstruct only measured pair XY; diagnostics never invent a complete pair."""
    from stmviewer.deep_ecc import HybridDiagnostics
    from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence
    from stmviewer.pair_comparison import ManualProvenance, PairTrial
    from stmviewer.registration import FrameOrigin
    payload = document.payload
    records = payload['records']
    index = moving_index if moving_index is not None else (records[0]['index'] if payload['kind'] == 'pair' else 1)
    record = next((item for item in records if item['index'] == index), None)
    if record is None or record['shift_xy'] is None:
        raise ValueError('Brak zatwierdzonego wyniku tej pary; dostępna jest jedynie diagnostyka.')
    reference_index = payload['reference_index'] if payload['kind'] == 'pair' else index - 1
    if not 0 <= reference_index < len(frames) or not 0 <= index < len(frames):
        raise ValueError('Para nie należy do bieżącej serii.')
    hybrid_data = deepcopy(record['hybrid'])
    hybrid = None
    if hybrid_data is not None and hybrid_data.get('final_shift_xy') is not None:
        for name in ('deep_shift_xy', 'final_shift_xy', 'correction_xy'):
            hybrid_data[name] = tuple(hybrid_data[name])
        hybrid = HybridDiagnostics(**hybrid_data)
    local_data = deepcopy(record['local'])
    local = None
    if local_data is not None:
        local_data['deep_shift_xy'] = tuple(local_data['deep_shift_xy'])
        if local_data['final_shift_xy'] is not None:
            local_data['final_shift_xy'] = tuple(local_data['final_shift_xy'])
        patches = []
        for patch in local_data['patches']:
            for key in ('reference_rect', 'moving_rect', 'shift_xy'):
                if patch.get(key) is not None:
                    patch[key] = tuple(patch[key])
            patches.append(LocalPatchEvidence(**patch))
        local_data['patches'] = tuple(patches)
        local = LocalDiagnostics(**local_data)
    manual_data = record['manual']
    manual = None if manual_data is None else ManualProvenance(
        tuple(manual_data['start_xy']), tuple(manual_data['correction_xy']),
        manual_data['source_label'], manual_data['settings_version'],
    )
    reference, moving = frames[reference_index], frames[index]
    return PairTrial(
        FrameOrigin(reference.source, reference.source_frame_index), FrameOrigin(moving.source, moving.source_frame_index),
        'manual' if manual else payload['method'], 'Ręczna korekta filmu' if manual and payload['kind'] == 'series' else payload['label'],
        payload['settings_text'], 'Operator' if manual else payload['device'],
        tuple(record['shift_xy']), 'manual' if manual else record.get('pair_status') or record['status'],
        None if manual else record.get('pair_quality_score', record['quality_score']),
        manual=manual, hybrid=hybrid, local=local, settings=deepcopy(payload['settings']),
    )


def diagnostic_start_from_document(document: 'TrialDocument', frames: tuple[ImageFrame, ...],
                                   moving_index: int | None = None) -> 'PairTrial':
    """Preview an available Deep start explicitly as evidence of an incomplete attempt."""
    from stmviewer.pair_comparison import PairTrial
    from stmviewer.registration import FrameOrigin
    payload = document.payload
    records = payload['records']
    index = moving_index if moving_index is not None else (records[0]['index'] if payload['kind'] == 'pair' else 1)
    record = next((item for item in records if item['index'] == index), None)
    details = None if record is None else record.get('hybrid') or record.get('local')
    if details is None or details.get('deep_shift_xy') is None:
        raise ValueError('Brak zapisanego początkowego XY Deep dla tej pary.')
    reference_index = payload['reference_index'] if payload['kind'] == 'pair' else index - 1
    if not 0 <= reference_index < len(frames) or not 0 <= index < len(frames):
        raise ValueError('Para nie należy do bieżącej serii.')
    reference, moving = frames[reference_index], frames[index]
    stage = details.get('stage', 'lokalne fragmenty')
    label = f'Start Deep — {stage}: przerwana próba'
    return PairTrial(
        FrameOrigin(reference.source, reference.source_frame_index),
        FrameOrigin(moving.source, moving.source_frame_index), 'deep_matcher_translation', label,
        payload['settings_text'] + '\n' + (payload['error'] or 'Brak kompletnego wyniku.'),
        payload['device'], tuple(details['deep_shift_xy']), 'manual_review', None,
        settings=deepcopy(payload['settings']),
    )
