"""Post-freeze input-footprint audit; exploratory ROI never supplies labels."""
from __future__ import annotations

import numpy as np

from .e1_run import compact
from .e5_catalog import PATCHES
from .e5_metrics import context_summary
from .e5_support import footprint_context


def audit_context(bank, out, index, truths, check_budget):
    unique = {entry['shared']: entry for entry in index}
    count = 0
    with (out / 'context-audit.jsonl').open('w') as stream:
        for path, entry in sorted(unique.items()):
            check_budget()
            rows = bank.inputs.rows(entry)
            xy = np.asarray([row['raw_edge_xy'] for row in rows], float).reshape(-1, 2)
            with np.load(out / path, allow_pickle=False) as z: data = dict(z)
            _, truth = truths['controls' if entry['kind'] == 'synthetic' else 'references'].get(entry['sample_id'], ({}, {}))
            frame = bank.inputs.group(entry)['record'].get('frame_number')
            spacing = np.asarray(entry['pixel_spacing_xy'], float)
            if not np.allclose(spacing, spacing[0]) or spacing[0] <= 0:
                raise ValueError('E5 footprint audit requires isotropic positive spacing')
            rois = ([dict(id='A', bbox_raw_xyxy=[64, 24, 176, 104]),
                     dict(id='B', bbox_raw_xyxy=[218, 58, 250, 126])]
                    if entry['kind'] == 'measurement' and frame is not None and 259 <= frame <= 266 else [])
            for patch, (scale, _) in PATCHES.items():
                eligible = data[f'{patch}__scope'] & data[f'{patch}__available']
                for margin in (0., 3.):
                    result = footprint_context(data[f'{patch}__centers'], scale / spacing[0], truth, entry['kind'],
                                               margin=margin / spacing[0], anchor_xy=xy, rois=rois)
                    summary = context_summary(result, eligible)
                    stream.write(compact(dict(sample_id=entry['sample_id'], regime=entry['regime'],
                        sampler=entry['sampler'], kind=entry['kind'], patch=patch, margin_px=margin,
                        scale_reference_px=scale, scale_raw_px=scale / spacing[0],
                        margin_raw_px=margin / spacing[0],
                        summary=summary)) + '\n')
                    count += 1
    return count
