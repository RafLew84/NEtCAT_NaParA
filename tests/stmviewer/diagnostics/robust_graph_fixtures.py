"""REG-08b: separate development measurements and fresh visual acceptance scenes.

These supplied measurements evaluate the graph solver, not Deep. Sources and
pixel samples are generated locally; no external data/model is needed.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from make_registration_fixtures import write_movie
from stmviewer.graph_registration import graph_pairs, solve_graph
from stmviewer.graph_provenance import graph_sources
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphSource
from stmviewer.robust_graph import solve_robust_graph
from stmviewer.robust_graph_types import RobustConfig
from stmviewer.series import open_frame_series
from stmviewer.session_archive import save_session
from stmviewer.session_state import SessionState

ACCEPTANCE_XY = ((0., 0.), (5., -3.), (11., -7.), (8., 2.), (-6., 5.),
                 (-3., -8.), (7., -1.), (2., 9.), (-8., 4.))


def config():
    return GraphConfig(3, 'supplied-measurements-no-model', '0'*64, 'cpu', 'CPU',
                       (('measurement', 'reg08b-supplied-v1'),), (), 'reg08b-fixture-v1')


def development(destination: Path) -> None:
    """Threshold comparison only here; acceptance scenes below are not used to tune."""
    rows = []
    for seed in (808100, 808101, 808102):
        rng = np.random.default_rng(seed)
        t = np.linspace(0, 3*np.pi, 17)
        truth = np.column_stack((12*np.sin(t), 9*np.cos(t)))
        truth -= truth[0]
        sources = tuple(GraphSource('development', i, (16, 16), '0'*64) for i in range(len(truth)))
        noise = {pair: rng.normal(0, .8, 2) for pair in graph_pairs(len(truth), 3)}
        for contaminated in (False, True):
            edges = tuple(GraphEdge(i, j, tuple(float(v) for v in truth[j]-truth[i]+noise[i, j]
                                  + (np.array([20., -16.]) if contaminated and (i, j) == (5, 8) else 0)), 'ok')
                          for i, j in graph_pairs(len(truth), 3))
            graph = solve_graph(sources, edges, config())
            ls_error = float(np.sqrt(np.mean((np.asarray(graph.positions)-truth)**2)))
            for threshold in (.5, 1., 2., 4., 8.):
                result = solve_robust_graph(graph, RobustConfig(threshold_px=threshold))
                rows.append({'seed': seed, 'one_outlier': contaminated, 'threshold_px': threshold,
                             'status': result.status, 'reason': result.reason, 'iterations': result.iterations,
                             'ls_rmse_px': ls_error,
                             'huber_rmse_px': float(np.sqrt(np.mean((np.asarray(result.positions)-truth)**2)))
                               if result.positions is not None else None,
                             'downweighted': sum(w is not None and w < .99 for w in result.weights),
                             'edge_count': len(edges)})
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'development.json').write_text(json.dumps(rows, indent=2, allow_nan=False)+'\n')


def acceptance(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(808290)  # Separate from the development networks.
    y, x = np.mgrid[:400, :400]
    texture = gaussian_filter(rng.normal(size=x.shape), 1.1)
    for _ in range(180):
        cx, cy = rng.uniform(0, 400, 2)
        sx, sy = rng.uniform(2, 8, 2)
        texture += rng.uniform(-3, 3)*np.exp(-((x-cx)/sx)**2-((y-cy)/sy)**2)
    texture[140:160, 135:165] += 3
    texture[240:257, 250:281] -= 3
    periodic = np.cos(2*np.pi*x/24)+np.sin(2*np.pi*y/24)+.5*np.cos(2*np.pi*(x+y)/24)
    yy, xx = np.mgrid[:256, :256]
    truth = np.asarray(ACCEPTANCE_XY)
    manifest = {'positions_xy': ACCEPTANCE_XY, 'role': 'Fresh acceptance scenes; never used to tune defaults.',
                'cases': {}}
    for scenario in ('one-outlier', 'bridge', 'tree', 'disconnected', 'periodic-alias', 'majority-wrong'):
        scene = periodic if scenario == 'periodic-alias' else texture
        arrays = tuple(map_coordinates(scene, [yy+70+dy, xx+70+dx], order=1) for dx, dy in truth)
        path = destination/f'{scenario}.mpp'
        write_movie(path, arrays)
        frames = open_frame_series([path])
        edges = []
        for i, j in graph_pairs(len(frames), 3):
            shift = truth[j]-truth[i]
            missing = ((scenario in ('bridge', 'disconnected') and i < 4 <= j
                        and not (scenario == 'bridge' and (i, j) == (3, 4)))
                       or (scenario == 'tree' and j-i != 1))
            if scenario == 'one-outlier' and (i, j) == (2, 5):
                shift = shift+np.array([18., -14.])
            if scenario == 'bridge' and (i, j) == (3, 4):
                shift = shift+np.array([18., -14.])
            if scenario == 'periodic-alias' or (scenario == 'majority-wrong' and (i, j) not in ((1, 2), (5, 6))):
                shift = shift+np.array([24.*(j-i), 0.])
            edges.append(GraphEdge(i, j, None if missing else tuple(float(v) for v in shift), 'missing' if missing else 'ok',
                                   'Zadany brak relacji we wzorcu solvera.' if missing else None))
        graph = solve_graph(graph_sources(frames), tuple(edges), config())
        # Save LS-only input so the user can actually run and compare thresholds.
        save_session(destination/f'{scenario}.stmsession', SessionState(frames, graph=graph))
        result = solve_robust_graph(graph, RobustConfig())
        graph = replace(graph, robust_trials=(result,))
        save_session(destination/f'{scenario}-with-huber.stmsession', SessionState(frames, graph=graph))
        manifest['cases'][scenario] = {'source': path.name, 'status': result.status, 'reason': result.reason,
                                      'ls_positions': graph.positions, 'huber_positions': result.positions,
                                      'weights': result.weights,
                                      'caution': 'Supplied measurements, not model output; small residuals need not mean correct structure.'}
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['development', 'acceptance'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    (development if args.mode == 'development' else acceptance)(args.output)
