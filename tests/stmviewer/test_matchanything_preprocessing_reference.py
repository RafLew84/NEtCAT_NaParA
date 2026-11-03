"""Optional pixel-for-pixel comparison against pinned authors' preprocessing functions."""
import ast
from hashlib import sha256
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_MATCHANYTHING_ROOT'),
                               reason='Requires explicitly downloaded pinned reference source')
HASHES = {
    'match_dense.py': '9f3bb4e8c0a652cddc20f7170e1843f81e07c31b25a826c139ee4b14e50bef73',
    'extract_features.py': 'edc3884390b66924bc87ab8584e123bccb4ada72bd347bc4666f2b6ad5177204',
    'matchanything.py': '33b2f4a2f892c536b8bf54f26c858bcaf61791f362c4a3f65f603e0ab2e62b6a',
}


def reference_input(raw):
    import cv2
    import PIL
    from PIL import Image
    import torch
    from torchvision.transforms import functional as F
    torch.set_num_threads(4)
    root = Path(os.environ['STMVIEWER_TEST_MATCHANYTHING_ROOT']) / 'reference'
    trees = {}
    for name, expected in HASHES.items():
        data = (root / name).read_bytes()
        assert sha256(data).hexdigest() == expected
        trees[name] = ast.parse(data)
    confs = next(node.value for node in trees['match_dense.py'].body
                 if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'confs'
                                                         for t in node.targets))
    preset = ast.literal_eval(next(value for key, value in zip(confs.keys, confs.values)
                                   if isinstance(key, ast.Constant) and key.value == 'matchanything_eloftr'))
    scope = {'np': np, 'cv2': cv2, 'PIL': PIL, 'Image': Image, 'torch': torch, 'F': F,
             'conf': SimpleNamespace(**preset['preprocessing'])}
    helper = next(node for node in trees['extract_features.py'].body
                  if isinstance(node, ast.FunctionDef) and node.name == 'resize_image')
    parent = next(node for node in trees['match_dense.py'].body
                  if isinstance(node, ast.FunctionDef) and node.name == 'match_images')
    preprocess = next(node for node in parent.body if isinstance(node, ast.FunctionDef) and node.name == 'preprocess')
    exec(compile(ast.Module(body=[helper, preprocess], type_ignores=[]), 'pinned-match-images', 'exec'), scope)
    tensor, _ = scope['preprocess'](np.repeat(raw[..., None], 3, axis=2))
    # Execute the pinned wrapper's resize helpers, excluding its heavyweight model imports.
    helpers = [node for node in trees['matchanything.py'].body if isinstance(node, ast.FunctionDef)
               and node.name in ('resize', 'process_resize', 'resize_image', 'pad_bottom_right')]
    exec(compile(ast.Module(body=helpers, type_ignores=[]), 'pinned-matchanything-wrapper', 'exec'), scope)
    rgb = (tensor.numpy().transpose(1, 2, 0) * 255).astype(np.uint8)
    gray = np.asarray(Image.fromarray(rgb).convert('L'))
    resized, _, mask = scope['resize'](gray, df=32)
    return resized / 255., mask


@pytest.mark.parametrize('shape', [(80, 80), (137, 219), (1001, 301)])
def test_prepared_pixels_equal_pinned_reference_including_upscale_and_max_resize(shape):
    from stmviewer.matchanything_matcher import prepare_matchanything_image
    raw = np.random.default_rng(20261102).integers(0, 256, shape, dtype=np.uint8)
    raw[0, :2] = (0, 255)
    expected, mask = reference_input(raw)
    actual, geometry = prepare_matchanything_image(raw.astype(np.float64))
    np.testing.assert_array_equal(actual, expected)
    assert mask[:480].all() and not mask[480:].any()
    assert geometry.padding_ltrb == (0, 0, 0, 160)
