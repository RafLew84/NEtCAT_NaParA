"""REG-11 real movie attempts through the isolated RoMa worker.

PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/roma_trial.py
    OUTPUT --source data/MOVIE_4.mpp --drop-first 2 --device cuda
Model support is not independent evidence of STM registration quality.
"""
import argparse
from collections import Counter
import cProfile
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
from threading import Event, Thread
from time import perf_counter

import psutil

from graph_application_trial import fingerprint
from graph_methods_trial import lifecycle
from stmviewer.graph_registration import register_graph
from stmviewer.registration import register_series
from stmviewer.roma_matcher import default_roma_options
from stmviewer.robust_graph import solve_robust_graph
from stmviewer.robust_graph_types import RobustConfig
from stmviewer.series import open_frame_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState


class Resources:
    """Observed process-tree RSS and driver GPU allocations, sampled every second."""
    def __init__(self):
        self.done = Event()
        self.process = psutil.Process()
        self.peak_rss_mib = 0.
        self.peak_driver_vram_mib = 0.
        self.gpu_probe_errors = []
        self.thread = Thread(target=self.sample, daemon=True)

    def sample(self):
        while not self.done.is_set():
            try:
                processes = [self.process] + self.process.children(recursive=True)
                live = {p.pid: p.memory_info().rss for p in processes if p.is_running()}
                self.peak_rss_mib = max(self.peak_rss_mib, sum(live.values()) / 2**20)
                result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory',
                                         '--format=csv,noheader,nounits'], capture_output=True,
                                        text=True, timeout=3, check=True)
                gpu = 0.
                for line in result.stdout.splitlines():
                    pid, memory = line.split(',')
                    if int(pid.strip()) in live:
                        gpu += float(memory.strip())
                self.peak_driver_vram_mib = max(self.peak_driver_vram_mib, gpu)
            except (psutil.Error, OSError, ValueError, subprocess.SubprocessError) as error:
                message = str(error)
                if message not in self.gpu_probe_errors:
                    self.gpu_probe_errors.append(message)
            self.done.wait(1.)


def profile_attempt(function):
    resources = Resources()
    resources.thread.start()
    profile = cProfile.Profile()
    start = perf_counter()
    result = error = None
    profile.enable()
    try:
        result = function()
    except Exception as caught:
        error = caught
    finally:
        profile.disable()
        resources.done.set()
        resources.thread.join(timeout=5.)
    timing = {'wall_s': perf_counter() - start, 'consensus_s': 0., 'renderer_s': 0.,
              'solver_s': 0., 'worker_rpc_s': 0.,
              'sampled_tree_peak_rss_mib': resources.peak_rss_mib,
              'sampled_tree_peak_driver_vram_mib': resources.peak_driver_vram_mib,
              'parent_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              'children_peak_rss_mib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024,
              'gpu_probe_errors': resources.gpu_probe_errors,
              'note': 'RSS/driver VRAM sampled at 1 s, not an 8 GB acceptance test. '
                      'Worker RPC includes transport and model work. Child RSS is process-lifetime high water.'}
    for entry in profile.getstats():
        code = entry.code
        if isinstance(code, str):
            continue
        if code.co_name == 'estimate_correspondence_translation':
            timing['consensus_s'] += entry.totaltime
        elif code.co_name == 'render_registration':
            timing['renderer_s'] += entry.totaltime
        elif code.co_name == 'solve_graph':
            timing['solver_s'] += entry.totaltime
        elif code.co_name == 'match' and 'roma_process' in code.co_filename:
            timing['worker_rpc_s'] += entry.totaltime
    return result, error, timing


def error_details(error):
    record = {'type': type(error).__name__, 'reason': str(error)}
    current = error
    while current is not None:
        evidence = getattr(current, 'diagnostics', None)
        if evidence is not None:
            record['diagnostics'] = asdict(evidence)
            break
        current = current.__cause__
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    parser.add_argument('--preset', default='turbo')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    options = replace(default_roma_options(), device=args.device, preset=args.preset)
    frames = open_frame_series([args.source])[args.drop_first:]
    with args.source.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'source': str(args.source.resolve()), 'source_sha256': source_hash,
              'drop_first': args.drop_first, 'frames': len(frames), 'shape': frames[0].data.shape,
              'device': args.device, 'preset': args.preset,
              'quality': 'No independent STM ground truth; image quality awaits human review.',
              'original_hashes': [hashlib.sha256(f.data.tobytes()).hexdigest() for f in frames]}

    def save():
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    last = -100
    last_description = ''

    def progress(done, total, text):
        nonlocal last, last_description
        last_description = text
        if done >= last + 100 or done == total:
            print(f'{done}/{total}: {text}', flush=True)
            last = done

    view = SessionViewState(pixel_proportions=True, method='roma_v2', deep_device=args.device,
                            deep_weights=str(options.weights), deep_source=str(options.source),
                            deep_interpreter=str(options.interpreter), deep_preset=options.preset,
                            deep_samples=options.samples, deep_seed=options.seed)
    print('Adjacent registration:', args.source, flush=True)
    chain, error, timing = profile_attempt(lambda: register_series(
        frames, method='roma_v2', deep_options=options, progress=progress))
    report['chain'] = {'complete': chain is not None, 'timing': timing,
                       'last_progress': last_description}
    if error is not None:
        report['chain']['error'] = error_details(error)
    if chain is not None:
        report['chain'].update(canvas=chain.canvas_shape, actual_device=chain.device,
                               statuses=dict(Counter(f.status for f in chain.frames)))
        save_session(args.output / 'chain.stmsession', SessionState(frames, chain, replace(view, view='aligned')))
        reopened = load_session(args.output / 'chain.stmsession')
        assert fingerprint(reopened.registration) == fingerprint(chain)
        assert reopened.registration.correspondence_diagnostics == chain.correspondence_diagnostics
        del reopened, chain
    save()
    last = -100
    print('Full graph: window 3', flush=True)
    graph, error, timing = profile_attempt(lambda: register_graph(
        frames, method='roma_v2', deep_options=options, window=3, progress=progress))
    report['graph'] = {'available': graph is not None, 'timing': timing}
    if error is not None:
        report['graph']['error'] = error_details(error)
        save()
        raise error
    robust = solve_robust_graph(graph, RobustConfig())
    graph = replace(graph, robust_trials=(robust,))
    item = report['graph']
    item.update(config=asdict(graph.config), measured_pairs=graph.measured_pairs,
                edge_statuses=dict(Counter(e.status for e in graph.edges)),
                ls_complete=graph.positions is not None, chain_complete=graph.chain_positions is not None,
                components=[len(c) for c in graph.components], measurement_s=graph.measurement_s,
                ls_solver_s=graph.solver_s, huber_status=robust.status,
                huber_iterations=robust.iterations, huber_solver_s=robust.solver_s,
                missing_pairs=[{'pair': [e.i+1,e.j+1], 'reason': e.reason} for e in graph.edges
                               if e.shift_xy is None])
    archive = args.output / 'graph-candidate.stmsession'
    save_session(archive, SessionState(frames, display=view, graph=graph))
    reopened = load_session(archive)
    assert reopened.graph == graph and reopened.registration is None
    del reopened
    save()
    if graph.positions is not None:
        item['lifecycle'] = lifecycle(frames, graph, args.output, view)
    assert report['original_hashes'] == [hashlib.sha256(f.data.tobytes()).hexdigest() for f in frames]
    report['model_modules_in_parent'] = [name for name in sys.modules
                                         if name.split('.')[0] in ('romav2', 'dinov3', 'torch')]
    save()
    print('Completed:', args.output / 'report.json', flush=True)


if __name__ == '__main__':
    main()
