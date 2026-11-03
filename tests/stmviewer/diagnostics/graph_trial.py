"""Opt-in full-film REG-08a validation with real local Deep weights.

Run from repository with PYTHONPATH=.:tests/stmviewer. No candidate is exported
as MPP/AVI: REG-08a saves a session and renders it only for inspection.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
from time import perf_counter
import urllib.request

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_registration import register_graph
from stmviewer.graph_preview import GraphMoviePreview
from stmviewer.registration import FrameOrigin, render_registration
from stmviewer.series import open_frame_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--expected', type=Path, help='Synthetic manifest with positions_xy')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    import torch

    def no_download(*a, **kw):
        raise RuntimeError('Graph validation prohibits downloads.')

    torch.hub.load_state_dict_from_url = no_download
    torch.hub.download_url_to_file = no_download
    urllib.request.urlopen = no_download
    torch.set_num_threads(4)
    frames = open_frame_series([args.source])[args.drop_first:]
    with args.source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'source': str(args.source), 'source_sha256': digest, 'drop_first': args.drop_first,
              'count': len(frames), 'shape': frames[0].data.shape, 'runs': [],
              'visual_quality': 'Requires human review; residual is not physical ground truth.'}
    previous = None
    active = None
    for window in (3, 5):
        if args.device == 'cuda':
            torch.cuda.reset_peak_memory_stats()
        last = 0

        def progress(done, total, description):
            nonlocal last
            if done >= last + 100 or done == total:
                last = done
                print(f'window={window} {done}/{total}: {description}', flush=True)

        start = perf_counter()
        trial = register_graph(frames, window=window, deep_options=DeepMatcherOptions(args.weights, args.device),
                               previous=previous, progress=progress)
        model_solver_s = perf_counter()-start
        # Active baseline is explicitly the sum of these same adjacent measurements.
        if active is None and trial.chain_positions is not None:
            active = render_registration(frames, trial.chain_positions, ('manual_review',)*len(frames),
                                         (None,)*len(frames), (False,)*len(frames),
                                         reference=FrameOrigin(frames[0].source, frames[0].source_frame_index),
                                         method='Deep Matcher — łańcuch z pomiarów grafu', device=trial.config.device)
        variants = {}
        if trial.positions is not None:
            variants['graph'] = trial.positions
        if trial.chain_positions is not None:
            variants['chain'] = trial.chain_positions
        rendering = []
        canvas = None
        if variants:
            preview = GraphMoviePreview(frames, variants)
            canvas = preview.canvas_shape
            for key in variants:
                for index in range(len(frames)):
                    started = perf_counter()
                    preview.render(index, key)
                    rendering.append(perf_counter()-started)
        path = args.output / f'window-{window}.stmsession'
        view = SessionViewState(view='aligned' if active else 'original',
                                deep_weights=str(args.weights), deep_device=args.device)
        started = perf_counter()
        save_session(path, SessionState(frames, active, view, graph=trial))
        session_save_s = perf_counter()-started
        started = perf_counter()
        loaded = load_session(path)
        session_load_s = perf_counter()-started
        assert loaded.graph == trial
        assert (loaded.registration is None) == (active is None)
        del loaded
        record = {'window': window, 'graph': asdict(trial), 'model_solver_wall_s': model_solver_s,
                  'canvas_shape': canvas, 'session_bytes': path.stat().st_size,
                  'session_save_s': session_save_s, 'session_load_s': session_load_s,
                  'render_median_ms': float(np.median(rendering)*1000) if rendering else None,
                  'render_p95_ms': float(np.percentile(rendering, 95)*1000) if rendering else None,
                  'process_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  'peak_cuda_allocated_mib': torch.cuda.max_memory_allocated()/2**20 if args.device == 'cuda' else None,
                  'peak_cuda_reserved_mib': torch.cuda.max_memory_reserved()/2**20 if args.device == 'cuda' else None}
        if args.expected and trial.positions is not None:
            truth = np.asarray(json.loads(args.expected.read_text())['positions_xy'])
            record['graph_max_xy_error_px'] = float(np.max(np.abs(np.asarray(trial.positions)-truth)))
            if trial.chain_positions:
                record['chain_max_xy_error_px'] = float(np.max(np.abs(np.asarray(trial.chain_positions)-truth)))
        report['runs'].append(record)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        print(f'window={window}: {model_solver_s:.2f}s, saved {path}', flush=True)
        previous = trial


if __name__ == '__main__':
    main()
