"""Deterministic manual REG-08a scenes and supplied-measurement solver sessions.

Run with PYTHONPATH=.:tests/stmviewer from the repository. The generated files
stay outside Git; supplied measurements test the solver, not learned matching.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from make_registration_fixtures import write_movie
from stmviewer.graph_registration import graph_pairs, solve_graph
from stmviewer.graph_types import GraphConfig, GraphEdge
from stmviewer.graph_provenance import graph_sources
from stmviewer.series import open_frame_series
from stmviewer.session_archive import save_session
from stmviewer.session_state import SessionState

POSITIONS = ((0., 0.), (7., -4.), (18., -9.), (11., 2.), (-4., 10.), (-9., 3.), (3., -5.))


def generate(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(8081)
    y, x = np.mgrid[:400, :400]
    scene = gaussian_filter(rng.normal(size=x.shape), 1.1)
    for _ in range(220):
        cx, cy = rng.uniform(0, 400, 2)
        sx, sy = rng.uniform(1.4, 7, 2)
        scene += rng.uniform(-3, 3) * np.exp(-((x-cx)/sx)**2 - ((y-cy)/sy)**2)
    scene[130:153, 143:177] += 2
    scene[230:252, 250:269] -= 2
    yy, xx = np.mgrid[:256, :256]
    arrays = tuple(map_coordinates(scene, [yy+70+dy, xx+70+dx], order=1)
                   for dx, dy in POSITIONS)
    source = destination / 'known-xy.mpp'
    write_movie(source, arrays)
    frames = open_frame_series([source])
    sources = graph_sources(frames)
    config = GraphConfig(3, 'supplied-measurements-no-model', '0'*64, 'cpu', 'CPU',
                         (('measurement', 'known-scene-v1'),), (), 'manual-fixture-v1')
    manifest = {'positions_xy': POSITIONS, 'note': 'Separate crops of a larger scene; no wrap/fill.',
                'solver_sessions': {}}
    for name in ('complete', 'bypass', 'bridge', 'disconnected', 'periodic-alias'):
        edges = []
        for i, j in graph_pairs(len(frames), 3):
            shift = (POSITIONS[j][0]-POSITIONS[i][0], POSITIONS[j][1]-POSITIONS[i][1])
            missing = ((name == 'bypass' and (i, j) == (2, 3))
                       or (name in ('bridge', 'disconnected') and i < 3 <= j
                           and not (name == 'bridge' and (i, j) == (2, 3))))
            if name == 'periodic-alias':
                shift = (shift[0]+24*(j-i), shift[1])
            edges.append(GraphEdge(i, j, None if missing else shift,
                                   'missing' if missing else 'ok',
                                   'Kontrolowany brak pomiaru we wzorcu solvera.' if missing else None))
        graph = solve_graph(sources, tuple(edges), config)
        save_session(destination / f'solver-{name}.stmsession', SessionState(frames, graph=graph))
        manifest['solver_sessions'][name] = {
            'complete_positions': graph.positions is not None,
            'components_1based': [[i+1 for i in c] for c in graph.components],
            'bridges_1based': [[i+1, j+1] for i, j in graph.bridges],
            'caution': 'Supplied measurements, not model output. An alias can have zero residual.'}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    generate(parser.parse_args().output)
