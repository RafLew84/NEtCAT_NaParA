"""Visible pixels and zoom, without involving molecule overlays."""

import numpy as np
import pytest
from PyQt6.QtCore import QPointF

from stmdomains.core.display import render_image
from stmdomains.ui.image_view import ImageView


def test_asymmetric_image_keeps_rows_columns_and_pixel_positions(qtbot):
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    view.set_image(render_image(np.array([[0., 50., 100.], [100., 50., 0.]])))
    qtbot.waitUntil(lambda: view.viewport().width() > 0)
    screenshot = view.viewport().grab().toImage()
    upper_left = view.mapFromScene(QPointF(0.5, 0.5))
    upper_right = view.mapFromScene(QPointF(2.5, 0.5))
    lower_right = view.mapFromScene(QPointF(2.5, 1.5))
    assert screenshot.pixelColor(upper_left).red() == 0
    assert screenshot.pixelColor(upper_right).red() == 255
    assert screenshot.pixelColor(lower_right).red() == 0


@pytest.mark.parametrize("samples, expected", [
    ([[4., 4.], [4., 4.]], [128, 128, 128, 255]),
    ([[float('nan'), float('inf')]], [0, 0, 0, 0]),
])
def test_constant_or_missing_signal_is_explicit_without_changing_data(samples, expected):
    image = np.array(samples)
    original = image.copy()
    with np.errstate(all="raise"):
        rendered = render_image(image)
    assert rendered.rgba[0, 0].tolist() == expected
    assert rendered.has_data == bool(np.isfinite(image).any())
    np.testing.assert_array_equal(image, original)


def test_zoom_survives_same_size_frame_change_and_fit_can_be_restored(qtbot):
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    view.set_image(render_image(np.arange(100.).reshape(10, 10)))
    fitted = view.transform().m11()
    view.zoom_by(1.5)
    assert view.transform().m11() == pytest.approx(fitted * 1.5)
    view.set_image(render_image(np.arange(100., 200.).reshape(10, 10)))
    assert view.transform().m11() == pytest.approx(fitted * 1.5)
    view.fit_to_window()
    assert view.transform().m11() == pytest.approx(fitted)
