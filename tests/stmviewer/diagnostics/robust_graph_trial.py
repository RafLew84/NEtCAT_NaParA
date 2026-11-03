"""REG-08b replay of saved measurements, never running or loading a matcher."""
import argparse
from dataclasses import asdict, replace
import importlib.abc
import hashlib
import json
from pathlib import Path
import resource
import sys
from time import perf_counter

import numpy as np


class NoModel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('torch', 'kornia'):
            raise ImportError('REG-08b replay explicitly forbids importing a model library.')
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--threshold', type=float, action='append')
    parser.add_argument('--max-iterations', type=int, default=200)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.meta_path.insert(0, NoModel())
    from stmviewer.graph_preview import GraphMoviePreview
    from stmviewer.robust_graph import measurement_id, solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    from stmviewer.session_archive import load_session, save_session

    state = load_session(args.session)
    graph = state.graph
    if graph is None:
        raise ValueError('Input session has no measured graph.')
    identity = measurement_id(graph)
    source_edges = graph.edges
    active_digests = tuple(hashlib.sha256(frame.image.data.tobytes()).hexdigest()
                           for frame in state.registration.frames) if state.registration else ()
    report = {'input': str(args.session), 'measurement_id': identity, 'window': graph.config.window,
              'frames': len(state.frames), 'edges': len(graph.edges), 'attempts': [],
              'note': 'No matcher; visual-quality assessment remains manual.'}
    for threshold in args.threshold or (2., 1.):
        start = perf_counter()
        result = solve_robust_graph(graph, RobustConfig(threshold_px=threshold, max_iterations=args.max_iterations))
        elapsed = perf_counter()-start
        graph = replace(graph, robust_trials=graph.robust_trials+(result,))
        assert graph.edges == source_edges and measurement_id(graph) == identity
        report['attempts'].append({'threshold_px': threshold, 'wall_s': elapsed, 'result': asdict(result)})
        print(f'threshold={threshold}: {result.status}, iterations={result.iterations}, {elapsed:.3f}s', flush=True)
    variants = {'graph': graph.positions} if graph.positions is not None else {}
    variants.update({r.revision: r.positions for r in graph.robust_trials if r.positions is not None})
    times = []
    if variants:
        preview = GraphMoviePreview(state.frames, variants)
        for variant in variants:
            for i in range(len(state.frames)):
                start = perf_counter()
                preview.render(i, variant)
                times.append(perf_counter()-start)
        report['canvas_shape'] = preview.canvas_shape
    path = args.output/'comparison.stmsession'
    save_session(path, replace(state, graph=graph))
    restored = load_session(path)
    assert restored.graph == graph
    assert (restored.registration is None) == (state.registration is None)
    if restored.registration is not None:
        assert tuple(hashlib.sha256(frame.image.data.tobytes()).hexdigest()
                     for frame in restored.registration.frames) == active_digests
    report.update(render_p95_ms=float(np.percentile(times, 95)*1000) if times else None,
                  session_bytes=path.stat().st_size,
                  process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  model_libraries_imported=any(name.split('.')[0] in ('torch', 'kornia') for name in sys.modules))
    (args.output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
