"""Private subprocess entry point: keep optional native computation out of Qt."""

import json
from pathlib import Path
import sys

import numpy as np


def main() -> None:
    import freud
    freud.parallel.set_num_threads(1)
    with np.load(sys.argv[1], allow_pickle=False) as data:
        xy = data['points']
        points = np.column_stack((xy-xy.mean(axis=0), np.zeros(len(xy)))).astype(np.float32)
        box = freud.box.Box(float(np.ptp(points[:, 0])+4), float(np.ptp(points[:, 1])+4), is2D=True)
        box.periodic = (False, False, False)
        def neighbors(q, t):
            return freud.locality.NeighborList.from_arrays(len(points), len(points), q, t, points[t]-points[q])
        env = neighbors(data['query'], data['neighbor'])
        eligible = data['eligible']
        left, right = np.triu_indices(len(eligible), 1)
        pairs = neighbors(eligible[left].astype(np.uint32), eligible[right].astype(np.uint32))
        result = freud.environment.EnvironmentCluster().compute((box, points), float(data['tolerance']),
            cluster_neighbors=pairs, env_neighbors=env, registration=bool(data['registration']))
        Path(sys.argv[2]).write_text(json.dumps({'labels': result.cluster_idx.tolist(), 'version': freud.__version__}))


if __name__ == '__main__':
    main()
