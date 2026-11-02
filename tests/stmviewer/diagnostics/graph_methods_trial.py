"""REG-08e real estimators: known XY or local STM, saved candidates and lifecycle checks."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import importlib.abc
import json
from pathlib import Path
import resource
import sys
from time import perf_counter
import urllib.request

import numpy as np

from graph_application_trial import correct, fingerprint, prefix
from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
from stmviewer.graph_preview import GraphMoviePreview
from stmviewer.graph_registration import register_graph
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.registration import CPU_METHODS, REGISTRATION_METHODS
from stmviewer.robust_graph import measurement_id, solve_robust_graph
from stmviewer.robust_graph_types import RobustConfig
from stmviewer.series import open_frame_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState


class NoModel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('torch', 'kornia'):
            raise ImportError('CPU graph must work without model libraries.')
        return None


def known_movie(output):
    from scipy.ndimage import gaussian_filter
    from make_registration_fixtures import write_movie
    positions = ((0, 0), (2, -1), (1, 1), (-2, 0), (3, 2), (-1, -2), (0, 1), (2, 0))
    scene = gaussian_filter(np.random.default_rng(8085).normal(size=(320, 320)), 1.2)
    scene[52:87, 49:111] += 2
    scene[149:183, 178:241] -= 2
    scene[193:247, 60:80] += 1.5
    scene[226:247, 60:136] += 1.5
    frames = [scene[30+y:286+y, 30+x:286+x].copy() for x, y in positions]
    write_movie(output / 'known.mpp', frames)
    (output / 'known.json').write_text(json.dumps({'positions_xy': positions}, indent=2)+'\n')
    return output / 'known.mpp', np.asarray(positions)


def lifecycle(frames, graph, output, view):
    """Exercise real public application/session/export paths for every complete solver."""
    results = []
    prior = None
    variants = [('ls', None)] + [('huber', item.revision) for item in graph.robust_trials if item.positions is not None]
    for name, revision in variants:
        tick = perf_counter()
        applied = apply_graph_to_movie(frames, graph, robust_revision=revision, previous=prior)
        apply_s = perf_counter()-tick
        corrected = correct(applied, 1, 0, 1)
        path = output / f'{name}-corrected.stmsession'
        save_session(path, SessionState(frames, corrected, view, graph))
        loaded = load_session(path)
        assert loaded.graph == graph
        assert loaded.registration.graph_application == corrected.graph_application
        assert fingerprint(loaded.registration) == fingerprint(corrected)
        assert loaded.registration.corrections == corrected.corrections
        del loaded
        if prior is not None:
            restored = restore_movie_result(frames, corrected)
            assert fingerprint(restored) == fingerprint(prior)
            del restored
        small = prefix(corrected, min(5, len(frames)))
        mpp = save_aligned_mpp(output / f'{name}-five-frames.mpp', small)
        reopened = open_frame_series([mpp])
        for expected, actual in zip(small.frames, reopened, strict=True):
            assert actual.data.tobytes() == expected.image.data.tobytes()
            assert actual.alignment.shift_xy == expected.shift_xy
        for codec in ('FFV1', 'MJPG'):
            save_avi(output / f'{name}-{codec}.avi', prepare_avi(
                tuple(frame.image for frame in applied.frames), start=1, end=min(12,len(frames)),
                fps=5, codec=codec, presentation=MoviePresentation(pixel_proportions=True, background=255)))
        results.append({'solver': name, 'apply_s': apply_s, 'canvas': applied.canvas_shape,
                        'session_mpp_avi_manual_roundtrip': 'passed', 'restored_previous': prior is not None})
        prior = applied
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', type=Path, help='Omit to generate independent crops with known XY.')
    parser.add_argument('--methods', nargs='+', choices=tuple(REGISTRATION_METHODS), default=list(CPU_METHODS))
    parser.add_argument('--windows', type=int, nargs='+', choices=(3,5), default=[3])
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--device', choices=('cpu','cuda'), default='cuda')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    torch = None
    if all(method in CPU_METHODS for method in args.methods):
        sys.meta_path.insert(0, NoModel())
    else:
        import torch
        torch.set_num_threads(4)
        def no_download(*a, **kw):
            raise RuntimeError('This diagnostic prohibits model downloads.')
        torch.hub.load_state_dict_from_url = no_download
        torch.hub.download_url_to_file = no_download
        urllib.request.urlopen = no_download
    source, truth = (args.source, None) if args.source else known_movie(args.output)
    frames = open_frame_series([source])[args.drop_first:]
    with source.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'source': str(source), 'source_sha256': source_hash, 'drop_first': args.drop_first,
              'count': len(frames), 'shape': frames[0].data.shape, 'runs': [],
              'quality': 'Known XY only for generated crops; real STM requires human review.'}
    original = tuple(hashlib.sha256(frame.data.tobytes()).hexdigest() for frame in frames)
    for method in args.methods:
        previous = None
        for window in args.windows:
            out = args.output / f'{method}-window{window}'
            out.mkdir()
            print(f'{method}, window {window}', flush=True)
            last = -100
            def progress(done,total,text):
                nonlocal last
                if done >= last+100 or done == total:
                    print(f'  {done}/{total}: {text}', flush=True)
                    last = done
            if torch is not None and args.device == 'cuda':
                torch.cuda.reset_peak_memory_stats()
            tick = perf_counter()
            graph = register_graph(frames, method=method, window=window, previous=previous,
                                   deep_options=DeepMatcherOptions(args.weights,args.device), progress=progress)
            elapsed = perf_counter()-tick
            identity = measurement_id(graph)
            robust = solve_robust_graph(graph, RobustConfig())
            assert identity == measurement_id(graph)
            graph = replace(graph, robust_trials=(robust,))
            view = SessionViewState(pixel_proportions=True, deep_weights=str(args.weights) if args.weights else None,
                                    deep_device=args.device)
            archive = out / 'candidate.stmsession'
            save_session(archive, SessionState(frames, display=view, graph=graph))
            reopened = load_session(archive)
            assert reopened.graph == graph and reopened.registration is None
            del reopened
            item = {'method':method,'window':window,'config':asdict(graph.config),
                    'wall_s':elapsed,'measurement_s':graph.measurement_s,'ls_solver_s':graph.solver_s,
                    'measured_pairs':graph.measured_pairs,'reused_pairs':graph.reused_pairs,
                    'edge_statuses':dict(Counter(edge.status for edge in graph.edges)),
                    'missing_reasons':dict(Counter(edge.reason for edge in graph.edges if edge.shift_xy is None)),
                    'ls_complete':graph.positions is not None,'huber_status':robust.status,
                    'huber_reason':robust.reason,'huber_iterations':robust.iterations,'huber_solver_s':robust.solver_s}
            variants = {name:positions for name,positions in [('ls',graph.positions),('huber',robust.positions),
                                                              ('chain',graph.chain_positions)] if positions is not None}
            if variants:
                preview = GraphMoviePreview(frames, variants)
                render_s = []
                for name in variants:
                    for i in range(len(frames)):
                        tick = perf_counter()
                        preview.render(i,name)
                        render_s.append(perf_counter()-tick)
                item['render_p95_ms'] = float(np.percentile(render_s,95)*1000)
            if truth is not None:
                item['max_coordinate_error_px'] = {name:float(np.max(np.abs(np.asarray(positions)-truth)))
                                                   for name,positions in variants.items()}
            if graph.positions is not None:
                item['lifecycle'] = lifecycle(frames,graph,out,view)
            assert tuple(hashlib.sha256(frame.data.tobytes()).hexdigest() for frame in frames) == original
            item['process_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
            item['cuda_peak_mib'] = torch.cuda.max_memory_allocated()/2**20 if torch is not None and args.device=='cuda' else None
            report['runs'].append(item)
            report['model_imported'] = any(name.split('.')[0] in ('torch','kornia') for name in sys.modules)
            (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
            print(f'  LS={item["ls_complete"]}, Huber={robust.status}; saved {archive}', flush=True)
            previous=graph


if __name__ == '__main__':
    main()
