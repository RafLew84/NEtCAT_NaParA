"""REG-14 opt-in CPU trials; reuse the unchanged REG-13 input manifest and baselines."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
from time import perf_counter, process_time

import cv2
import numpy as np

from lightglue_trial import (digest, export_corrected_avi, input_manifest,
                             pair_inputs, run_visuals, save)
from roma_trial import error_details
from stmviewer.akaze_matcher import AkazeBackend
from stmviewer.correspondence_types import CorrespondenceRefusal
from stmviewer.series import open_frame_series


def profile(function):
    wall, cpu = perf_counter(), process_time()
    result = error = None
    try:
        result = function()
    except Exception as caught:
        error = caught
    return result, error, {
        'wall_s': perf_counter()-wall, 'process_cpu_s': process_time()-cpu,
        'process_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'ram_note': 'Linux process lifetime RSS high-water mark, including prior stages; no child/model process.'
    }


def verify_baselines(args):
    """Preserve original reports and verify the exact measured frame values."""
    records = {}
    for mode in ('pairs', 'patterns'):
        for method in ('deep', 'roma', 'lightglue'):
            source = args.baseline / f'{mode}-{method}.json'
            target = args.output / source.name
            if target.exists() and digest(target) != digest(source):
                raise ValueError(f'Changed baseline: {target}')
            shutil.copyfile(source, target)
            records[source.name] = digest(source)
    shutil.copytree(args.baseline/'fixtures', args.output/'fixtures', dirs_exist_ok=True)
    for mode in ('pairs', 'patterns'):
        _, cases = pair_inputs(argparse.Namespace(**(vars(args) | {'mode': mode})))
        for method in ('deep', 'roma', 'lightglue'):
            old = json.loads((args.output/f'{mode}-{method}.json').read_text())
            assert len(old['attempts']) == len(cases)
            for case, previous in zip(cases, old['attempts'], strict=True):
                path, a, b, number, _ = case
                assert path.name == previous['file'] and number == previous['pair_1based'][0]
                assert [digest_array(a.data), digest_array(b.data)] == previous['frame_sha256']
    source_files = ('deep_matcher.py', 'roma_matcher.py', 'roma_process.py', 'roma_worker.py',
                    'lightglue_matcher.py', 'lightglue_resources.py', 'lightglue_worker.py',
                    'correspondence_consensus.py')
    hashes = {}
    for name in source_files:
        path = Path('stmviewer')/name
        original = subprocess.check_output(['git', 'show', f'cc8dfcd:{path}'])
        assert hashlib.sha256(original).hexdigest() == digest(path), f'Changed estimator: {path}'
        hashes[str(path)] = digest(path)
    save(args.output/'baseline-verification.json', {
        'report_sha256': records, 'unchanged_source_sha256': hashes,
        'verification': 'Same source frame values and estimator code; baseline timings are historical CUDA runs.'
    })


def digest_array(data):
    return hashlib.sha256(data.tobytes()).hexdigest()


def pairs(args):
    manifest, cases = pair_inputs(args)
    backend = AkazeBackend()
    report = {'mode': args.mode, 'method': 'akaze', 'inputs': manifest,
              'provenance': dict(backend.provenance), 'actual_device': backend.device,
              'python': platform.python_version(), 'opencv_threads': cv2.getNumThreads(),
              'libraries': {name: importlib.metadata.version(name)
                            for name in ('opencv-python', 'numpy')},
              'source_sha256': {str(p): digest(p) for p in (
                  Path('stmviewer/akaze_matcher.py'), Path('stmviewer/correspondence_consensus.py'))},
              'attempts': []}
    def measure():
        for path, reference, moving, number, known in cases:
            before = [digest_array(reference.data), digest_array(moving.data)]
            attempt = {'file': path.name, 'pair_1based': [number, number+1],
                       'frame_sha256': before, 'shape_yx': list(reference.data.shape), **known}
            started = perf_counter()
            try:
                result = backend.estimate(reference.data, moving.data, moving_frame_index=number)
                attempt.update(outcome='result', shift_xy=list(result.shift_xy),
                               status=result.status, quality_score=None)
                expected = known.get('expected_alignment_xy')
                if expected is not None:
                    attempt['max_axis_error_px'] = float(np.max(np.abs(np.asarray(result.shift_xy)-expected)))
            except Exception as error:
                attempt.update(outcome='refusal' if isinstance(error, CorrespondenceRefusal) else 'error',
                               error=error_details(error))
            attempt['estimation_seconds'] = perf_counter()-started
            if backend.last_diagnostics is not None:
                attempt['diagnostics'] = asdict(backend.last_diagnostics)
            assert before == [digest_array(reference.data), digest_array(moving.data)]
            report['attempts'].append(attempt)
            print(path.name, number, attempt['outcome'], attempt.get('shift_xy'), flush=True)
    _, error, timing = profile(measure)
    backend.close()
    report['timing'] = timing
    save(args.output/f'{args.mode}-akaze.json', report)
    if error:
        raise error


def movie(args):
    from graph_application_trial import fingerprint
    from graph_methods_trial import lifecycle
    from stmviewer.graph_registration import register_graph
    from stmviewer.registration import register_series
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState, SessionViewState

    frames = open_frame_series([args.source])[args.drop_first:]
    output = args.output/f'movie-{args.source.stem.lower()}'
    output.mkdir(exist_ok=False)
    report = {'inputs': input_manifest([args.source], [args.drop_first]), 'count': len(frames),
              'shape_yx': list(frames[0].data.shape), 'opencv_threads': cv2.getNumThreads(),
              'quality': 'Completeness is not evidence of correct physical STM drift.'}
    view = SessionViewState(pixel_proportions=True, method='akaze')
    last = -100
    def progress(done, total, description):
        nonlocal last
        if done >= last+100 or (done == total and done != last):
            print(f'{done}/{total}: {description}', flush=True)
            last = done
    chain, error, timing = profile(lambda: register_series(frames, method='akaze', progress=progress))
    report['chain'] = {'complete': chain is not None, 'timing': timing}
    if error:
        report['chain']['error'] = error_details(error)
    if chain is not None:
        report['chain'].update(canvas=list(chain.canvas_shape),
                               statuses=dict(Counter(f.status for f in chain.frames)))
        save_session(output/'chain.stmsession', SessionState(frames, chain, replace(view, view='aligned')))
        reopened = load_session(output/'chain.stmsession')
        assert fingerprint(reopened.registration) == fingerprint(chain)
        del reopened, chain
    save(output/'report.json', report)
    last = -100
    graph, error, timing = profile(lambda: register_graph(frames, method='akaze', window=3, progress=progress))
    report['graph'] = {'available': graph is not None, 'timing': timing}
    if error:
        report['graph']['error'] = error_details(error)
        save(output/'report.json', report)
        raise error
    robust = solve_robust_graph(graph, RobustConfig())
    graph = replace(graph, robust_trials=(robust,))
    report['graph'].update(
        config=asdict(graph.config), measured_pairs=graph.measured_pairs,
        edge_statuses=dict(Counter(e.status for e in graph.edges)),
        ls_complete=graph.positions is not None, components=[len(c) for c in graph.components],
        measurement_s=graph.measurement_s, ls_solver_s=graph.solver_s,
        huber_status=robust.status, huber_iterations=robust.iterations, huber_solver_s=robust.solver_s,
        missing_pairs=[{'pair': [e.i+1,e.j+1], 'reason': e.reason} for e in graph.edges if e.shift_xy is None])
    save_session(output/'graph-candidate.stmsession', SessionState(frames, display=view, graph=graph))
    reopened = load_session(output/'graph-candidate.stmsession')
    assert reopened.graph == graph and reopened.registration is None
    del reopened
    save(output/'report.json', report)
    if graph.positions is not None:
        report['graph']['lifecycle'] = lifecycle(frames, graph, output, view)
        if len(frames) <= 12:
            report['graph']['corrected_avi'] = export_corrected_avi(output, report['graph']['lifecycle'])
    save(output/'report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('verify', 'pairs', 'patterns', 'movie', 'known', 'visuals'), required=True)
    parser.add_argument('--output', type=Path, default=Path('data/registration-reg14'))
    parser.add_argument('--baseline', type=Path, default=Path('data/registration-reg13'))
    parser.add_argument('--data', type=Path, default=Path('data'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--drop-first', type=int, default=0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(4)  # Harness only; the application does not change global OpenCV state.
    if args.mode == 'verify':
        verify_baselines(args)
    elif args.mode in ('pairs', 'patterns'):
        pairs(args)
    elif args.mode == 'movie':
        if args.source is None:
            parser.error('--source is required for movie')
        movie(args)
    elif args.mode == 'known':
        from graph_methods_trial import known_movie
        args.source, _ = known_movie(args.output)
        movie(args)
    else:
        args.methods = ['deep', 'roma', 'lightglue', 'akaze']
        run_visuals(args)


if __name__ == '__main__':
    main()
