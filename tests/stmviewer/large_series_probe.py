"""Opt-in measurement helpers using public widgets, X11 captures and process RSS."""

import hashlib
from pathlib import Path
from threading import Event, Thread
from time import perf_counter

import numpy as np
import psutil
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QTimer, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialogButtonBox, QFileDialog,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QWidget,
)


def source_identity(path):
    source = Path(path).resolve()
    with source.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(source=str(source), source_bytes=source.stat().st_size, source_sha256=checksum)


def distribution(values):
    return dict(zip(('min', 'median', 'p95', 'max'),
                    map(float, np.percentile(values, [0, 50, 95, 100]))))


class Resources:
    def __init__(self):
        self.samples = []
        self.stop = Event()
        self.process = psutil.Process()
        self.started = perf_counter()
        self.thread = Thread(target=self._sample, daemon=True)
        self.thread.start()

    def _sample(self):
        while not self.stop.is_set():
            self.samples.append((perf_counter() - self.started, self.snapshot()))
            self.stop.wait(.05)

    def snapshot(self):
        # Includes workers (currently QThreads in the same process).
        return sum(p.memory_info().rss for p in [self.process] + self.process.children(recursive=True)
                   if p.is_running())

    def close(self):
        self.stop.set()
        self.thread.join()


class GuiProbe:
    def __init__(self, window):
        self.window = window
        self.preview = self.widget(QWidget, 'imagePreview')
        self.preview.setFixedSize(640, 640)
        self.number = self.widget(QSpinBox, 'frameNumber')
        self.play = self.widget(QPushButton, 'playPause')
        self.view = self.widget(QComboBox, 'frameView')
        self.resources = Resources()
        self.heartbeats = []
        self.timer = QTimer(window)
        self.timer.setInterval(25)
        self.timer.timeout.connect(lambda: self.heartbeats.append(perf_counter()))
        self.timer.start()

    def widget(self, kind, name):
        found = self.window.findChild(kind, name)
        assert found is not None, name
        return found

    def capture(self, widget=None):
        widget = widget or self.preview
        point = widget.mapTo(self.window, QPoint())
        image = widget.screen().grabWindow(self.window.winId(), point.x(), point.y(),
                                          widget.width(), widget.height()).toImage()
        if image.isNull():
            raise RuntimeError('Screen capture unavailable; require Qt xcb/X11.')
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        return hashlib.sha256(image.constBits().asstring(image.sizeInBytes())).hexdigest()

    def errors(self):
        return [m.text() for m in self.window.findChildren(QMessageBox) if m.isVisible()]

    def wait(self, predicate, timeout=1800):
        deadline = perf_counter() + timeout
        while not predicate():
            if self.errors():
                raise RuntimeError(self.errors())
            if perf_counter() >= deadline:
                raise TimeoutError('GUI operation did not finish.')
            QTest.qWait(5)
        if self.errors():
            raise RuntimeError(self.errors())

    def select(self, index):
        editor = self.number.findChild(QLineEdit)
        editor.selectAll()
        QTest.keyClicks(editor, str(index))
        QTest.keyClick(editor, Qt.Key.Key_Return)

    def open(self, path):
        def choose():
            dialog = next(w for w in QApplication.topLevelWidgets() if isinstance(w, QFileDialog))
            dialog.setDirectory(str(path.resolve().parent))
            dialog.findChild(QLineEdit, 'fileNameEdit').setText(path.name)
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Open).click()
        QTimer.singleShot(50, choose)
        self.widget(QPushButton, 'openFrames').click()

    def operation(self, start, *, kind, cancel_fraction=None):
        button = self.widget(QPushButton, 'openFrames' if kind == 'import' else 'registerFrames')
        progress = self.widget(QProgressBar, 'importProgress' if kind == 'import' else 'registrationProgress')
        cancel = self.widget(QPushButton, 'cancelImport' if kind == 'import' else 'cancelRegistration')
        before_rss = self.resources.snapshot()
        first_sample = len(self.resources.samples)
        first_beat = len(self.heartbeats)
        began = perf_counter()
        start()
        self.wait(lambda: progress.isVisible() or button.isEnabled())
        progress_values = set()
        cancelled_at = None
        navigation_ms = None
        preserved = None
        while not button.isEnabled():
            if progress.maximum() > 0:
                value = progress.value() / progress.maximum()
                progress_values.add(progress.value())
                # Exercise actual old-series navigation while the worker runs.
                if value > .05 and self.number.maximum() > 1 and navigation_ms is None:
                    old = self.capture()
                    began_navigation = perf_counter()
                    self.select(self.number.maximum() if self.number.value() == 1 else 1)
                    self.wait(lambda: self.capture() != old, timeout=3)
                    navigation_ms = (perf_counter() - began_navigation) * 1000
                if cancel_fraction is not None and value >= cancel_fraction and cancelled_at is None:
                    preserved = (self.capture(), self.number.maximum(), self.number.value(), self.view.currentText())
                    cancelled_at = perf_counter()
                    cancel.click()
                    assert not cancel.isEnabled()
            if self.errors():
                raise RuntimeError(self.errors())
            if perf_counter() - began > 1800:
                raise TimeoutError('Operation exceeded measurement timeout (not an application limit).')
            QTest.qWait(5)
        duration = perf_counter() - began
        cancel_s = perf_counter() - cancelled_at if cancelled_at else None
        if cancel_fraction is not None:
            assert cancelled_at is not None, 'Operation ended before cancellation point.'
            assert (self.capture(), self.number.maximum(), self.number.value(), self.view.currentText()) == preserved
        self.wait(lambda: not progress.isVisible())
        QTest.qWait(250)  # Allow normal Qt deferred deletion; no forced GC/malloc trimming.
        # The synchronous driver stays inside one timer callback. Deliver the
        # DeferredDelete events that a normal return to the main loop would process.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        beats = self.heartbeats[first_beat:]
        return dict(kind=kind, seconds=duration, cancel_to_finish_s=cancel_s,
                    progress_values=len(progress_values), navigation_ms=navigation_ms,
                    heartbeat_intervals_ms=distribution(np.diff(beats) * 1000) if len(beats) > 1 else None,
                    rss_before=before_rss, rss_after=self.resources.snapshot(),
                    rss_peak=max([v for t, v in self.resources.samples[first_sample:]] or [before_rss]),
                    frames=self.number.maximum(), registration=self.widget(QLabel, 'registrationInfo').text())

    def references(self):
        result = []
        for index in range(1, self.number.maximum() + 1):
            self.number.setValue(index)
            QTest.qWait(5)
            result.append(self.capture())
        assert len(set(result)) == len(result), 'Use distinct visible frames for an unambiguous order measurement.'
        return result

    def playback(self, expected, *, fps=5, seconds=30):
        self.widget(QComboBox, 'playbackFps').setCurrentText(str(fps))
        self.widget(QCheckBox, 'playbackLoop').setChecked(True)
        self.number.setValue(1)
        QTest.qWait(30)
        previous = self.capture()
        assert previous == expected[0]
        current = 0
        observed = []
        began = perf_counter()
        QTest.mouseClick(self.play, Qt.MouseButton.LeftButton)
        while perf_counter() - began < seconds:
            QTest.qWait(2)
            captured = self.capture()
            if captured != previous:
                current = (current + 1) % len(expected)
                assert captured == expected[current], f'Unexpected image after frame {current}; skipping/occlusion.'
                observed.append(perf_counter())
                previous = captured
        QTest.mouseClick(self.play, Qt.MouseButton.LeftButton)
        assert len(observed) > 1
        intervals = np.diff(observed)
        return dict(seconds=seconds, requested_fps=fps, changes=len(observed), skipped=0,
                    mean_fps=float(1 / np.mean(intervals)), intervals_ms=distribution(intervals * 1000))

    def latency(self, expected, trials=50):
        self.widget(QComboBox, 'playbackFps').setCurrentText('5')
        QTest.qWait(100)
        paused = self.capture(self.play)
        pause, selection = [], []
        for i in range(trials):
            QTest.mouseClick(self.play, Qt.MouseButton.LeftButton)
            QTest.qWait(30)
            before = self.capture()
            began = perf_counter()
            QTest.mouseClick(self.play, Qt.MouseButton.LeftButton)
            self.wait(lambda: self.capture(self.play) == paused, timeout=3)
            pause.append((perf_counter() - began) * 1000)
            QTest.qWait(210)
            assert self.capture() == before
            QTest.mouseClick(self.play, Qt.MouseButton.LeftButton)
            QTest.qWait(30)
            target = (self.number.value() + 97) % len(expected) + 1
            began = perf_counter()
            self.select(target)
            self.wait(lambda: self.capture() == expected[target - 1], timeout=3)
            selection.append((perf_counter() - began) * 1000)
            assert self.play.text() == 'Play'
        return dict(trials_per_action=trials, pause_ms=distribution(pause), selection_ms=distribution(selection),
                    pause_within_250ms=float(np.mean(np.asarray(pause) <= 250)),
                    selection_within_250ms=float(np.mean(np.asarray(selection) <= 250)))
