"""Explicitly apply a saved graph to originals, without inference or optimization."""
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.graph_application_types import GraphApplication, MovieSnapshot, SourceGeometry
from stmviewer.graph_types import GraphTrial
from stmviewer.graph_provenance import check_cancelled, graph_sources
from stmviewer.graph_validation import validate_graph_result
from stmviewer.manual_movie_types import MovieBaselineFrame, MovieSource
from stmviewer.registration import (
    FrameOrigin, RegistrationError, RegistrationResult, render_registration,
)


def apply_graph_to_movie(
        frames: tuple[ImageFrame, ...], graph: GraphTrial, *,
        robust_revision: str | None = None, previous: RegistrationResult | None = None,
        progress: Callable[[int, int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None) -> RegistrationResult:
    """Produce a complete movie; publishing it is the caller's atomic operation."""
    check_cancelled(cancelled)
    reason = graph_application_reason(frames, graph, robust_revision=robust_revision,
                                      cancelled=cancelled)
    if reason is not None:
        raise RegistrationError(reason)
    predecessor = None if previous is None else _snapshot(previous, cancelled)
    if predecessor is not None and predecessor.sources != graph.sources:
        raise RegistrationError('Poprzedni wynik nie należy do aktualnej serii oryginałów.')
    application = GraphApplication(graph, robust_revision)
    rendered = render_registration(
        frames, application.positions, ('manual_review',) * len(frames),
        (None,) * len(frames), (False,) * len(frames),
        reference=FrameOrigin(frames[0].source, frames[0].source_frame_index),
        method=f'Deep Matcher — graf {application.solver}', device=graph.config.device,
        progress=progress, cancelled=cancelled,
    )
    return replace(rendered, graph_application=application, predecessor=predecessor)


def graph_application_reason(
        frames: tuple[ImageFrame, ...], graph: GraphTrial, *,
        robust_revision: str | None = None, check_sources: bool = True,
        cancelled: Callable[[], bool] | None = None) -> str | None:
    """Explain refusal; cheap UI hints may omit pixel hashing and algebra checks.

    Applying always performs the full check in its cancellable worker.
    """
    check_cancelled(cancelled)
    if graph.config.settings_version != 1:
        return 'Graf: nieobsługiwana wersja ustawień.'
    if len(frames) < 2 or len(frames) != len(graph.sources):
        return 'Graf: liczba źródeł nie odpowiada aktualnej serii; wykonaj nową rejestrację.'
    for frame, source in zip(frames, graph.sources, strict=True):
        if (str(frame.source) != source.source
                or frame.source_frame_index != source.source_frame_index
                or frame.data.shape != source.shape):
            return 'Graf jest nieaktualny: źródła, kolejność lub geometria serii zmieniły się.'
    try:
        application = GraphApplication(graph, robust_revision)
        positions = application.positions
        if (len(positions) != len(frames) or positions[0] != (0., 0.)
                or np.asarray(positions).shape != (len(frames), 2)
                or not np.isfinite(positions).all()):
            return 'Graf: nieprawidłowe końcowe pozycje XY.'
        if graph.positions is None or len(graph.components) != 1:
            return 'Graf jest rozłączny lub nie ma kompletnego rozwiązania.'
        if not check_sources:
            return None
        if graph_sources(frames, cancelled=cancelled) != graph.sources:
            return 'Graf jest nieaktualny: wartości oryginałów zmieniły się.'
        for edge in graph.edges:
            check_cancelled(cancelled)
            if edge.quality_score is not None and (not np.isfinite(edge.quality_score)
                                                   or not 0 <= edge.quality_score <= 1):
                return 'Graf: nieprawidłowy wskaźnik pomiaru.'
            if edge.shift_xy is None:
                if edge.status != 'missing' or not edge.reason:
                    return 'Graf: brakujący pomiar nie zawiera powodu odmowy.'
            elif (edge.status not in ('ok', 'low_confidence')
                  or np.asarray(edge.shift_xy).shape != (2,)
                  or not np.isfinite(edge.shift_xy).all()):
                return 'Graf: nieprawidłowy pomiar lub anulowana próba.'
        validate_graph_result(graph, lambda: check_cancelled(cancelled))
        if robust_revision is not None:
            from stmviewer.robust_graph_validation import validate_robust_result
            selected = next(item for item in graph.robust_trials if item.revision == robust_revision)
            validate_robust_result(graph, selected, lambda: check_cancelled(cancelled))
    except (ValueError, TypeError, IndexError, KeyError) as error:
        return str(error) or 'Graf: nieprawidłowa próba.'
    return None


def _geometry(frames: tuple[ImageFrame, ...]) -> tuple[SourceGeometry, ...]:
    return tuple((f.size_x_nm, f.size_y_nm, f.offset_x_nm, f.offset_y_nm) for f in frames)


def _snapshot(result: RegistrationResult,
              cancelled: Callable[[], bool] | None) -> MovieSnapshot:
    originals = tuple(item.original for item in result.frames)
    sources = graph_sources(originals, cancelled=cancelled)
    final = tuple(MovieBaselineFrame(
        MovieSource(str(item.original.source), item.original.source_frame_index),
        item.shift_xy, item.status, item.quality_score, item.inherited_uncertainty,
    ) for item in result.frames)
    return MovieSnapshot(
        sources=sources, source_geometry=_geometry(originals), final_frames=final,
        reference=MovieSource(str(result.reference.source), result.reference.source_frame_index),
        canvas_shape=result.canvas_shape, padding_ltrb=result.padding_ltrb,
        pixel_size_nm=result.pixel_size_nm, method=result.method, device=result.device,
        settings_version=result.settings_version, revision=result.revision, baseline=result.baseline,
        corrections=result.corrections, corrections_editable=result.corrections_editable,
        pair_diagnostics=result.pair_diagnostics, local_diagnostics=result.local_diagnostics,
        graph_application=result.graph_application,
    )


def restore_movie_reason(
        frames: tuple[ImageFrame, ...], current: RegistrationResult, *,
        check_sources: bool = True, cancelled: Callable[[], bool] | None = None) -> str | None:
    """Explain why the retained result cannot be rebuilt from these originals."""
    check_cancelled(cancelled)
    saved = current.predecessor
    if saved is None:
        return 'Brak zachowanego poprzedniego wyniku.'
    if len(frames) != len(saved.sources) or len(frames) != len(saved.final_frames):
        return 'Zachowany wynik nie odpowiada składowi serii; po usunięciu klatki przelicz rejestrację.'
    for frame, source, final in zip(frames, saved.sources, saved.final_frames, strict=True):
        if (str(frame.source) != source.source
                or frame.source_frame_index != source.source_frame_index
                or frame.data.shape != source.shape
                or final.source != MovieSource(source.source, source.source_frame_index)):
            return 'Zachowany wynik nie odpowiada źródłom, kolejności lub geometrii serii.'
    left, top, right, bottom = saved.padding_ltrb
    if saved.canvas_shape != (frames[0].data.shape[0] + top + bottom,
                              frames[0].data.shape[1] + left + right):
        return 'Zachowany wynik ma niezgodny rozmiar obszaru i padding.'
    if _geometry(frames) != saved.source_geometry:
        return 'Zachowany wynik nie odpowiada geometrii fizycznej oryginałów.'
    if check_sources and graph_sources(frames, cancelled=cancelled) != saved.sources:
        return 'Zachowany wynik nie odpowiada wartościom oryginałów.'
    return None


def restore_movie_result(
        frames: tuple[ImageFrame, ...], current: RegistrationResult, *,
        progress: Callable[[int, int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None) -> RegistrationResult:
    """Restore one lightweight predecessor and retain current as the next predecessor.

    A fresh revision makes pair trials started before switching the base stale.
    """
    reason = restore_movie_reason(frames, current, cancelled=cancelled)
    if reason is not None:
        raise RegistrationError(reason)
    saved = current.predecessor
    assert saved is not None
    predecessor = _snapshot(current, cancelled)
    rendered = render_registration(
        frames, saved.final_positions, tuple(f.status for f in saved.final_frames),
        tuple(f.quality_score for f in saved.final_frames),
        tuple(f.inherited_uncertainty for f in saved.final_frames),
        reference=FrameOrigin(Path(saved.reference.source), saved.reference.source_frame_index),
        method=saved.method, device=saved.device, progress=progress, cancelled=cancelled,
        padding_ltrb=saved.padding_ltrb,
    )
    # Deleting an outlier calibration must not change the historical canvas scale.
    # This replaces only metadata; the interpolated arrays and validity masks remain shared.
    if rendered.pixel_size_nm != saved.pixel_size_nm:
        scale = saved.pixel_size_nm
        aligned = tuple(replace(item, image=replace(
            item.image, size_x_nm=saved.canvas_shape[1] * scale[0] if scale else None,
            size_y_nm=saved.canvas_shape[0] * scale[1] if scale else None,
        )) for item in rendered.frames)
        rendered = replace(rendered, frames=aligned, pixel_size_nm=scale)
    return replace(
        rendered, settings_version=saved.settings_version, baseline=saved.baseline,
        corrections=saved.corrections, corrections_editable=saved.corrections_editable,
        pair_diagnostics=saved.pair_diagnostics, local_diagnostics=saved.local_diagnostics,
        graph_application=saved.graph_application, predecessor=predecessor,
    )
