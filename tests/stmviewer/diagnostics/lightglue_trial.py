"""REG-13 opt-in real comparisons, shared manifest, and full-movie attempts.

PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/lightglue_trial.py
    --mode pairs --output data/registration-reg13 --methods deep roma lightglue
Use a single process at a time for comparable timing. Model evidence does not
establish physical STM drift; real images require manual assessment.
"""
import argparse
from collections import Counter
import cProfile
from dataclasses import asdict, replace
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from time import perf_counter

import numpy as np

from roma_trial import Resources, error_details
from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
from stmviewer.registration import estimate_confidence
from stmviewer.roma_matcher import default_roma_options, load_roma_backend
from stmviewer.series import open_frame_series


METHODS = {'deep': 'deep_matcher_translation', 'roma': 'roma_v2',
           'lightglue': 'lightglue_superpoint'}
PAIRS = {'MOVIE_4.mpp': (1, 31, 118, 29, 35, 44, 45, 61, 94, 95, 96, 160, 250),
         'MOVIE_8.mpp': (1, 16, 56, 25, 70)}
DEEP_WEIGHTS = Path('/home/rlew/projekty/tracker-import-20261008/trackers-windows-20261008/'
                    'model_cache/torch/hub/checkpoints/loftr_outdoor.ckpt')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def options_for(method, args):
    if method == 'deep':
        return DeepMatcherOptions(args.deep_weights, args.device)
    if method == 'roma':
        return replace(default_roma_options(), device=args.device, preset='turbo')
    from stmviewer.lightglue_matcher import default_lightglue_options
    return replace(default_lightglue_options(), device=args.device)


def backend_for(method, options):
    if method == 'deep':
        loaded = load_deep_backend(options)
        return loaded.backend, loaded.device, {
            'weights_path': str(options.weights), 'weights_sha256': digest(options.weights),
            'estimator': 'historical LoFTR outdoor + NanoTrack consensus',
            'configuration': asdict(loaded.backend.config)}
    if method == 'roma':
        backend = load_roma_backend(options)
    else:
        from stmviewer.lightglue_matcher import load_lightglue_backend
        backend = load_lightglue_backend(options)
    return backend, backend.device, dict(backend.provenance)


def resource_record(resources):
    return {'sampled_peak_tree_rss_mib': resources.peak_rss_mib,
            'sampled_peak_driver_vram_mib': resources.peak_driver_vram_mib,
            'probe_errors': resources.gpu_probe_errors,
            'sampling_note': 'Process-tree RSS and driver VRAM every 1 s; short peaks may be missed.'}


def profile_movie(function):
    """Time public stages; worker RPC includes model computation and transport."""
    resources = Resources()
    resources.thread.start()
    profiler = cProfile.Profile()
    tick = perf_counter()
    result = error = None
    profiler.enable()
    try:
        result = function()
    except Exception as caught:
        error = caught
    finally:
        profiler.disable()
        resources.done.set()
        resources.thread.join(timeout=5.)
    timing = {'wall_s': perf_counter()-tick, 'consensus_s': 0., 'renderer_s': 0.,
              'solver_s': 0., 'worker_rpc_s': 0., **resource_record(resources)}
    for item in profiler.getstats():
        code = item.code
        if isinstance(code, str):
            continue
        if code.co_name == 'estimate_correspondence_translation':
            timing['consensus_s'] += item.totaltime
        elif code.co_name == 'render_registration':
            timing['renderer_s'] += item.totaltime
        elif code.co_name == 'solve_graph':
            timing['solver_s'] += item.totaltime
        elif code.co_name == 'match' and any(name in code.co_filename for name in
                                           ('lightglue_process', 'roma_process')):
            timing['worker_rpc_s'] += item.totaltime
    return result, error, timing


def input_manifest(paths, drops):
    return [{'path': str(path.resolve()), 'sha256': digest(path), 'drop_first': drop}
            for path, drop in zip(paths, drops, strict=True)]


def pair_inputs(args):
    if args.mode == 'pairs':
        paths = [args.data / name for name in PAIRS]
        manifest = input_manifest(paths, (2, 0))
        cases = []
        for path, drop in zip(paths, (2, 0), strict=True):
            frames = open_frame_series([path])[drop:]
            for number in PAIRS[path.name]:
                cases.append((path, frames[number - 1], frames[number], number,
                              {'source_pair_1based': [number + drop, number + drop + 1]}))
        return manifest, cases
    from make_local_consensus_fixtures import generate
    fixtures = args.output / 'fixtures'
    if not (fixtures / 'manifest.json').exists():
        generate(fixtures)
    known = json.loads((fixtures / 'manifest.json').read_text())['movies']
    cpu = Path(__file__).resolve().parents[1] / 'fixtures/registration/cpu.mpp'
    known[cpu.name] = {'adjacent_xy': [[2., -1.], [-3., 2.]],
                       'expected': 'Known XY, periodic edge wrapping.'}
    paths = [cpu] + [fixtures / f'{name}.mpp' for name in
                    ('translation', 'stationary-artifact', 'one-band', 'split-motion', 'periodic', 'noisy')]
    cases = []
    for path in paths:
        frames = open_frame_series([path])
        for i in range(1, len(frames)):
            description = known[path.name]
            expected = (description['adjacent_xy'][i - 1] if 'adjacent_xy' in description
                        else description.get('scene_xy'))
            cases.append((path, frames[i - 1], frames[i], i,
                          {'known': description, 'expected_alignment_xy': expected}))
    return input_manifest(paths, [0] * len(paths)), cases


def run_pairs(args):
    manifest, cases = pair_inputs(args)
    for method in args.methods:
        destination = args.output / f'{args.mode}-{method}.json'
        if destination.exists():
            raise FileExistsError(f'Refusing to replace {destination}')
        record = {'mode': args.mode, 'method': METHODS[method], 'inputs': manifest,
                  'options': asdict(options_for(method, args)), 'device_requested': args.device,
                  'python': platform.python_version(),
                  'libraries': {name: importlib.metadata.version(name) for name in ('torch', 'kornia', 'numpy')},
                  'viewer_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'viewer_dirty': subprocess.check_output(['git', 'diff', '--stat'], text=True),
                  'known_limits': 'Development pairs; no independent STM truth. Different Deep consensus.',
                  'attempts': []}
        record['options'] = {k: str(v) if isinstance(v, Path) else v for k, v in record['options'].items()}
        resources = Resources()
        resources.thread.start()
        backend = None
        tick = perf_counter()
        try:
            backend, device, provenance = backend_for(method, options_for(method, args))
            record.update(load_seconds=perf_counter()-tick, actual_device=device, provenance=provenance)
            for path, reference, moving, number, known in cases:
                before = (hashlib.sha256(reference.data.tobytes()).hexdigest(),
                          hashlib.sha256(moving.data.tobytes()).hexdigest())
                attempt = {'file': path.name, 'pair_1based': [number, number + 1],
                           'shape_yx': list(reference.data.shape), 'frame_sha256': before, **known}
                record['attempts'].append(attempt)
                started = perf_counter()
                try:
                    result = backend.estimate(reference.data, moving.data, moving_frame_index=number)
                    status, quality = estimate_confidence(METHODS[method], result)
                    attempt.update(outcome='result', shift_xy=list(result.shift_xy), status=status,
                                   quality_score=quality)
                    expected = known.get('expected_alignment_xy')
                    if expected is not None:
                        attempt['max_axis_error_px'] = float(np.max(np.abs(np.asarray(result.shift_xy)-expected)))
                except Exception as error:
                    from stmviewer.correspondence_types import CorrespondenceRefusal
                    attempt.update(outcome='refusal' if isinstance(error, CorrespondenceRefusal) else 'error',
                                   error=error_details(error))
                finally:
                    attempt['estimation_seconds'] = perf_counter()-started
                    diagnostic = getattr(backend, 'last_diagnostics', None)
                    if diagnostic is not None:
                        attempt['diagnostics'] = asdict(diagnostic)
                    attempt['worker_metrics'] = getattr(backend, 'last_metrics', {})
                    assert before == (hashlib.sha256(reference.data.tobytes()).hexdigest(),
                                      hashlib.sha256(moving.data.tobytes()).hexdigest())
                    save(destination, record)
                    print(method, path.name, number, attempt['outcome'], attempt.get('shift_xy'), flush=True)
        finally:
            if backend is not None:
                close = getattr(backend, 'close', None)
                if close is not None:
                    close()
            backend = None
            gc.collect()
            resources.done.set()
            resources.thread.join(timeout=5.)
            record['resources'] = resource_record(resources)
            record['total_seconds'] = perf_counter()-tick
            save(destination, record)


def run_movie(args):
    from graph_application_trial import fingerprint
    from graph_methods_trial import lifecycle
    from stmviewer.graph_registration import register_graph
    from stmviewer.registration import register_series
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState, SessionViewState

    if args.source is None:
        raise ValueError('--source is required for a full movie')
    options = options_for('lightglue', args)
    frames = open_frame_series([args.source])[args.drop_first:]
    report = {'inputs': input_manifest([args.source], [args.drop_first]),
              'count': len(frames), 'shape_yx': list(frames[0].data.shape),
              'quality': 'Completeness is not independent STM quality; manual review pending.'}
    output = args.output / f'movie-{args.source.stem.lower()}'
    output.mkdir(exist_ok=False)
    view = SessionViewState(pixel_proportions=True, method='lightglue_superpoint',
                            deep_device=args.device, deep_weights=str(options.weights),
                            deep_source=str(options.source),
                            deep_extractor_weights=str(options.extractor_weights), lightglue_options=options)
    last_printed = -100
    def progress(done, total, description):
        nonlocal last_printed
        if done >= last_printed + 100 or (done == total and done != last_printed):
            print(f'{done}/{total}: {description}', flush=True)
            last_printed = done
    chain, error, timing = profile_movie(lambda: register_series(
        frames, method='lightglue_superpoint', deep_options=options, progress=progress))
    report['chain'] = {'complete': chain is not None, 'timing': timing}
    if error is not None:
        report['chain']['error'] = error_details(error)
    if chain is not None:
        report['chain'].update(canvas=list(chain.canvas_shape), actual_device=chain.device,
                               statuses=dict(Counter(f.status for f in chain.frames)))
        save_session(output / 'chain.stmsession', SessionState(frames, chain, replace(view, view='aligned')))
        reopened = load_session(output / 'chain.stmsession')
        assert fingerprint(reopened.registration) == fingerprint(chain)
        del reopened, chain
    save(output / 'report.json', report)
    last_printed = -100
    graph, error, timing = profile_movie(lambda: register_graph(
        frames, method='lightglue_superpoint', deep_options=options, window=3, progress=progress))
    report['graph'] = {'available': graph is not None, 'timing': timing}
    if error is not None:
        report['graph']['error'] = error_details(error)
        save(output / 'report.json', report)
        raise error
    robust = solve_robust_graph(graph, RobustConfig())
    graph = replace(graph, robust_trials=(robust,))
    report['graph'].update(config=asdict(graph.config), measured_pairs=graph.measured_pairs,
                           edge_statuses=dict(Counter(e.status for e in graph.edges)),
                           ls_complete=graph.positions is not None,
                           components=[len(c) for c in graph.components],
                           measurement_s=graph.measurement_s, ls_solver_s=graph.solver_s,
                           huber_status=robust.status, huber_iterations=robust.iterations,
                           huber_solver_s=robust.solver_s,
                           missing_pairs=[{'pair':[e.i+1,e.j+1],'reason':e.reason}
                                          for e in graph.edges if e.shift_xy is None])
    save_session(output / 'graph-candidate.stmsession', SessionState(frames, display=view, graph=graph))
    reopened = load_session(output / 'graph-candidate.stmsession')
    assert reopened.graph == graph and reopened.registration is None
    del reopened
    save(output / 'report.json', report)
    if graph.positions is not None:
        report['graph']['lifecycle'] = lifecycle(frames, graph, output, view)
    save(output / 'report.json', report)


def run_visuals(args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matchanything_visuals import overlay
    records = {name: json.loads((args.output / f'pairs-{name}.json').read_text()) for name in args.methods}
    manifests = [record['inputs'] for record in records.values()]
    assert all(value == manifests[0] for value in manifests), 'Different input manifests'
    for item in manifests[0]:
        assert digest(Path(item['path'])) == item['sha256'], 'Source data changed after measurement'
    results = {name: record['attempts'] for name, record in records.items()}
    for film, numbers in PAIRS.items():
        frames = open_frame_series([args.data / film])[(2 if film == 'MOVIE_4.mpp' else 0):]
        for page, offset in enumerate(range(0, len(numbers), 4), 1):
            subset = numbers[offset:offset+4]
            fig, axes = plt.subplots(len(subset), len(args.methods)+1,
                                     figsize=(4*(len(args.methods)+1), 3.5*len(subset)), squeeze=False)
            for row, number in enumerate(subset):
                a, b = frames[number-1].data, frames[number].data
                axes[row, 0].imshow(overlay(a, b, (0,0)), origin='upper')
                axes[row, 0].set_title(f'{film}: {number}→{number+1}\nPrzed dopasowaniem')
                for col, method in enumerate(args.methods, 1):
                    item = next(x for x in results[method] if x['file']==film and x['pair_1based'][0]==number)
                    if item['outcome']=='result':
                        xy=item['shift_xy']
                        axes[row,col].imshow(overlay(a,b,xy),origin='upper')
                        axes[row,col].set_title(f'{method}: XY={xy[0]:.2f}, {xy[1]:.2f}\n{item["status"]}')
                    else:
                        axes[row,col].text(.5,.5,f'{method}: {item["outcome"]}',ha='center',va='center')
                for ax in axes[row]: ax.set_axis_off()
            fig.suptitle('Bazowa: czerwony; przesuwana: turkusowy. Wspólny zakres i pole oryginału.\n'
                         'Nie jest to niezależny pomiar fizycznego dryfu STM.')
            fig.tight_layout(rect=(0,0,1,.96))
            fig.savefig(args.output/f'{Path(film).stem.lower()}-pairs-{page}.png',dpi=110)
            plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('pairs','patterns','movie','visuals'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--methods', choices=tuple(METHODS), nargs='+', default=list(METHODS))
    parser.add_argument('--device', choices=('cpu','cuda'), default='cuda')
    parser.add_argument('--deep-weights', type=Path, default=DEEP_WEIGHTS)
    parser.add_argument('--data', type=Path, default=Path('data'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--drop-first', type=int, default=0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.mode in ('pairs','patterns'):
        import torch
        torch.set_num_threads(4)
        run_pairs(args)
    elif args.mode == 'movie':
        run_movie(args)
    else:
        run_visuals(args)


if __name__ == '__main__':
    main()
