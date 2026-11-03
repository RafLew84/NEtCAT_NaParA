"""Exercise real MPP/JSON import through the application's public UI."""

from pathlib import Path
from threading import Event

import numpy as np
from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtWidgets import QStyle, QStyleOptionSlider

from stmdomains.tools.demo_inputs import create_demo_inputs, write_mpp, write_session
from stmdomains.ui.main_window import STMDomainsMainWindow


class Prompts:
    """Script only operating-system file choices and user confirmations."""

    def __init__(self, session: Path):
        self.session = session
        self.source: Path | None = None
        self.accept = False
        self.errors: list[str] = []
        self.source_requests: list[str] = []
        self.confirmations: list[Path] = []

    def choose_session(self) -> Path | None:
        return self.session

    def choose_source(self, message: str, suggested: Path | None) -> Path | None:
        self.source_requests.append(message)
        result, self.source = self.source, None
        return result

    def confirm_source(self, path: Path, reasons: tuple[str, ...]) -> bool:
        self.confirmations.append(path)
        return self.accept

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def pixel(view, x, y):
    point = view.mapFromScene(QPointF(x + .5, y + .5))
    return view.viewport().grab().toImage().pixelColor(point).red()


def test_open_and_navigate_real_mpp_in_saved_order(qtbot, tmp_path):
    frames = np.zeros((3, 2, 3))
    frames[0, 0, 0] = 100
    frames[2, 1, 2] = 100
    mpp = write_mpp(tmp_path / "images.mpp", frames)
    session = write_session(tmp_path / "session.json", mpp, [2, 0], reverse=True)
    prompts = Prompts(session)
    window = STMDomainsMainWindow(prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    assert not window.frame_slider.isEnabled()
    qtbot.mouseClick(window.open_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.frame_label.text().startswith("Klatka 1 / 2"))
    assert "źródłowa 3" in window.frame_label.text()
    assert pixel(window.image_view, 0, 0) == 255
    assert pixel(window.image_view, 2, 1) == 0
    assert not window.previous_button.isEnabled()
    qtbot.mouseClick(window.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.frame_label.text().startswith("Klatka 2 / 2"))
    assert "źródłowa 1" in window.frame_label.text()
    assert pixel(window.image_view, 0, 0) == 0
    assert pixel(window.image_view, 2, 1) == 255
    assert not window.next_button.isEnabled()
    slider = window.frame_slider
    assert slider.value() == 2
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(
        QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, slider,
    )
    qtbot.mousePress(slider, Qt.MouseButton.LeftButton, pos=handle.center())
    try:
        qtbot.mouseMove(slider, QPoint(2, slider.height() // 2))
        qtbot.waitUntil(lambda: "Klatka 1 / 2" in window.frame_label.text())
        assert slider.isSliderDown()  # Preview changes before releasing the handle.
        assert window.frame_number.value() == slider.value() == 1
        assert pixel(window.image_view, 0, 0) == 255
        for x in (slider.width() - 2, 2, slider.width() - 2):
            qtbot.mouseMove(slider, QPoint(x, slider.height() // 2))
        qtbot.waitUntil(lambda: "Klatka 2 / 2" in window.frame_label.text())
        assert window.frame_number.value() == slider.value() == 2
        assert pixel(window.image_view, 2, 1) == 255
        assert not window.next_button.isEnabled()
    finally:
        qtbot.mouseRelease(slider, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.previous_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Klatka 1 / 2" in window.frame_label.text())
    assert slider.value() == 1
    assert prompts.errors == []


def open_and_wait(qtbot, window, path):
    window.controller.open_session(path)
    qtbot.waitUntil(lambda: not window.controller.is_busy)


def test_number_selection_and_single_frame_controls(qtbot, tmp_path):
    paths = create_demo_inputs(tmp_path)
    window = STMDomainsMainWindow(prompts=Prompts(paths["reordered"]))
    qtbot.addWidget(window)
    window.show()
    open_and_wait(qtbot, window, paths["reordered"])
    window.frame_number.setFocus()
    window.frame_number.selectAll()
    qtbot.keyClicks(window.frame_number, "2")
    qtbot.keyClick(window.frame_number, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: "Klatka 2 / 2" in window.frame_label.text())
    assert "źródłowa 2" in window.frame_label.text()
    assert "czas 20 s" in window.frame_label.text()
    assert window.frame_slider.value() == 2
    open_and_wait(qtbot, window, paths["single"])
    assert "Klatka 1 / 1" in window.frame_label.text()
    assert "czas nieznany" in window.frame_label.text()
    assert not window.frame_number.isEnabled()
    assert not window.previous_button.isEnabled()
    assert not window.next_button.isEnabled()
    assert not window.frame_slider.isEnabled()
    assert window.frame_slider.minimum() == window.frame_slider.maximum() == 1
    fitted = window.image_view.transform().m11()
    qtbot.mouseClick(window.zoom_in_button, Qt.MouseButton.LeftButton)
    assert window.image_view.transform().m11() > fitted
    qtbot.mouseClick(window.fit_button, Qt.MouseButton.LeftButton)
    assert abs(window.image_view.transform().m11() - fitted) < 1e-8


def test_relocation_cancel_and_invalid_session_preserve_old_series(qtbot, tmp_path):
    paths = create_demo_inputs(tmp_path)
    prompts = Prompts(paths["single"])
    window = STMDomainsMainWindow(prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    open_and_wait(qtbot, window, paths["single"])
    old_title = window.windowTitle()
    open_and_wait(qtbot, window, paths["bad_source"])
    assert len(prompts.source_requests) == 1
    assert window.windowTitle() == old_title
    open_and_wait(qtbot, window, paths["unknown_version"])
    assert "wersja" in prompts.errors[-1]
    assert window.windowTitle() == old_title
    prompts.source = paths["source"]
    open_and_wait(qtbot, window, paths["bad_source"])
    assert "bad-source" in window.windowTitle()
    assert "Klatka 1 / 4" in window.frame_label.text()


def test_changed_mtime_requires_confirmation_before_replacing_series(qtbot, tmp_path):
    paths = create_demo_inputs(tmp_path)
    prompts = Prompts(paths["single"])
    window = STMDomainsMainWindow(prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    open_and_wait(qtbot, window, paths["single"])
    before = paths["source"].stat()
    open_and_wait(qtbot, window, paths["changed_mtime"])
    assert prompts.confirmations == [paths["source"]]
    assert "single.moltrack.json" in window.windowTitle()
    prompts.accept = True
    open_and_wait(qtbot, window, paths["changed_mtime"])
    assert "changed-mtime.moltrack.json" in window.windowTitle()
    assert paths["source"].stat().st_mtime_ns == before.st_mtime_ns


def test_cancelled_slow_file_read_cannot_replace_a_newer_series(qtbot, tmp_path, monkeypatch):
    paths = create_demo_inputs(tmp_path)
    prompts = Prompts(paths["single"])
    window = STMDomainsMainWindow(prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    open_and_wait(qtbot, window, paths["single"])
    entered, release = Event(), Event()
    original_read = Path.read_bytes

    def delayed_read(path, *args, **kwargs):
        if path == paths["changed_mtime"]:
            entered.set()
            if not release.wait(5):
                raise TimeoutError("The UI did not release the delayed filesystem read")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", delayed_read)
    try:
        window.controller.open_session(paths["changed_mtime"])
        qtbot.waitUntil(entered.is_set)
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        qtbot.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
        assert not window.controller.is_busy
        assert "single.moltrack.json" in window.windowTitle()
        open_and_wait(qtbot, window, paths["reordered"])
        release.set()
        qtbot.waitUntil(lambda: window.controller.pending_task_count == 0)
        assert "reordered.moltrack.json" in window.windowTitle()
        assert "źródłowa 4" in window.frame_label.text()
        assert prompts.confirmations == []
        assert prompts.errors == []
    finally:
        release.set()
        qtbot.waitUntil(lambda: window.controller.pending_task_count == 0)
