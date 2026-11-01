"""REG-08d manual fixtures with supplied relations, independent of model accuracy."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from make_registration_fixtures import write_movie
from stmviewer.graph_application import apply_graph_to_movie
from stmviewer.graph_provenance import graph_sources
from stmviewer.graph_registration import graph_pairs, solve_graph
from stmviewer.graph_types import GraphConfig, GraphEdge
from stmviewer.long_references import plan_long_references, solve_extended_graph
from stmviewer.series import open_frame_series
from stmviewer.session_archive import save_session
from stmviewer.session_state import SessionState, SessionViewState


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    positions = tuple((float((i * 7) % 23 - (0 if i == 0 else 4)),
                       float((i * 5) % 17 - (0 if i == 0 else 3))) for i in range(18))
    rng = np.random.default_rng(808401)
    yy, xx = np.mgrid[:400, :400]
    irregular = gaussian_filter(rng.normal(size=(400, 400)), 1.3)
    irregular[155:177, 141:161] += 4
    irregular[203:222, 243:275] -= 4
    periodic = np.cos(2 * np.pi * xx / 24) + np.sin(2 * np.pi * yy / 18)
    y, x = np.mgrid[:256, :256]
    report = {'positions_xy': positions, 'references_1based': [1], 'target_range_1based': [7, 18],
              'note': 'Supplied measurements; neither these sessions nor their residuals validate Deep.', 'cases': {}}
    for case in ('correct-long-links', 'periodic-alias', 'missing-long-links'):
        scene = periodic if case == 'periodic-alias' else irregular
        samples = tuple(map_coordinates(scene, [y + 60 + py, x + 60 + px], order=1)
                        for px, py in positions)
        source = output / f'{case}.mpp'
        write_movie(source, samples)
        frames = open_frame_series([source])
        config = GraphConfig(3, 'supplied-relations-no-model', '0' * 64, 'cpu', 'CPU',
                             (('measurement', 'long-reference-fixture-v1'),), (), 'supplied-v1')
        def measured(i, j, *, distant=False):
            delta = positions[j][0] - positions[i][0], positions[j][1] - positions[i][1]
            if case == 'periodic-alias':
                return delta[0] + 24 * (int(j >= 9) - int(i >= 9)), delta[1]
            return delta if distant else (delta[0] + .8 * (j - i), delta[1])
        base = solve_graph(graph_sources(frames), tuple(
            GraphEdge(i, j, measured(i, j), 'ok') for i, j in graph_pairs(len(frames), 3)), config)
        pairs = plan_long_references(base, (0,), 6, 17)
        additions = tuple(GraphEdge(i, j, None, 'missing', 'Kontrolowany brak wspólnych struktur.')
                          if case == 'missing-long-links' else GraphEdge(i, j, measured(i, j, distant=True), 'ok')
                          for i, j in pairs)
        extended = solve_extended_graph(base, additions, references=(0,), target_start=6,
                                         target_end=17, measurement_config=config)
        active = apply_graph_to_movie(frames, base)
        view = SessionViewState(view='aligned')
        save_session(output / f'{case}-base.stmsession', SessionState(frames, active, view, base))
        save_session(output / f'{case}-extended.stmsession', SessionState(frames, active, view, extended))
        error_before = float(np.max(np.abs(np.asarray(base.positions) - positions)))
        error_after = float(np.max(np.abs(np.asarray(extended.positions) - positions)))
        report['cases'][case] = {'window_max_coordinate_error_px': error_before,
                                 'extended_max_coordinate_error_px': error_after,
                                 'new_pairs': len(pairs),
                                 'missing_pairs': sum(e.shift_xy is None for e in additions),
                                 'max_residual_px': max(np.hypot(*e.residual_xy) for e in extended.edges
                                                        if e.residual_xy is not None)}
        if case == 'correct-long-links':
            assert error_after < error_before
        else:
            np.testing.assert_allclose(extended.positions, base.positions, atol=1e-9)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report['cases'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    generate(parser.parse_args().output)
