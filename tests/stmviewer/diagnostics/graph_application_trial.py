"""REG-08c: apply saved LS/Huber, edit, restore and reopen real exports without a model."""
import argparse
import hashlib
import importlib.abc
import json
from pathlib import Path
import resource
import sys
from time import perf_counter


class NoModel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('torch', 'kornia'):
            raise ImportError('Application of saved graph must not import a model.')
        return None


def fingerprint(result):
    return tuple((item.shift_xy, item.origin_xy, item.status, item.quality_score,
                  item.inherited_uncertainty,
                  hashlib.sha256(item.image.data.tobytes()).hexdigest(),
                  hashlib.sha256(item.valid_mask.tobytes()).hexdigest()) for item in result.frames)


def correct(result, moving, dx, dy):
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.manual_pair import ManualPairDraft
    draft = ManualPairDraft(result.frames[moving - 1].original, result.frames[moving].original,
                            movie_pair_trial(result, moving))
    draft.nudge(dx, dy)
    return apply_movie_correction(result, draft.apply())


def prefix(result, count):
    for _ in range(max(0, len(result.frames) - count)):
        result = result.without_frame(len(result.frames) - 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--moving-frame', type=int, default=2, help='One-based moving frame for a demonstrative manual correction.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.meta_path.insert(0, NoModel())
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.manual_movie import movie_pair_trial
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.registration import FrameOrigin, render_registration
    from stmviewer.robust_graph import measurement_id
    from stmviewer.series import open_frame_series
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState, SessionViewState

    state = load_session(args.session)
    frames, graph = state.frames, state.graph
    if graph is None or graph.chain_positions is None:
        raise ValueError('This replay requires a saved connected graph with a complete chain.')
    moving = args.moving_frame - 1
    if not 1 <= moving < len(frames):
        raise ValueError('Choose a moving frame from 2 to the frame count.')
    count = len(frames)
    raw_id = measurement_id(graph)
    prior = render_registration(frames, graph.chain_positions, ('manual_review',) * count,
                                (None,) * count, (False,) * count,
                                reference=FrameOrigin(frames[0].source, frames[0].source_frame_index),
                                method='Deep Matcher — łańcuch zapisanych pomiarów', device=graph.config.device)
    prior = correct(prior, moving, 1, 0)
    prior_pixels = fingerprint(prior)
    display = SessionViewState(index=moving, view='aligned')
    save_session(args.output / 'ready-to-apply.stmsession', SessionState(frames, prior, display, graph))
    report = {'input': str(args.session), 'frames': count, 'window': graph.config.window,
              'measurement_id': raw_id, 'moving_frame': moving + 1,
              'note': 'The +1/+1 edits exercise workflow; they are not a proposed physical correction.',
              'results': []}
    variants = [('ls', None)]
    selected = next((item for item in graph.robust_trials if item.positions is not None
                     and item.config.threshold_px == 2.), None)
    if selected is not None:
        variants.append(('huber', selected.revision))
    for label, revision in variants:
        start = perf_counter()
        result = apply_graph_to_movie(frames, graph, robust_revision=revision, previous=prior)
        applied_s = perf_counter() - start
        base_pair = movie_pair_trial(result, moving).shift_xy
        corrected = correct(result, moving, 0, 1)
        assert corrected.graph_application == result.graph_application
        assert measurement_id(corrected.graph_application.graph) == raw_id
        assert fingerprint(prior) == prior_pixels
        archive = args.output / f'{label}-corrected.stmsession'
        save_session(archive, SessionState(frames, corrected, display, graph))
        reopened = load_session(archive)
        assert reopened.graph == graph
        assert reopened.registration.graph_application == corrected.graph_application
        assert reopened.registration.corrections == corrected.corrections
        assert fingerprint(reopened.registration) == fingerprint(corrected)
        restored = restore_movie_result(reopened.frames, reopened.registration)
        assert fingerprint(restored) == prior_pixels
        assert restored.baseline == prior.baseline and restored.corrections == prior.corrections
        assert restored.revision != prior.revision
        # Restoring swaps the lightweight predecessor, enabling the reverse action.
        reapplied = restore_movie_result(reopened.frames, restored)
        assert fingerprint(reapplied) == fingerprint(corrected)
        assert reapplied.graph_application == corrected.graph_application
        small = prefix(corrected, min(count, max(moving + 2, 5)))
        mpp = save_aligned_mpp(args.output / f'{label}-corrected.mpp', small)
        opened = open_frame_series([mpp])
        assert len(opened) == len(small.frames)
        for expected, actual in zip(small.frames, opened, strict=True):
            assert actual.data.tobytes() == expected.image.data.tobytes()
            assert actual.alignment.shift_xy == expected.shift_xy
            assert actual.alignment.manual_movie.corrections == corrected.corrections
        for codec in ('FFV1', 'MJPG'):
            save_avi(args.output / f'{label}-{codec}.avi', prepare_avi(
                tuple(item.image for item in corrected.frames), start=max(1, moving - 2),
                end=min(count, moving + 4), fps=5, codec=codec,
                presentation=MoviePresentation(pixel_proportions=True, background=255)))
        report['results'].append({'variant': label, 'robust_revision': revision,
                                  'application_s': applied_s, 'base_pair_xy': base_pair,
                                  'corrected_pair_xy': movie_pair_trial(corrected, moving).shift_xy,
                                  'canvas': corrected.canvas_shape, 'session_bytes': archive.stat().st_size,
                                  'mpp_frames': len(small.frames), 'roundtrip_and_restore': 'passed'})
        print(f'{label}: applied in {applied_s:.3f}s, session/MPP/AVI/restore passed', flush=True)
    report['process_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report['model_libraries_imported'] = any(name.split('.')[0] in ('torch', 'kornia') for name in sys.modules)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
