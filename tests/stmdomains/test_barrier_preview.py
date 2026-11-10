"""Diagnostic barriers use the exact stored raw mask in every image coordinate system."""

import json
import numpy as np
from PyQt6.QtGui import QImage

from stmdomains.analysis import analyze_frame
from stmdomains.core.export import ExportOptions
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.export_png import render_export_png


def test_barrier_layer_and_png_follow_raw_mask_in_raw_aligned_and_crop(qtbot, tmp_path):
    series = prepare_import(create_analysis_demo(tmp_path)['series']).series
    presenter = FramePresenter(series)
    result = analyze_frame(presenter.analysis_input(1), k=4)
    assert result.barrier_mask.any()
    layers = {key: False for key in ('centers', 'boxes', 'masks', 'fill', 'outlines', 'numbers')}
    for mode in ('raw', 'expanded_aligned'):
        frame = presenter.present(1, mode, result=result)
        offset_x, offset_y, _, _ = frame.field_rect
        for crop in (None, (offset_x + 30, offset_y + 30, 400, 400)):
            options = ExportOptions(image_width=1200, crop=crop)
            images = [QImage.fromData(render_export_png(frame, {'layers': {**layers, 'barriers': enabled}}, options))
                      for enabled in (False, True)]
            meta = json.loads(images[1].text('STM Domains'))
            assert any(entry['label'] == 'Bariery [px]' for entry in meta['legend'])
            left, top, width, _ = meta['image_rect_px']
            x0, y0, source_width, _ = meta['crop_view_px']
            scale = width / source_width
            # Use interior mask pixels, away from rounded resampling boundaries.
            yy, xx = np.where(result.barrier_mask)
            inside = (xx > 35) & (xx < 420) & (yy > 35) & (yy < 420)
            candidates = np.flatnonzero(inside)[::max(1, int(inside.sum()) // 20)]
            assert len(candidates) > 0
            for i in candidates:
                x = int(left + (xx[i] + .5 + offset_x - x0) * scale)
                y = int(top + (yy[i] + .5 + offset_y - y0) * scale)
                assert images[0].pixelColor(x, y) != images[1].pixelColor(x, y)
    assert result.barrier_mask.flags.writeable is False
