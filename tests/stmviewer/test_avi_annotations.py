"""Movie annotations checked through the public rendering plan."""
from dataclasses import replace

import cv2
import numpy as np

from stmviewer.avi_export import prepare_avi
from stmviewer.avi_annotations import AnnotationOptions
from test_avi_raster import frame


def has_text(raster, text, tolerance=1e-5):
    # Independent glyph oracle: the expected words/numbers are literal test data.
    (width, height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, .5, 1)
    template = np.zeros((height + baseline + 8, width + 8, 3), np.uint8)
    mask = np.zeros_like(template)
    origin = (4, height + 4)
    cv2.putText(template, text, origin, cv2.FONT_HERSHEY_SIMPLEX, .5,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(mask, text, origin, cv2.FONT_HERSHEY_SIMPLEX, .5,
                (255, 255, 255), 3, cv2.LINE_AA)
    # Compare only opaque glyph/contour pixels; no assumption about the image behind them.
    mask = (mask == 255).astype(np.uint8)
    match = cv2.matchTemplate(raster, template, cv2.TM_SQDIFF_NORMED, mask=mask)
    return float(np.nanmin(match)) < tolerance



def test_movie_uses_series_numbers_and_measurement_times_for_range_after_deletion():
    source = frame(np.ones((256, 256)))
    frames = tuple(replace(source, measurement_time_s=float(i * 15), source_frame_index=100 + i)
                   for i in range(21))
    frames = frames[:2] + frames[3:]
    frames = frames[:5] + (replace(frames[5], measurement_time_s=None),) + frames[6:]
    plan = prepare_avi(frames, start=5, end=10, fps=30,
                       annotations=AnnotationOptions(frame_number=True, measurement_time=True))
    first = plan.render_frame(0)
    assert has_text(first, 'Klatka 5/20') and has_text(first, 'Czas: 75 s')
    missing = plan.render_frame(1)
    assert has_text(missing, 'Klatka 6/20') and has_text(missing, 'Czas: brak')
    last = plan.render_frame(5)
    assert has_text(last, 'Klatka 10/20') and has_text(last, 'Czas: 150 s')
    assert first.shape == (256, 256, 3)
    assert np.all(first[-1] == 127)


def test_scale_bar_uses_physical_geometry_before_padding_and_pixel_override():
    from stmviewer.avi_raster import MoviePresentation
    source = frame(np.ones((129, 129)), size_x_nm=258, size_y_nm=129)
    options = AnnotationOptions(scale_bar=True)
    physical = prepare_avi((source,), annotations=options).render_frame(0)
    assert physical.shape == (130, 258, 3)
    assert has_text(physical, '50 nm')
    assert np.count_nonzero(physical[110, :, 0] == 255) == 50
    pixel = prepare_avi((source,), annotations=options,
                        presentation=MoviePresentation(pixel_proportions=True)).render_frame(0)
    assert pixel.shape == (130, 130, 3)
    assert has_text(pixel, '20 px')
    assert np.count_nonzero(pixel[110, :, 0] == 255) == 20
    assert np.all(physical[-1] == 0) and np.all(pixel[-1] == 0)


def test_annotations_reject_small_images_before_writing_but_clean_export_still_works():
    import pytest
    for shape in ((256, 80), (80, 256), (129, 129)):
        source = frame(np.ones(shape))
        with pytest.raises(ValueError, match='za mały'):
            prepare_avi((source,), annotations=AnnotationOptions(
                scale_bar=True, frame_number=True, measurement_time=True))
        clean = prepare_avi((source,)).render_frame(0)
        assert clean.shape == (shape[0] + shape[0] % 2, shape[1] + shape[1] % 2, 3)


def test_unknown_or_mixed_scale_uses_pixels_but_homogeneous_range_uses_nm():
    source = frame(np.ones((256, 256)), size_x_nm=512, size_y_nm=256)
    other = replace(source, size_x_nm=256)
    options = AnnotationOptions(scale_bar=True)
    mixed = prepare_avi((source, other), annotations=options).render_frame(0)
    assert has_text(mixed, '50 px')
    known_range = prepare_avi((source, other), end=1, annotations=options).render_frame(0)
    assert has_text(known_range, '100 nm')
    for size in (None, -1, float('nan'), float('inf')):
        unknown = replace(source, size_x_nm=size)
        assert has_text(prepare_avi((unknown,), annotations=options).render_frame(0), '50 px')


def test_annotations_are_independent_of_gamma_and_background_without_changing_samples():
    from stmviewer.avi_raster import MoviePresentation
    data = np.full((256, 256), np.nan)
    data[100:180, 120:220] = np.arange(100)[None, :]
    source = replace(frame(data, size_x_nm=256, size_y_nm=256), measurement_time_s=12.5)
    before = source.data.tobytes()
    options = AnnotationOptions(scale_bar=True, frame_number=True, measurement_time=True)
    for background in (0, 128, 255):
        first = prepare_avi((source,), annotations=options,
                            presentation=MoviePresentation(gamma=1, background=background)).render_frame(0)
        second = prepare_avi((source,), annotations=options,
                             presentation=MoviePresentation(gamma=2, background=background)).render_frame(0)
        assert has_text(first, 'Klatka 1/1') and has_text(first, 'Czas: 12.5 s') and has_text(first, '50 nm')
        np.testing.assert_array_equal(first[:90], second[:90])
        np.testing.assert_array_equal(first[200:], second[200:])
        assert not np.array_equal(first[100:180], second[100:180])
        assert np.all(first[:, -1] == background)
    assert source.data.tobytes() == before


def test_independent_options_and_clean_default():
    source = replace(frame(np.ones((256, 256))), measurement_time_s=15)
    clean = prepare_avi((source,)).render_frame(0)
    assert np.all(clean == 127)
    for chosen, text in (('scale_bar', '50 px'), ('frame_number', 'Klatka 1/1'), ('measurement_time', 'Czas: 15 s')):
        raster = prepare_avi((source,), annotations=AnnotationOptions(**{chosen: True})).render_frame(0)
        assert has_text(raster, text)
        for name, unwanted in (('scale_bar', '50 px'), ('frame_number', 'Klatka 1/1'), ('measurement_time', 'Czas: 15 s')):
            if name != chosen:
                assert not has_text(raster, unwanted)


def test_finite_zero_and_invalid_times_are_distinguished():
    source = frame(np.ones((256, 256)))
    for value, label in ((0, 'Czas: 0 s'), (None, 'Czas: brak'), (float('nan'), 'Czas: brak'), (float('inf'), 'Czas: brak')):
        plan = prepare_avi((replace(source, measurement_time_s=value),),
                           annotations=AnnotationOptions(measurement_time=True))
        assert has_text(plan.render_frame(0), label)


def test_unavailable_annotation_dependency_is_a_user_facing_validation_error(monkeypatch):
    import sys
    import pytest
    monkeypatch.setitem(sys.modules, 'cv2', None)
    source = frame(np.ones((256, 256)))
    with pytest.raises(ValueError, match='OpenCV'):
        prepare_avi((source,), annotations=AnnotationOptions(frame_number=True))
    assert prepare_avi((source,)).annotations is None


def test_aligned_scale_uses_complete_canvas_and_original_pixel_size_after_deletion():
    from stmviewer.registration import register_series
    from stmviewer.avi_sources import aligned_movie_frames
    from make_avi_annotation_fixtures import annotation_frames
    originals = annotation_frames()[:3]
    originals = (originals[0], replace(originals[1], data=np.roll(originals[1].data, (4, -7), (0, 1))),
                 replace(originals[2], data=np.roll(originals[2].data, (-3, 5), (0, 1))))
    result = register_series(originals).without_frame(0)
    frames = aligned_movie_frames(originals[1:], result)
    before = tuple(f.data.tobytes() for f in frames)
    plan = prepare_avi(frames, start=2, end=2, annotations=AnnotationOptions(scale_bar=True))
    raster = plan.render_frame(0)
    assert raster.shape == (264, 536, 3)
    # Canvas width 268 source pixels × 2 nm; physical movie width 536 px.
    assert plan.annotations.scale_label == '100 nm'
    assert np.count_nonzero(raster[244, 16:116, 0] == 255) == 100
    assert np.all(raster[-1] == 0)
    assert tuple(f.data.tobytes() for f in frames) == before


def test_labels_and_scale_leave_surrounding_image_visible_without_black_panels():
    source = replace(frame(np.ones((256, 256))), measurement_time_s=15)
    plan = prepare_avi((source,), annotations=AnnotationOptions(
        scale_bar=True, frame_number=True, measurement_time=True))
    raster = plan.render_frame(0)
    assert np.all(raster[8:12, 8:12] == 127)
    assert np.all(raster[208:212, 8:12] == 127)
    assert np.any(raster == 0)  # narrow dark contours keep white marks readable
    assert np.any(raster == 255)
