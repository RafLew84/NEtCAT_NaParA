"""Compare a manually exported MPP with its source series (indices start at 1)."""
from argparse import ArgumentParser

import numpy as np

from stmviewer.frame import FrameProvenance
from stmviewer.series import open_frame_series


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--source', nargs='+', required=True)
    parser.add_argument('--saved', required=True)
    parser.add_argument('--keep', nargs='+', type=int, help='Remaining source indices, starting at 1')
    args = parser.parse_args()
    source = open_frame_series(args.source)
    if args.keep:
        if any(index < 1 or index > len(source) for index in args.keep):
            parser.error('--keep: indeks poza serią źródłową')
        source = tuple(source[index - 1] for index in args.keep)
    saved = open_frame_series([args.saved])
    assert len(saved) == len(source), 'Inna liczba klatek'
    for index, (expected, actual) in enumerate(zip(source, saved, strict=True), 1):
        np.testing.assert_array_equal(actual.data, expected.data, err_msg=f'Klatka {index}')
        assert actual.provenance == (expected.provenance or
                                    FrameProvenance(str(expected.source), expected.source_frame_index))
        for field in ('channel', 'signal_unit', 'size_x_nm', 'size_y_nm', 'offset_x_nm', 'offset_y_nm',
                      'bias_v', 'setpoint_a', 'scan_angle_deg', 'measurement_time_s',
                      'measurement_time_raw', 'raw_header', 'calibration_note'):
            assert getattr(actual, field) == getattr(expected, field), f'Klatka {index}: {field}'
    print(f'OK: {len(saved)} klatek; dokładne wartości/NaN, parametry, czasy i pochodzenie.')


if __name__ == '__main__':
    main()
