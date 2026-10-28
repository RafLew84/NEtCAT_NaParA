"""Opt-in ticket 18 GUI benchmark; run on X11, separately from fast pytest tests."""

import argparse
import json
from importlib.metadata import version
import platform
import subprocess
from pathlib import Path

import numpy as np
import psutil
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from large_series_probe import GuiProbe
from stmviewer.ui.main_window import STMViewerMainWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true', help='Short harness check, NOT acceptance evidence')
    parser.add_argument('--typical', action='store_true', help='Typical film: import, Phase and both views only')
    args = parser.parse_args()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication([])
    if app.platformName() != 'xcb':
        raise RuntimeError('Use QT_QPA_PLATFORM=xcb and an unobscured X11 display.')
    window = STMViewerMainWindow()
    probe = GuiProbe(window)
    window.show()
    window.raise_()
    window.activateWindow()
    cpu_info = Path('/proc/cpuinfo')
    cpu_model = next((line.split(':', 1)[1].strip() for line in cpu_info.read_text().splitlines()
                      if line.startswith('model name')), platform.processor()) if cpu_info.exists() else platform.processor()
    report = dict(source=str(args.source.resolve()), smoke=args.smoke,
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  platform=platform.platform(), python=platform.python_version(), numpy=np.__version__,
                  cpu=cpu_model, logical_cpus=psutil.cpu_count(),
                  dependencies={name: version(name) for name in ('numpy', 'scipy', 'scikit-image', 'PyQt6', 'psutil')},
                  ram_total=psutil.virtual_memory().total, ram_available_start=psutil.virtual_memory().available,
                  capture='X11 screen pixels, Qt xcb; not physical monitor/scanout',
                  stages=[], views={})
    failures = []

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report['rss_peak'] = max(v for t, v in probe.resources.samples)
        report['rss_within_16GB'] = report['rss_peak'] <= 16_000_000_000
        args.output.write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, start, kind, cancel=None):
        result = probe.operation(start, kind=kind, cancel_fraction=cancel)
        result['name'] = name
        report['stages'].append(result)
        print(name, json.dumps(result), flush=True)
        save()
        return result

    def register():
        probe.widget(QPushButton, 'registerFrames').click()

    def run():
        try:
            stage('open', lambda: probe.open(args.source), 'import')
            report['source_frames'] = probe.number.maximum()
            for view in ('original', 'aligned'):
                if view == 'aligned':
                    stage('phase', register, 'registration')
                    assert probe.view.currentText() == 'aligned'
                references = probe.references()
                print('references', view, len(references), flush=True)
                result = dict(play=probe.playback(references, seconds=1 if args.smoke else 30),
                              latency=probe.latency(references, trials=1 if args.smoke else 50),
                              fast_play=probe.playback(references, fps=30, seconds=1 if args.smoke else 3))
                report['views'][view] = result
                window.grab().save(str(args.output.with_name(args.output.stem + '-' + view + '.png')))
                print(view, json.dumps(result), flush=True)
                save()
            if not args.typical:
                # Delete middle, last and the historical reference; compare surviving screen images.
                remaining = list(references)
                for index in (len(remaining) // 2, len(remaining) - 1, 1):
                    index = min(index, probe.number.maximum())
                    probe.number.setValue(index)
                    remaining.pop(index - 1)
                    probe.widget(QPushButton, 'deleteFrame').click()
                    QTest.qWait(20)
                    assert probe.capture() == remaining[probe.number.value() - 1]
                report['after_deletion_frames'] = probe.number.maximum()
                report['after_deletion_registration'] = probe.widget(QLabel, 'registrationInfo').text()
                stage('phase-after-delete', register, 'registration')
                for fraction in (.1, .65):
                    stage(f'cancel-phase-{fraction}', register, 'registration', fraction)
                for fraction in (.15, .65):
                    stage(f'cancel-import-{fraction}', lambda: probe.open(args.source), 'import', fraction)
                # Replacing and re-registering cannot retain previous completed series/results.
                stage('reopen', lambda: probe.open(args.source), 'import')
                stage('phase-after-reopen', register, 'registration')
                stage('reopen-again', lambda: probe.open(args.source), 'import')
                stage('phase-after-reopen-again', register, 'registration')
                small = Path(__file__).parent / 'fixtures/mpp/known-times.mpp'
                stage('release-large-by-opening-small', lambda: probe.open(small), 'import')
            report['status'] = 'completed'
        except Exception as error:
            report['status'] = 'failed'
            report['error'] = repr(error)
            failures.append(error)
        finally:
            probe.resources.close()
            report['rss_samples_50ms'] = probe.resources.samples
            save()
            window.close()
            # closeEvent waits for workers to stop; never destroy a running QThread.
            while window.isVisible():
                QTest.qWait(10)
            app.quit()
    QTimer.singleShot(100, run)
    app.exec()
    if failures:
        raise failures[0]


if __name__ == '__main__':
    main()
