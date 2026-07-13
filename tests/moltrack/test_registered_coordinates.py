import unittest

import numpy as np

from moltrack.core import RegisteredFrameTransform


class RegisteredFrameTransformTests(unittest.TestCase):
    def test_transforms_raw_bbox_polygon_and_mask_to_expanded_coordinates(self) -> None:
        transform = RegisteredFrameTransform(
            raw_shape=(4, 5),
            expanded_shape=(8, 10),
            frame_origin_xy=(2.5, 1.5),
        )

        self.assertEqual(
            transform.raw_bbox_to_expanded((1.0, 1.0, 4.0, 3.0)),
            (3.5, 2.5, 6.5, 4.5),
        )
        self.assertEqual(
            transform.expanded_bbox_to_raw((3.5, 2.5, 6.5, 4.5)),
            (1.0, 1.0, 4.0, 3.0),
        )
        self.assertEqual(
            transform.raw_polygon_to_expanded(((1.0, 1.0), (4.0, 1.0), (2.0, 3.0))),
            ((3.5, 2.5), (6.5, 2.5), (4.5, 4.5)),
        )

        integer_transform = RegisteredFrameTransform(
            raw_shape=(4, 5),
            expanded_shape=(8, 10),
            frame_origin_xy=(2.0, 1.0),
        )
        raw_mask = np.zeros((4, 5), dtype=bool)
        raw_mask[1:3, 1:4] = True

        expanded_mask = integer_transform.raw_mask_to_expanded(raw_mask)

        expected = np.zeros((8, 10), dtype=bool)
        expected[2:4, 3:6] = True
        np.testing.assert_array_equal(expanded_mask, expected)
        self.assertEqual(np.count_nonzero(expanded_mask), np.count_nonzero(raw_mask))

    def test_maps_and_clips_expanded_prompt_bbox_to_observed_raw_footprint(self) -> None:
        transform = RegisteredFrameTransform(
            raw_shape=(10, 12),
            expanded_shape=(20, 24),
            frame_origin_xy=(4.5, 3.5),
        )

        self.assertEqual(
            transform.expanded_prompt_bbox_to_raw((2.0, 2.0, 10.5, 9.5)),
            (0.0, 0.0, 6.0, 6.0),
        )
        with self.assertRaisesRegex(ValueError, "does not overlap"):
            transform.expanded_prompt_bbox_to_raw((0.0, 0.0, 4.0, 3.0))

if __name__ == "__main__":
    unittest.main()
