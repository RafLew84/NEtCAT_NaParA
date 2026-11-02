"""Frame preparation must not move the browser's image or navigation."""

from threading import Event

import pytest
from PyQt6.QtCore import QRunnable, QThreadPool, Qt

from stmdomains.tools.browsing_demo import create_browsing_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


def layout_geometry(window):
    positions = {
        name: getattr(window, name).geometry().getRect()
        for name in ("image_view", "frame_slider", "filmstrip", "playback_controls")
    }
    positions["window"] = window.geometry().getRect()
    return positions


@pytest.mark.parametrize("size", [(1100, 760), (900, 650)])
@pytest.mark.parametrize("cancel", [False, True])
def test_loading_frame_keeps_window_layout(qtbot, qapp, tmp_path, size, cancel):
    window = STMDomainsMainWindow()
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    controller = window.controller
    controller.open_session(create_browsing_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    qtbot.waitUntil(lambda: controller.pending_task_count == 0)
    qtbot.wait(30)
    before = layout_geometry(window)
    release = Event()

    class WorkerGate(QRunnable):
        def __init__(self):
            super().__init__()
            self.entered = Event()

        def run(self):
            self.entered.set()
            release.wait(5)

    gates = []
    for pool in qapp.findChildren(QThreadPool):
        for _ in range(pool.maxThreadCount()):
            gate = WorkerGate()
            gates.append(gate)
            pool.start(gate)
    try:
        qtbot.waitUntil(lambda: all(gate.entered.is_set() for gate in gates))
        window.frame_number.setValue(2)
        qtbot.waitUntil(lambda: controller.is_busy)
        qtbot.wait(30)
        assert window.progress_bar.isVisible()
        assert window.cancel_button.isVisible()
        assert layout_geometry(window) == before
        if cancel:
            qtbot.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
            qtbot.wait(30)
            assert not controller.is_busy
            assert layout_geometry(window) == before
    finally:
        release.set()
        qtbot.waitUntil(lambda: controller.pending_task_count == 0)
    assert controller.current_index == (0 if cancel else 1)
    qtbot.wait(30)
    assert not window.progress_bar.isVisible()
    assert not window.cancel_button.isVisible()
    assert layout_geometry(window) == before
