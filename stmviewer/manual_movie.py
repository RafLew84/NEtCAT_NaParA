"""Replace selected adjacent shifts and rebuild the movie from its originals."""

from collections.abc import Callable
from dataclasses import replace
import math

from stmviewer.manual_movie_types import MovieCorrection, MovieSource
from stmviewer.pair_comparison import PairTrial
from stmviewer.registration import (
    FrameOrigin, RegistrationCancelled, RegistrationError, RegistrationResult, render_registration,
)


def _source(result: RegistrationResult, index: int) -> MovieSource:
    original = result.frames[index].original
    return MovieSource(str(original.source), original.source_frame_index)


def _check_editable(result: RegistrationResult) -> None:
    if not result.corrections_editable:
        raise RegistrationError('Po usunięciu klatki wykonaj nową pełną rejestrację przed korektą filmu.')
    if not result.frames or len(result.baseline) != len(result.frames):
        raise RegistrationError('Korekta filmu wymaga kompletnej pełnej rejestracji.')
    if any(base.source != _source(result, i) for i, base in enumerate(result.baseline)):
        raise RegistrationError('Korekta filmu: źródła nie odpowiadają rejestracji bazowej.')


def movie_pair_trial(result: RegistrationResult, moving_index: int) -> PairTrial:
    """Start from the current relative shift, bound to this complete movie version."""
    _check_editable(result)
    if not 1 <= moving_index < len(result.frames):
        raise RegistrationError('Korekta wymaga sąsiedniej pary klatek.')
    reference, moving = result.frames[moving_index - 1:moving_index + 1]
    shift = tuple(a - b for a, b in zip(moving.shift_xy, reference.shift_xy))
    corrected = any(c.moving == _source(result, moving_index) for c in result.corrections)
    label = f'{result.method} — dopasowanie z filmu' + (' + korekta ręczna' if corrected else '')
    return PairTrial(
        FrameOrigin(reference.original.source, reference.original.source_frame_index),
        FrameOrigin(moving.original.source, moving.original.source_frame_index),
        'movie', label,
        f'Pełny wynik v{result.settings_version}; aktualne przesunięcie pary',
        result.device, (shift[0], shift[1]), moving.status, moving.quality_score,
        movie_revision=result.revision,
    )


def apply_movie_correction(
        result: RegistrationResult, trial: PairTrial, *,
        progress: Callable[[int, int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None) -> RegistrationResult:
    """Publish a manual pair shift only against the movie where editing began."""
    if cancelled is not None and cancelled():
        raise RegistrationCancelled
    _check_editable(result)
    if trial.movie_revision != result.revision:
        raise RegistrationError('Próba jest nieaktualna; rozpocznij korektę z bieżącego filmu.')
    if trial.method != 'manual' or trial.status != 'manual' or trial.manual is None:
        raise RegistrationError('Zastosuj zatwierdzoną ręczną korektę pary.')
    reference = MovieSource(str(trial.reference.source), trial.reference.source_frame_index)
    moving = MovieSource(str(trial.moving.source), trial.moving.source_frame_index)
    indices = [i for i in range(1, len(result.frames))
               if (_source(result, i - 1), _source(result, i)) == (reference, moving)]
    if len(indices) != 1:
        raise RegistrationError('Próba nie wskazuje jednoznacznej sąsiedniej pary tego filmu.')
    i = indices[0]
    manual = trial.manual
    values = (*trial.shift_xy, *manual.start_xy)
    if (len(trial.shift_xy) != 2 or len(manual.start_xy) != 2
            or len(manual.correction_xy) != 2 or not all(math.isfinite(v) for v in values)
            or any(type(v) is not int for v in manual.correction_xy)
            or trial.shift_xy != tuple(a + b for a, b in zip(manual.start_xy, manual.correction_xy))):
        raise RegistrationError('Nieprawidłowe XY lub pochodzenie ręcznej korekty.')
    current = movie_pair_trial(result, i).shift_xy
    if all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12) for a, b in zip(current, trial.shift_xy)):
        return result
    baseline_xy = tuple(a - b for a, b in zip(result.baseline[i].shift_xy,
                                             result.baseline[i - 1].shift_xy))
    correction = MovieCorrection(reference, moving, (baseline_xy[0], baseline_xy[1]),
                                 manual.start_xy, manual.correction_xy, manual.source_label,
                                 trial.shift_xy, manual.settings_version)
    remaining = tuple(c for c in result.corrections if c.moving != moving)
    return _rebuild(result, (*remaining, correction), progress=progress, cancelled=cancelled)


def remove_movie_correction(
        result: RegistrationResult, moving_index: int, *,
        progress: Callable[[int, int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None) -> RegistrationResult:
    """Restore one pair's automatic shift while retaining all other overrides."""
    if cancelled is not None and cancelled():
        raise RegistrationCancelled
    movie_pair_trial(result, moving_index)
    moving = _source(result, moving_index)
    remaining = tuple(c for c in result.corrections if c.moving != moving)
    if len(remaining) == len(result.corrections):
        return result
    return _rebuild(result, remaining, progress=progress, cancelled=cancelled)


def _rebuild(result: RegistrationResult, corrections: tuple[MovieCorrection, ...], *,
             progress: Callable[[int, int, str], None] | None,
             cancelled: Callable[[], bool] | None) -> RegistrationResult:
    correction_by_source = {correction.moving: correction for correction in corrections}
    shifts = [result.baseline[0].shift_xy]
    statuses = [result.baseline[0].status]
    qualities = [result.baseline[0].quality_score]
    inherited = [result.baseline[0].inherited_uncertainty]
    affected = False
    offset_x = offset_y = 0.0
    for i in range(1, len(result.frames)):
        if cancelled is not None and cancelled():
            raise RegistrationCancelled
        base = result.baseline[i]
        override = correction_by_source.get(base.source)
        if override is not None:
            offset_x += override.shift_xy[0] - override.baseline_xy[0]
            offset_y += override.shift_xy[1] - override.baseline_xy[1]
        shifts.append((base.shift_xy[0] + offset_x, base.shift_xy[1] + offset_y))
        inherited.append(affected or base.inherited_uncertainty)
        affected = affected or override is not None
        statuses.append('manual_review' if affected else base.status)
        qualities.append(None if affected else base.quality_score)
    rebuilt = render_registration(
        tuple(f.original for f in result.frames), tuple(shifts), tuple(statuses), tuple(qualities),
        tuple(inherited), reference=result.reference, method=result.method, device=result.device,
        progress=progress, cancelled=cancelled,
    )
    ordered = tuple(correction_by_source[base.source] for base in result.baseline
                    if base.source in correction_by_source)
    # Preserve the automatic pair estimates as history, independent of manual overrides.
    return replace(rebuilt, baseline=result.baseline, corrections=ordered,
                   settings_version=result.settings_version, pair_diagnostics=result.pair_diagnostics,
                   local_diagnostics=result.local_diagnostics,
                   settings_text=result.settings_text, settings=result.settings,
                   pair_estimates=result.pair_estimates)
