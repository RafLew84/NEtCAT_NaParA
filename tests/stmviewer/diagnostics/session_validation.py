"""Local session IO validation; requires MOVIE_4/8 and optional AVI dependencies.

From the repository root (the output directory is reserved for this diagnostic)::

    PYTHONPATH=. python tests/stmviewer/diagnostics/session_validation.py
    PYTHONPATH=. python tests/stmviewer/diagnostics/session_validation.py \
        --load-session /tmp/stmviewer-session-real/MOVIE_4-moved.stmsession

The second invocation opens an existing archive in a fresh process, checks that
Torch/Kornia are not imported, and exports three AVI frames without registration.
These are persistence checks, not an assessment of registration quality.
"""
import json
from pathlib import Path
import argparse
import sys
import tempfile
import time
import numpy as np
from stmviewer.series import open_frame_series
from stmviewer.registration import RegistrationResult, register_series
from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
from stmviewer.manual_pair import ManualPairDraft
from stmviewer.session_archive import save_session, load_session
from stmviewer.session_state import SessionState, SessionViewState
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.alignment_metadata import aligned_export_frames
from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.mpp import open_mpp_series


REPO_ROOT = Path(__file__).resolve().parents[3]


def peak_rss_mib() -> float | None:
    """Report process high-water memory where the platform exposes it."""
    try:
        import resource
    except ImportError:
        return None
    divisor = 1024 ** 2 if sys.platform == 'darwin' else 1024
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor, 1)


def nudge(result: RegistrationResult, index: int, dx: int, dy: int) -> RegistrationResult:
    draft = ManualPairDraft(result.frames[index - 1].original,
                            result.frames[index].original, movie_pair_trial(result, index))
    draft.nudge(dx, dy)
    return apply_movie_correction(result, draft.apply())

def validate_movie(data_dir: Path, out: Path, name: str, drop: int) -> dict[str, object]:
    row: dict[str, object] = {'movie': name, 'dropped_first_frames': drop}
    t = time.perf_counter()
    frames = open_frame_series([data_dir / f'{name}.mpp'])[drop:]
    row['frames'] = len(frames)
    row['original_shape'] = frames[0].data.shape
    row['import_s'] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    base = register_series(frames, method='phase_correlation')
    row['phase_s'] = round(time.perf_counter() - t, 3)
    result = nudge(nudge(base, 1, 1, 0), 2, 0, 1)
    del base
    row['aligned_shape'] = result.canvas_shape
    state = SessionState(frames, result, SessionViewState(index=2, view='aligned', gamma=1.7))
    t = time.perf_counter()
    path = save_session(out / f'{name}.stmsession', state)
    row['save_s'] = round(time.perf_counter() - t, 3)
    row['archive_bytes'] = path.stat().st_size
    moved = path.with_name(f'{name}-moved.stmsession')
    path.replace(moved)
    t = time.perf_counter()
    loaded = load_session(moved)
    row['load_s'] = round(time.perf_counter() - t, 3)
    assert loaded.display == state.display
    assert loaded.registration is not None
    assert result.corrections == loaded.registration.corrections
    assert result.baseline == loaded.registration.baseline
    assert result.reference == loaded.registration.reference
    assert result.revision == loaded.registration.revision
    for i, (a, b) in enumerate(zip(state.frames, loaded.frames)):
        assert a.data.tobytes() == b.data.tobytes(), ('original', i)
        assert a.raw_header == b.raw_header
        assert a.provenance == b.provenance
        assert a.source_frame_index == b.source_frame_index
        assert a.measurement_time_s == b.measurement_time_s
    for i, (aligned_before, aligned_after) in enumerate(zip(result.frames, loaded.registration.frames)):
        assert aligned_before.image.data.tobytes() == aligned_after.image.data.tobytes(), ('aligned', i)
        assert aligned_before.shift_xy == aligned_after.shift_xy
        assert aligned_before.origin_xy == aligned_after.origin_xy
        assert np.array_equal(aligned_before.valid_mask, aligned_after.valid_mask)
    row['exact_all_original_aligned_pixels_metadata'] = True
    next_result = nudge(loaded.registration, 1, 1, 0)
    assert next_result.frames[1].shift_xy[0] == result.frames[1].shift_xy[0] + 1
    del next_result
    row['continue_manual_correction_after_load'] = True
    t = time.perf_counter()
    mpp = save_aligned_mpp(out / f'{name}-restored.mpp', loaded.registration, overwrite=True)
    reopened = open_mpp_series(mpp, check_cancelled=lambda: None)
    for aligned, exported in zip(loaded.registration.frames, reopened):
        np.testing.assert_array_equal(aligned.image.data, exported.data)
    row['full_aligned_mpp_export_readback_s'] = round(time.perf_counter() - t, 3)
    row['mpp_values_equal'] = True
    del reopened
    t = time.perf_counter()
    avi_frames = aligned_export_frames(loaded.registration, lambda: None)
    plan = prepare_avi(avi_frames, start=1, end=3, codec='FFV1', fps=5)
    avi = save_avi(out / f'{name}-restored-first3.avi', plan, overwrite=True)
    row['ffv1_three_frames_export_decode_verified_s'] = round(time.perf_counter() - t, 3)
    row['ffv1_path'] = str(avi)
    row['peak_rss_mib_process'] = peak_rss_mib()
    return row


def validate_loaded_session(path: Path, out: Path) -> dict[str, object]:
    """Load without registration/model imports and exercise presentation export."""
    started = time.perf_counter()
    state = load_session(path)
    row: dict[str, object] = {
        'session': str(path), 'frames': len(state.frames),
        'load_s': round(time.perf_counter() - started, 3),
        'peak_rss_mib_after_load': peak_rss_mib(),
    }
    if state.registration is not None:
        result = state.registration
        row['aligned_shape'] = result.canvas_shape
        row['manual_corrections'] = len(result.corrections)
        row['manual_corrections_editable'] = result.corrections_editable
        frames = tuple(frame.image for frame in result.frames[:3])
    else:
        frames = state.frames[:3]
    started = time.perf_counter()
    plan = prepare_avi(frames, codec='FFV1', fps=5)
    avi = save_avi(out / 'fresh-load-first3.avi', plan, overwrite=True)
    row['ffv1_export_decode_verified_s'] = round(time.perf_counter() - started, 3)
    row['ffv1_path'] = str(avi)
    for library in ('torch', 'kornia'):
        imported = any(name == library or name.startswith(library + '.') for name in sys.modules)
        row[library + '_imported'] = imported
        assert not imported, f'{library} was imported by loading/exporting the session.'
    row['peak_rss_mib_process'] = peak_rss_mib()
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=REPO_ROOT / 'data')
    parser.add_argument('--output', type=Path,
                        default=Path(tempfile.gettempdir()) / 'stmviewer-session-real')
    parser.add_argument('--load-session', type=Path,
                        help='Only load this existing archive; do not run registration.')
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    if arguments.load_session is not None:
        row = validate_loaded_session(arguments.load_session, arguments.output)
        print(json.dumps(row), flush=True)
        (arguments.output / 'fresh-load-report.json').write_text(
            json.dumps(row, indent=2) + '\n', encoding='utf-8')
        return
    report = []
    for name, drop in [('MOVIE_4', 2), ('MOVIE_8', 0)]:
        row = validate_movie(arguments.data_dir, arguments.output, name, drop)
        print(json.dumps(row), flush=True)
        report.append(row)
        (arguments.output / 'report.json').write_text(
            json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
