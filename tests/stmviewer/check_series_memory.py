"""Opt-in live-allocation check, separate from timing (tracemalloc adds overhead)."""

import argparse
import json
from pathlib import Path
import tracemalloc

import numpy as np
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from large_series_probe import GuiProbe
from stmviewer.ui.main_window import STMViewerMainWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication([])
    if app.platformName() != 'xcb':
        raise RuntimeError('Require Qt xcb/X11, as in the timing probe.')
    window = STMViewerMainWindow()
    probe = GuiProbe(window)
    window.show()
    rows, errors = [], []
    tracemalloc.start()

    def sample(name):
        snapshot = tracemalloc.take_snapshot().filter_traces([
            tracemalloc.DomainFilter(True, np.lib.tracemalloc_domain)])
        rows.append(dict(stage=name, numpy_live_bytes=sum(t.size for t in snapshot.traces),
                         rss=probe.resources.snapshot()))
        print(rows[-1], flush=True)

    def run():
        try:
            sample('start')
            probe.operation(lambda: probe.open(args.source), kind='import')
            sample('original')
            for index in range(2):
                probe.operation(lambda: probe.widget(QPushButton, 'registerFrames').click(), kind='registration')
                sample(f'aligned-{index + 1}')
            small = Path(__file__).parent / 'fixtures/mpp/known-times.mpp'
            probe.operation(lambda: probe.open(small), kind='import')
            sample('small-replacement')
            assert rows[-1]['numpy_live_bytes'] < rows[1]['numpy_live_bytes'] / 10
        except Exception as error:
            errors.append(repr(error))
        finally:
            probe.resources.close()
            tracemalloc.stop()
            args.output.write_text(json.dumps(dict(stages=rows, errors=errors), indent=2) + '\n')
            window.close()
            while window.isVisible():
                QTest.qWait(10)
            app.quit()
    QTimer.singleShot(100, run)
    app.exec()
    if errors:
        raise RuntimeError(errors)


if __name__ == '__main__':
    main()
