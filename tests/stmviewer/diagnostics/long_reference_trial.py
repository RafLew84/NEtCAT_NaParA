"""Opt-in REG-08d: measure only explicit added pairs, replay sessions and exports."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import resource
from time import perf_counter
import urllib.request

import numpy as np

from graph_application_trial import correct, fingerprint, prefix
from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
from stmviewer.graph_preview import GraphMoviePreview
from stmviewer.long_references import extend_graph, plan_long_references, solve_extended_graph
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.series import open_frame_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--references', required=True, help='Comma-separated one-based indices.')
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    import torch
    torch.set_num_threads(4)

    def no_download(*a, **kw):
        raise RuntimeError('This diagnostic does not download weights.')
    torch.hub.load_state_dict_from_url = no_download
    torch.hub.download_url_to_file = no_download
    urllib.request.urlopen = no_download
    state = load_session(args.session)
    frames, base = state.frames, state.graph
    assert base is not None and base.extension is None and base.positions is not None
    refs = tuple(int(i.strip()) - 1 for i in args.references.split(','))
    selection = dict(references=refs, target_start=args.start - 1, target_end=args.end - 1)
    pairs = plan_long_references(base, **selection)
    print(f'{len(frames)} frames, window={base.config.window}, new pairs={len(pairs)}', flush=True)
    last = -25

    def progress(done, total, description):
        nonlocal last
        if done >= last + 25 or done == total:
            last = done
            print(f'{done}/{total}: {description}', flush=True)
    torch.cuda.reset_peak_memory_stats()
    started = perf_counter()
    extended = extend_graph(frames, base, progress=progress, **selection)
    measured_s = perf_counter() - started
    added = tuple(edge for edge in extended.edges if (edge.i, edge.j) in set(pairs))
    assert extended.extension.base == base
    old_edges = {(e.i, e.j): replace(e, residual_xy=None) for e in base.edges}
    assert all(replace(e, residual_xy=None) == old_edges[(e.i, e.j)]
               for e in extended.edges if (e.i, e.j) in old_edges)
    # Retain the real measurements before further rendering/export checks.
    save_session(args.output / 'measured.stmsession', replace(state, graph=extended))
    selected = next((item for item in base.robust_trials if item.positions is not None
                     and item.config.threshold_px == 2.), None)
    variants = [('ls', extended, None)]
    if selected is not None:
        robust_graph = solve_extended_graph(base, added, measurement_config=extended.extension.measurement_config,
                                            robust_revision=selected.revision, **selection)
        variants.append(('huber', robust_graph, selected.revision))
    report = {'input': str(args.session), 'frames': len(frames), 'window': base.config.window,
              'references_1based': [i + 1 for i in refs], 'target_range_1based': [args.start, args.end],
              'measurement_wall_s': measured_s, 'measurement_s': extended.measurement_s,
              'ls_solver_s': extended.solver_s, 'new_pairs': len(pairs),
              'missing_added_pairs': sum(e.shift_xy is None for e in added),
              'old_measurements_preserved': True, 'new_config': asdict(extended.extension.measurement_config),
              'visual_quality': 'Requires human review; global XY and residuals do not establish physical accuracy.',
              'results': []}
    display = SessionViewState(index=args.start - 1, view='aligned', pixel_proportions=True,
                               deep_weights=base.config.weights_path, deep_device=base.config.requested_device)
    for name, candidate, base_revision in variants:
        prior = apply_graph_to_movie(frames, base, robust_revision=base_revision)
        prior_fingerprint = fingerprint(prior)
        candidate_revision = candidate.robust_trials[0].revision if base_revision else None
        positions = candidate.robust_trials[0].positions if base_revision else candidate.positions
        base_positions = selected.positions if base_revision else base.positions
        archive = args.output / f'{name}-candidate.stmsession'
        save_session(archive, SessionState(frames, prior, display, candidate))
        reopened = load_session(archive)
        assert reopened.graph == candidate and fingerprint(reopened.registration) == prior_fingerprint
        del reopened
        item = {'solver': name, 'base_robust_revision': base_revision,
                'candidate_robust_revision': candidate_revision, 'complete': positions is not None}
        if base_revision:
            item['huber'] = asdict(candidate.robust_trials[0].config)
            item['status'] = candidate.robust_trials[0].status
            item['iterations'] = candidate.robust_trials[0].iterations
            item['solver_s'] = candidate.robust_trials[0].solver_s
        if positions is not None:
            delta = np.asarray(positions) - np.asarray(base_positions)
            item['max_coordinate_change_px'] = float(np.max(np.abs(delta)))
            preview = GraphMoviePreview(frames, {'base': base_positions, 'extended': positions})
            durations = []
            for key in ('base', 'extended'):
                for i in range(len(frames)):
                    tick = perf_counter()
                    preview.render(i, key)
                    durations.append(perf_counter() - tick)
            item['render_p95_ms'] = float(np.percentile(durations, 95) * 1000)
            applied = apply_graph_to_movie(frames, candidate, robust_revision=candidate_revision, previous=prior)
            changed = correct(applied, max(1, args.start - 1), 0, 1)
            save_session(args.output / f'{name}-applied-corrected.stmsession',
                         SessionState(frames, changed, display, candidate))
            restored = restore_movie_result(frames, changed)
            assert fingerprint(restored) == prior_fingerprint
            small = prefix(changed, 5)
            path = save_aligned_mpp(args.output / f'{name}-five-frames.mpp', small)
            loaded = open_frame_series([path])
            for expected, actual in zip(small.frames, loaded, strict=True):
                assert actual.data.tobytes() == expected.image.data.tobytes()
                assert actual.alignment.shift_xy == expected.shift_xy
                assert actual.alignment.manual_movie.corrections == changed.corrections
            for label, movie in [('window', prior), ('extended', applied)]:
                save_avi(args.output / f'{name}-{label}.avi', prepare_avi(
                    tuple(frame.image for frame in movie.frames), start=args.start, end=args.end,
                    fps=5, codec='FFV1', presentation=MoviePresentation(pixel_proportions=True, background=255)))
            item['session_apply_manual_restore_mpp_avi'] = 'passed'
        report['results'].append(item)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        print(json.dumps(item), flush=True)
    report['process_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report['cuda_peak_allocated_mib'] = torch.cuda.max_memory_allocated() / 2**20
    (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
