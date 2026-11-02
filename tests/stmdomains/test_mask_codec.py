"""The supported MolTrack mask encodings produce known non-square pixels."""

import base64
import zlib

import numpy as np
import pytest

from stmdomains.io.mask_codec import decode_mask


def test_rle_decodes_rows_and_reuses_the_historical_alias_without_a_copy():
    mask = decode_mask({"encoding": "rle", "shape": [2, 3], "counts": [1, 2, 3]}, (2, 3))
    np.testing.assert_array_equal(mask, [[False, True, True], [False, False, False]])
    assert not mask.flags.writeable
    alias = decode_mask({"encoding": "same-as-mask"}, (2, 3), reference_mask=mask)
    assert alias is mask
    with pytest.raises(ValueError):
        decode_mask({"encoding": "rle", "shape": [3, 2], "counts": [1, 2, 3]}, (2, 3))


@pytest.mark.parametrize(("encoding", "shape", "box", "expected"), [
    ("packbits-zlib-base64", [2, 3], None,
     [[False, True, True], [False, False, False]]),
    ("bbox-packbits-zlib-base64", [3, 5], [1, 1, 4, 3],
     [[False] * 5, [False, False, True, True, False], [False] * 5]),
])
def test_packed_masks_preserve_row_order_and_crop_origin(encoding, shape, box, expected):
    payload = {"encoding": encoding, "shape": shape,
               "data": base64.b64encode(zlib.compress(b"\x06")).decode("ascii")}
    if box is not None:
        payload["bbox_xyxy"] = box
    np.testing.assert_array_equal(decode_mask(payload, tuple(shape)), expected)


@pytest.mark.parametrize("changes", [
    {"data": "!bad!"},
    {"data": base64.b64encode(zlib.compress(b"\x06\x00")).decode("ascii")},
    {"encoding": "unknown"},
    {"encoding": "same-as-mask"},
    {"encoding": "rle", "counts": [1, True, 4]},
    {"encoding": "rle", "counts": [1, -1, 6]},
])
def test_corrupt_masks_are_rejected(changes):
    payload = {"encoding": "packbits-zlib-base64", "shape": [2, 3], "data": ""}
    payload.update(changes)
    with pytest.raises(ValueError):
        decode_mask(payload, (2, 3))
