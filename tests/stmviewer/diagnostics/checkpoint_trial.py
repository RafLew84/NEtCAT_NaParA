"""Opt-in comparison of classic LoFTR checkpoints, outside application defaults.

Indoor New needs temp_bug_fix=True; merely selecting its weights in the current
GUI does not set that configuration. Every constructed model gets a fresh config.
This harness changes the constructor only within its process, uses real weights
and the unchanged Viewer/translation pipeline, and never downloads anything.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

from local_consensus_trial import main as run_trial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--variant', choices=['outdoor', 'indoor', 'indoor_new'], required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--drop-first', type=int, default=0)
    parser.add_argument('--pair', action='append', type=int)
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()

    import kornia.feature
    from kornia.feature.loftr.loftr import default_cfg

    original_constructor = kornia.feature.LoFTR
    original_config = deepcopy(default_cfg)
    configuration = deepcopy(default_cfg)
    configuration['coarse']['temp_bug_fix'] = args.variant == 'indoor_new'

    def configured_model(*values, **options):
        if values or options != {'pretrained': None}:
            raise ValueError('Expected the local-only LoFTR constructor from STM Viewer.')
        return original_constructor(pretrained=None, config=deepcopy(configuration))

    command = [sys.argv[0], str(args.source), str(args.output),
               '--weights', str(args.weights), '--device', args.device,
               '--drop-first', str(args.drop_first), '--method', 'deep_matcher_translation']
    for moving in args.pair or ():
        command.extend(['--pair', str(moving)])
    if args.export:
        command.append('--export')
    with patch.object(sys, 'argv', command), patch.object(kornia.feature, 'LoFTR', configured_model):
        result = run_trial()
    if default_cfg != original_config:
        raise RuntimeError('The experiment mutated the shared Kornia configuration.')
    report_path = args.output / 'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    report['checkpoint_variant'] = args.variant
    report['loftr_configuration'] = configuration
    report['configuration_scope'] = 'Explicit experimental constructor; application defaults unchanged.'
    report['backend_label_notice'] = (
        'The injected translation backend retains its historical pretrained=outdoor label. '
        'It does not select the weights. Actual weights/SHA and checkpoint_variant above '
        'identify this experiment; Indoor New cannot be reproduced by just selecting its file in the GUI.'
    )
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    raise SystemExit(main())
