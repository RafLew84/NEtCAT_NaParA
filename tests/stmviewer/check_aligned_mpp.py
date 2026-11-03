"""Check a GUI export against a freshly computed CPU result, before frame deletion."""
from argparse import ArgumentParser

import numpy as np

from stmviewer.frame import FrameProvenance
from stmviewer.registration import CPU_METHODS, register_series
from stmviewer.series import open_frame_series


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--source', nargs='+', required=True)
    parser.add_argument('--saved', required=True)
    parser.add_argument('--keep', nargs='+', type=int, help='Source indices remaining after registration, from 1')
    parser.add_argument('--method', choices=CPU_METHODS, default='phase_correlation')
    args = parser.parse_args()
    source = open_frame_series(args.source)
    result = register_series(source, method=args.method)
    indices = args.keep if args.keep is not None else list(range(1, len(source) + 1))
    if not indices or indices != sorted(set(indices)) or any(i < 1 or i > len(source) for i in indices):
        parser.error('--keep: wymagane rosnące, niepowtarzające się indeksy klatek od 1')
    expected = tuple(result.frames[i - 1] for i in indices)
    loaded = open_frame_series([args.saved])
    assert len(loaded) == len(expected), 'Niezgodna liczba klatek'
    for index, (saved, aligned) in enumerate(zip(loaded, expected, strict=True), 1):
        assert saved.data.tobytes() == aligned.image.data.tobytes(), f'Klatka {index}: inne próbki'
        np.testing.assert_array_equal(np.isfinite(saved.data), aligned.valid_mask)
        original = aligned.original
        assert saved.provenance == (original.provenance or
                                    FrameProvenance(str(original.source), original.source_frame_index))
        for field in ('size_x_nm', 'size_y_nm', 'offset_x_nm', 'offset_y_nm', 'channel', 'signal_unit',
                      'measurement_time_s', 'measurement_time_raw', 'raw_header', 'bias_v', 'setpoint_a',
                      'scan_angle_deg', 'calibration_note'):
            assert getattr(saved, field) == getattr(aligned.image, field), f'Klatka {index}: {field}'
        history = saved.alignment
        assert history is not None, f'Klatka {index}: brak historii'
        assert history.canvas_shape == result.canvas_shape
        assert history.padding_ltrb == result.padding_ltrb
        assert history.pixel_size_nm == result.pixel_size_nm
        assert history.reference == FrameProvenance(str(result.reference.source), result.reference.source_frame_index)
        assert history.original_shape == original.data.shape
        assert history.original_rect == aligned.original_rect
        assert history.origin_xy == aligned.origin_xy and history.shift_xy == aligned.shift_xy
        assert history.original_size_nm == (original.size_x_nm, original.size_y_nm)
        assert history.original_offset_nm == (original.offset_x_nm, original.offset_y_nm)
        assert history.previous == original.alignment
        assert (history.method, history.device) == (result.method, result.device)
        assert (history.status, history.quality_score, history.inherited_uncertainty) == (
            aligned.status, aligned.quality_score, aligned.inherited_uncertainty)
        print(f'Klatka {index}: obszar {saved.data.shape[::-1]}, źródło {history.original_rect}, '
              f'{np.count_nonzero(aligned.valid_mask)} ważnych próbek; dokładna zgodność.')
    print(f'OK: {len(loaded)} klatek; próbki, NaN, geometria, odniesienie i metadane zachowane.')


if __name__ == '__main__':
    main()
