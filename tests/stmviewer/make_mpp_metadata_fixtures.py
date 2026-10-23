"""Independent small metadata pairs; no production metadata serializer is used."""

import copy
import hashlib
import json
import struct
from pathlib import Path

from make_mpp_fixtures import FIRST, SECOND, THIRD, movie_bytes


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    movie = movie_bytes([FIRST, SECOND, THIRD], times={0: '1500 ms', 2: '4.25 s'})
    frames = []
    for source, index, time, raw_time, channel, unit, sx, sy, bias, header in [
        ('/pomiary/first.stp', None, 10, '10000 ms', 'Topo', 'nm', 8, 9, 0,
         {'General Info': {'Operator': 'Żaneta', 'Z Amplitude': '2 nm'}}),
        (r'C:\pomiary\movie.MPP', 7, None, None, 'Current', 'nA', 16, 6, -0.2,
         {'Control': {'Set Point': '0 pA'}, 'Comment': 'frame eight'}),
        ('archive/third.s94', None, 35, '35 s', None, None, None, 12, None,
         {'z_gain': '99', 'Swapped': '0'}),
    ]:
        frames.append(dict(
            provenance=dict(source=source, source_frame_index=index),
            measurement_time_s=time, measurement_time_raw=raw_time,
            channel=channel, signal_unit=unit, size_x_nm=sx, size_y_nm=sy,
            offset_x_nm=0, offset_y_nm=-1, bias_v=bias, setpoint_a=0,
            scan_angle_deg=37, calibration_note='Nieznana kalibracja' if unit is None else None,
            raw_header=header,
        ))
    metadata = dict(format='stmviewer-mpp', version=1, image_kind='original',
                    movie=dict(sha256=hashlib.sha256(movie).hexdigest(),
                               frame_count=3, shape_yx=[3, 4]), frames=frames)
    (destination / 'mixed.MPP').write_bytes(movie)
    (destination / 'mixed.MPP.stmviewer.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (destination / 'without-addon.MPP').write_bytes(movie)
    for name in ('wrong-content', 'wrong-shape', 'wrong-count', 'unsupported', 'broken'):
        changed = copy.deepcopy(metadata)
        payload = movie
        if name == 'wrong-content':
            payload = movie[:-8] + struct.pack('<d', 999)
        elif name == 'wrong-shape':
            changed['movie']['shape_yx'] = [4, 3]
        elif name == 'wrong-count':
            changed['movie']['frame_count'] = 2
        elif name == 'unsupported':
            changed['version'] = 999
        (destination / f'{name}.MPP').write_bytes(payload)
        content = '{broken' if name == 'broken' else json.dumps(changed, ensure_ascii=False, indent=2)
        (destination / f'{name}.MPP.stmviewer.json').write_text(content + '\n', encoding='utf-8')



if __name__ == '__main__':
    generate(Path(__file__).parent / 'fixtures' / 'mpp-metadata')
