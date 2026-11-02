"""REG-10 full local movie attempts, explicit refusals, provenance and timing.

PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/efficient_trial.py
    OUTPUT --source data/MOVIE_4.mpp --drop-first 2 --method efficient_loftr
No model download is permitted. Result quality on STM remains a human judgement.
"""
import argparse
from collections import Counter
import cProfile
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import resource
import sys
from time import perf_counter
import urllib.request

from graph_application_trial import fingerprint
from graph_methods_trial import lifecycle
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.efficient_matcher import default_efficient_options
from stmviewer.graph_registration import register_graph
from stmviewer.registration import register_series
from stmviewer.robust_graph import solve_robust_graph
from stmviewer.robust_graph_types import RobustConfig
from stmviewer.series import open_frame_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState


def profile_attempt(function, torch, device):
    # Explicit wall timers survive profiler resets inside optional dependencies.
    from stmviewer.efficient_runtime import TorchEfficientRuntime
    from stmviewer.deep_matcher import _LocalLoFTR
    model_elapsed = 0.
    originals = []
    for runtime_type in (TorchEfficientRuntime, _LocalLoFTR):
        original = runtime_type.match
        originals.append((runtime_type, original))
        def measured(self, *args, _original=original, **kwargs):
            nonlocal model_elapsed
            tick = perf_counter()
            try:
                return _original(self, *args, **kwargs)
            finally:
                model_elapsed += perf_counter() - tick
        runtime_type.match = measured
    profiler = cProfile.Profile()
    if device == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    started = perf_counter()
    result = None
    error = None
    profiler.enable()
    try:
        result = function()
    except Exception as caught:
        error = caught
    finally:
        profiler.disable()
        for runtime_type, original in originals:
            runtime_type.match = original
    timing = {'wall_s': perf_counter() - started, 'model_inference_s': model_elapsed,
              'consensus_s': 0., 'renderer_s': 0., 'solver_s': 0.,
              'process_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              'cuda_peak_allocated_mib': torch.cuda.max_memory_allocated() / 2**20 if device == 'cuda' else None,
              'cuda_allocated_after_job_mib': torch.cuda.memory_allocated() / 2**20 if device == 'cuda' else None,
              'profiling_note': 'Model wall timer includes transfers/inference; other sections cProfile cumulative, instrumented timings.'}
    for entry in profiler.getstats():
        code = entry.code
        if isinstance(code, str):
            continue
        if code.co_name == 'estimate_correspondence_translation':
            timing['consensus_s'] += entry.totaltime
        elif code.co_name == 'render_registration':
            timing['renderer_s'] += entry.totaltime
        elif code.co_name == 'solve_graph':
            timing['solver_s'] += entry.totaltime
    return result, error, timing


def error_details(error):
    result = {'type': type(error).__name__, 'reason': str(error)}
    current = error
    while current is not None:
        diagnostic = getattr(current, 'diagnostics', None)
        if diagnostic is not None:
            result['diagnostics'] = asdict(diagnostic)
            break
        current = current.__cause__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--method', choices=('efficient_loftr', 'deep_matcher_translation'), default='efficient_loftr')
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--code', type=Path)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    import torch
    torch.set_num_threads(4)
    def no_download(*unused, **keywords):
        raise RuntimeError('REG-10 diagnostic prohibits network/model downloads.')
    torch.hub.load_state_dict_from_url = no_download
    torch.hub.download_url_to_file = no_download
    urllib.request.urlopen = no_download
    options = replace(default_efficient_options(), device=args.device) if args.method == 'efficient_loftr' else DeepMatcherOptions(args.weights, args.device)
    if args.weights is not None:
        options = replace(options, weights=args.weights)
    if args.code is not None:
        options = replace(options, source=args.code)
    frames = open_frame_series([args.source])[args.drop_first:]
    with args.source.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'source': str(args.source.resolve()), 'source_sha256': source_hash,
              'method': args.method, 'drop_first': args.drop_first, 'frames': len(frames),
              'shape': frames[0].data.shape, 'requested_device': args.device,
              'gpu': torch.cuda.get_device_name(0) if args.device == 'cuda' else None,
              'quality': 'No independent STM ground truth; support/residuals are not physical correctness.',
              'original_hashes': [hashlib.sha256(frame.data.tobytes()).hexdigest() for frame in frames]}
    def save_report():
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    last_progress = ''
    last_print = -100
    def progress(done, total, text):
        nonlocal last_progress, last_print
        last_progress = text
        if done >= last_print + 100 or done == total:
            print(f'{done}/{total}: {text}', flush=True)
            last_print = done
    view = SessionViewState(pixel_proportions=True, method=args.method,
                            deep_weights=str(options.weights), deep_device=args.device,
                            deep_source=str(options.source) if options.source is not None else None)
    print('Adjacent registration', args.source, args.method, flush=True)
    chain, error, timing = profile_attempt(lambda: register_series(
        frames, method=args.method, deep_options=options, progress=progress), torch, args.device)
    report['chain'] = {'timing': timing, 'complete': chain is not None, 'last_progress': last_progress}
    if error is not None:
        report['chain']['error'] = error_details(error)
    if chain is not None:
        report['chain'].update(canvas=chain.canvas_shape, device=chain.device,
                               statuses=dict(Counter(frame.status for frame in chain.frames)))
        path = args.output / 'chain.stmsession'
        save_session(path, SessionState(frames, chain, replace(view, view='aligned')))
        reopened = load_session(path)
        assert fingerprint(reopened.registration) == fingerprint(chain)
        assert reopened.registration.correspondence_diagnostics == chain.correspondence_diagnostics
        del reopened
    save_report()
    last_print = -100
    print('Full graph, window 3', flush=True)
    graph, error, timing = profile_attempt(lambda: register_graph(
        frames, method=args.method, deep_options=options, window=3, progress=progress), torch, args.device)
    report['graph'] = {'timing': timing, 'available': graph is not None}
    if error is not None:
        report['graph']['error'] = error_details(error)
        save_report()
        raise error
    robust = solve_robust_graph(graph, RobustConfig())
    graph = replace(graph, robust_trials=(robust,))
    item = report['graph']
    item.update(config=asdict(graph.config), measured_pairs=graph.measured_pairs,
                edge_statuses=dict(Counter(edge.status for edge in graph.edges)),
                ls_complete=graph.positions is not None, chain_complete=graph.chain_positions is not None,
                components=[len(component) for component in graph.components],
                measurement_s=graph.measurement_s, ls_solver_s=graph.solver_s,
                huber_status=robust.status, huber_iterations=robust.iterations, huber_solver_s=robust.solver_s,
                missing_pairs=[{'current_pair':[edge.i+1,edge.j+1], 'reason':edge.reason,
                                'diagnostics':asdict(edge.correspondence_diagnostics) if edge.correspondence_diagnostics is not None else None}
                               for edge in graph.edges if edge.shift_xy is None])
    archive = args.output / 'graph-candidate.stmsession'
    save_session(archive, SessionState(frames, display=view, graph=graph))
    reopened = load_session(archive)
    assert reopened.graph == graph and reopened.registration is None
    del reopened
    save_report()
    if graph.positions is not None:
        item['lifecycle'] = lifecycle(frames, graph, args.output, view)
    assert report['original_hashes'] == [hashlib.sha256(frame.data.tobytes()).hexdigest() for frame in frames]
    item['process_peak_rss_mib_with_sessions_exports'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report['isolated_source_modules_after_job'] = [name for name in sys.modules if name.startswith('_stmviewer_eloftr_')]
    save_report()
    print('Completed:', args.output / 'report.json', flush=True)


if __name__ == '__main__':
    main()
