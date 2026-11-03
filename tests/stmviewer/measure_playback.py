"""Opt-in GUI measurement: screen pixels, 30 s Play and selection/Pause latency.

Run with PYTHONPATH=. and Qt xcb (unobscured desktop) or offscreen (painted buffer).
This script is not part of pytest and never accesses the window's private state.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np
from PyQt6.QtCore import QPoint, QTimer, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialogButtonBox, QFileDialog, QLineEdit,
    QPushButton, QSpinBox, QWidget,
)

from stmviewer.ui.main_window import STMViewerMainWindow


def distribution(values):
    return dict(zip(('min', 'median', 'p95', 'max'),
                    (float(x) for x in np.percentile(values, [0, 50, 95, 100]))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--trials', type=int, default=50, help='Trials per action')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.seconds < 30 or args.trials < 50:
        parser.error('Use at least 30 s and 50 trials per action.')
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication([])
    if app.platformName() not in ('xcb', 'offscreen'):
        raise RuntimeError('Use Qt xcb or offscreen for this capture measurement.')
    window = STMViewerMainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    preview = window.findChild(QWidget, 'imagePreview')
    play = window.findChild(QPushButton, 'playPause')
    number = window.findChild(QSpinBox, 'frameNumber')
    failures = []

    def screen_hash(widget):
        point = widget.mapTo(window, QPoint())
        image = widget.screen().grabWindow(window.winId(), point.x(), point.y(), widget.width(), widget.height()).toImage()
        if image.isNull():
            raise RuntimeError('Screen capture is unavailable.')
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        return hashlib.sha256(image.constBits().asstring(image.sizeInBytes())).hexdigest()

    def wait_for(predicate, timeout=3):
        until = perf_counter() + timeout
        while not predicate():
            if perf_counter() >= until:
                raise TimeoutError('Visible GUI result did not arrive.')
            QTest.qWait(5)

    def choose():
        dialog = next(w for w in app.topLevelWidgets() if isinstance(w, QFileDialog))
        source = args.source.resolve()
        dialog.setDirectory(str(source.parent))
        dialog.findChild(QLineEdit, 'fileNameEdit').setText(source.name)
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Open).click()

    def run():
        try:
            QTimer.singleShot(100, choose)
            started = perf_counter()
            window.findChild(QPushButton, 'openFrames').click()
            wait_for(window.findChild(QPushButton, 'openFrames').isEnabled, timeout=120)
            cold_open_s = perf_counter() - started
            QTest.qWait(300)  # Let dialog/window focus animations finish before references.
            count = number.maximum()
            assert count > 1, 'Need a movie with distinct frames.'
            expected = []
            # Build independent references via manual navigation, capturing the actual screen.
            for index in range(1, count + 1):
                number.setValue(index)
                QTest.qWait(60)  # Allow the compositor to present the manual reference.
                expected.append(screen_hash(preview))
            assert len(set(expected)) == count, 'Use a movie with visually distinct frames.'
            number.setValue(1)
            window.findChild(QCheckBox, 'playbackLoop').setChecked(True)
            QTest.qWait(30)
            previous = screen_hash(preview)
            assert previous == expected[0]
            observed = []
            current = 0
            began = perf_counter()
            QTest.mouseClick(play, Qt.MouseButton.LeftButton)
            while perf_counter() - began < args.seconds:
                QTest.qWait(5)
                captured = screen_hash(preview)
                if captured != previous:
                    current = (current + 1) % count
                    assert captured == expected[current], f'Unexpected capture after frame {current}; check order and window occlusion'
                    observed.append(perf_counter())
                    previous = captured
            QTest.mouseClick(play, Qt.MouseButton.LeftButton)
            QTest.qWait(30)
            QTest.qWait(300)
            paused_button = screen_hash(play)
            assert len(observed) > 1
            intervals = np.diff(observed)
            pause_ms, select_ms = [], []
            for _ in range(args.trials):
                QTest.mouseClick(play, Qt.MouseButton.LeftButton)
                QTest.qWait(30)
                before = screen_hash(preview)
                began_pause = perf_counter()
                QTest.mouseClick(play, Qt.MouseButton.LeftButton)
                wait_for(lambda: screen_hash(play) == paused_button)
                pause_ms.append((perf_counter() - began_pause) * 1000)
                assert screen_hash(preview) == before
                QTest.mouseClick(play, Qt.MouseButton.LeftButton)
                QTest.qWait(30)
                target = (number.value() + 7) % count + 1
                editor = number.findChild(QLineEdit)
                began_select = perf_counter()
                editor.selectAll()
                QTest.keyClicks(editor, str(target))
                QTest.keyClick(editor, Qt.Key.Key_Return)
                wait_for(lambda: screen_hash(preview) == expected[target - 1])
                select_ms.append((perf_counter() - began_select) * 1000)
                assert play.text() == 'Play'
            result = {
                'source': str(args.source.resolve()), 'frames': count,
                'platform': platform.platform(), 'qt_platform': app.platformName(),
                'capture': 'screen' if app.platformName() == 'xcb' else 'Qt painted backing store',
                'cold_open_s_including_dialog': cold_open_s,
                'measurement_s': args.seconds, 'requested_fps': 5,
                'observed_changes': len(observed),
                'mean_fps': float(1 / np.mean(intervals)),
                'frame_intervals_ms': distribution(intervals * 1000),
                'skipped_frames': 0, 'trials_per_action': args.trials,
                'pause_ms': distribution(pause_ms), 'selection_ms': distribution(select_ms),
                'pause_within_250ms_fraction': float(np.mean(np.array(pause_ms) <= 250)),
                'selection_within_250ms_fraction': float(np.mean(np.array(select_ms) <= 250)),
            }
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            window.grab().save(str(args.output.with_suffix('.png')))
            print(json.dumps(result, indent=2), flush=True)
        except Exception as error:
            failures.append(error)
        finally:
            window.close()
            app.quit()

    QTimer.singleShot(100, run)
    app.exec()
    if failures:
        raise failures[0]


if __name__ == '__main__':
    main()
