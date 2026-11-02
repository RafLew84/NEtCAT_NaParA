"""Small real image series exercise the filmstrip through its widget API."""

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.demo_inputs import write_mpp, write_session
from stmdomains.ui.filmstrip import Filmstrip


def load_series(tmp_path, frames, indices=None, name="images"):
    source = write_mpp(tmp_path / f"{name}.mpp", frames)
    indices = range(len(frames)) if indices is None else indices
    session = write_session(tmp_path / f"{name}.json", source, indices, reverse=True)
    return prepare_import(session).series


def test_thumbnails_follow_source_map_and_selection_waits_for_display(qtbot, tmp_path):
    frames = np.array([[[0., 50., 100.], [100., 50., 0.]],
                       [[100., 50., 0.], [0., 50., 100.]]])
    series = load_series(tmp_path, frames, [1, 0])
    strip = Filmstrip()
    qtbot.addWidget(strip)
    strip.resize(400, 110)
    strip.show()
    strip.set_series(series)
    strip.set_current_index(0)
    qtbot.waitUntil(lambda: strip.is_ready(0) and strip.is_ready(1))
    model = strip.model()
    assert model.rowCount() == 2
    icon = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert isinstance(icon, QIcon)
    image = icon.pixmap(96, 64).toImage()
    assert image.pixelColor(0, 0).red() == 255
    assert image.pixelColor(image.width() - 1, 0).red() == 0
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "1"
    requests = []
    strip.frame_selected.connect(requests.append)
    qtbot.mouseClick(strip.viewport(), Qt.MouseButton.LeftButton,
                     pos=strip.visualRect(model.index(1, 0)).center())
    assert requests == [1]
    assert strip.current_index == strip.currentIndex().row() == 0
    strip.set_current_index(1)
    assert strip.current_index == strip.currentIndex().row() == 1
    strip.setFocus()
    qtbot.keyClick(strip, Qt.Key.Key_Left)
    assert requests == [1, 0]
    assert strip.current_index == 1
    strip.shutdown()


def test_replacing_series_discards_old_thumbnail_and_shutdown_stops_publication(qtbot, tmp_path):
    old = load_series(tmp_path, np.ones((1, 1024, 1536)), name="large")
    new = load_series(tmp_path, np.array([[[0., 0., 100.], [0., 0., 100.]]]), name="new")
    strip = Filmstrip()
    qtbot.addWidget(strip)
    strip.resize(400, 110)
    strip.show()
    strip.set_series(old)
    strip.set_current_index(0)
    qtbot.waitUntil(lambda: strip.pending_task_count == 1)
    strip.set_series(new)
    strip.set_current_index(0)
    qtbot.waitUntil(lambda: strip.is_ready(0) and strip.pending_task_count == 0)
    model = strip.model()
    image = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole).pixmap(96, 64).toImage()
    assert image.pixelColor(0, 0).red() == 255
    assert image.pixelColor(image.width() - 1, 0).red() == 0
    strip.set_series(old)
    strip.set_current_index(0)
    qtbot.waitUntil(lambda: strip.pending_task_count == 1)
    strip.shutdown()
    qtbot.waitUntil(lambda: strip.pending_task_count == 0)
    assert strip.cache_info == (0, 0)


def test_nonfinite_image_is_explicit_and_long_series_keeps_small_cache(qtbot, tmp_path):
    frames = np.tile(np.arange(6.).reshape(1, 2, 3), (160, 1, 1))
    frames[0] = np.nan
    series = load_series(tmp_path, frames)
    strip = Filmstrip()
    qtbot.addWidget(strip)
    strip.resize(400, 110)
    strip.show()
    strip.set_series(series)
    strip.set_current_index(0)
    qtbot.waitUntil(lambda: strip.is_ready(0))
    model = strip.model()
    assert "brak próbek" in model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
    icon = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert icon.pixmap(96, 64).toImage().pixelColor(0, 0).alpha() == 0
    for index in range(10, 160, 10):
        strip.set_current_index(index)
        qtbot.waitUntil(lambda: strip.is_ready(index) and strip.pending_task_count == 0)
    assert model.rowCount() == 160
    assert strip.cache_info[0] <= 64
    assert strip.cache_info[1] <= 1572864
    assert not strip.is_ready(0)
    assert strip.visualRect(model.index(150, 0)).intersects(strip.viewport().rect())
    strip.shutdown()
