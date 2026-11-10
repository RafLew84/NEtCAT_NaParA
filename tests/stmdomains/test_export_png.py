"""PNG is a standalone, labelled rendering with the same coordinates and colours."""

import json
import numpy as np
from PyQt6.QtGui import QImage

from stmdomains.core.export import ExportOptions
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.analysis_demo import create_analysis_demo


def test_png_keeps_gamma_crop_and_image_samples_with_readable_caption(qtbot, tmp_path):
    from stmdomains.ui.export_png import render_export_png
    series = prepare_import(create_analysis_demo(tmp_path)['single']).series
    presenter = FramePresenter(series)
    frame = presenter.present(0, 'raw', 1.6)
    view = {'assignment_mode': 'domains', 'layers': {'centers': False, 'boxes': False, 'masks': False,
            'fill': False, 'outlines': False, 'numbers': False}}
    options = ExportOptions(crop=(20, 20, 80, 60), image_width=320)
    encoded = render_export_png(frame, view, options)
    image = QImage.fromData(encoded, 'PNG')
    assert not image.isNull()
    meta = json.loads(image.text('STM Domains'))
    assert meta['gamma'] == 1.6 and meta['crop_view_px'] == [20, 20, 80, 60]
    x, y, width, height = meta['image_rect_px']
    assert width == 320 and height == 240 and image.height() > height
    for source_x, source_y in ((30, 30), (50, 50), (90, 70)):
        pixel = image.pixelColor(int(x) + (source_x-20)*4+2, int(y) + (source_y-20)*4+2)
        assert pixel.getRgb() == tuple(int(n) for n in frame.rendered.rgba[source_y, source_x])
    assert meta['analysis_status'] == 'unanalysed'
    assert 'Brak analizy' in meta['caption'] and 'wycinek' in meta['caption']


def test_png_domains_and_classes_use_saved_palette_and_full_legend(qtbot, tmp_path):
    from PyQt6.QtGui import QColor
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.ui.export_png import render_export_png
    from stmdomains.ui.result_style import domain_color
    series = prepare_import(create_analysis_demo(tmp_path)['single']).series
    presenter = FramePresenter(series)
    events = analyze_series(presenter.analysis_input, frame_count=1, series_id=series.identity,
                            plan=SeriesAnalysisPlan(k=4), run_id='colors')
    _, outcome = next(events), next(events)
    result = outcome.result
    frame = presenter.present(0, result=result)
    before = result.domain_labels.copy()
    layers = {'fill': True, 'domain_opacity': 100, 'centers': False, 'boxes': False, 'masks': False,
              'outlines': False, 'numbers': False}
    for mode in ('domains', 'classes'):
        encoded = render_export_png(frame, {'assignment_mode': mode, 'layers': layers}, ExportOptions(image_width=1200))
        image = QImage.fromData(encoded)
        meta = json.loads(image.text('STM Domains'))
        assert meta['assignment_mode'] == mode and meta['analysis_id'] == 'colors'
        assert meta['catalogue_id'] == result.catalogue.identifier and len(meta['legend']) > 1
        left, top, width, _ = meta['image_rect_px']
        scale = width / series.frame_shape[1]
        for domain_id in set(np.unique(result.domain_labels)) - {0}:
            ys, xs = np.where(result.domain_labels == domain_id)
            y, x = int(ys[len(ys)//2]), int(xs[len(xs)//2])
            member = next(a for a in result.assignments.values() if a.domain_local_id == domain_id)
            color = domain_color(int(domain_id)) if mode == 'domains' else next(c.color for c in result.classes if c.class_id == member.class_id)
            assert image.pixelColor(int(left + (x+.5)*scale), int(top + (y+.5)*scale)) == QColor(color)
    np.testing.assert_array_equal(before, result.domain_labels)


def test_cropped_overlays_never_paint_over_caption_or_legend(qtbot, tmp_path):
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.ui.export_png import render_export_png
    series = prepare_import(create_analysis_demo(tmp_path)['single']).series
    presenter = FramePresenter(series)
    events = analyze_series(presenter.analysis_input, frame_count=1, series_id=series.identity,
                            plan=SeriesAnalysisPlan(k=4), run_id='crop')
    _, outcome = next(events), next(events)
    frame = presenter.present(0, result=outcome.result)
    options = ExportOptions(crop=(50, 50, 40, 40), image_width=320)
    images = []
    for enabled in (False, True):
        layers = {key: enabled for key in ('centers', 'boxes', 'fill', 'outlines', 'numbers')}
        images.append(QImage.fromData(render_export_png(frame, {'layers': layers}, options)))
    meta = json.loads(images[0].text('STM Domains'))
    x, y, width, height = (int(value) for value in meta['image_rect_px'])
    assert images[0].copy(0, 0, images[0].width(), y) == images[1].copy(0, 0, images[1].width(), y)
    bottom = y + height
    assert images[0].copy(0, bottom, images[0].width(), images[0].height()-bottom) == images[1].copy(0, bottom, images[1].width(), images[1].height()-bottom)
