"""Opt-in full-series export through public GUI controls, with resource samples."""

from time import perf_counter

import numpy as np
from PyQt6.QtCore import QCoreApplication, QEvent, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
)

from large_series_probe import GuiProbe, distribution, source_identity


class ExportProbe(GuiProbe):
    def choose_save(self, path, version=None):
        dialog = next(
            w for w in QApplication.topLevelWidgets() if isinstance(w, QFileDialog)
        )
        dialog.setDirectory(str(path.resolve().parent))
        if version is not None:
            dialog.selectNameFilter(f"MPP {version} (*.mpp *.MPP)")
        dialog.findChild(QLineEdit, "fileNameEdit").setText(path.name)
        if path.exists():
            QTimer.singleShot(20, self.confirm_replace)
        dialog.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Save
        ).click()

    def confirm_replace(self):
        message = next(
            w
            for w in QApplication.topLevelWidgets()
            if isinstance(w, QMessageBox) and w.isVisible()
        )
        message.button(QMessageBox.StandardButton.Yes).click()

    def begin(self, path, options):
        version = options["version"]
        self.view.setCurrentText(version)
        self.widget(QDoubleSpinBox, "previewGamma").setValue(options.get("gamma", 1))
        if options["kind"] == "mpp":
            QTimer.singleShot(20, lambda: self.choose_save(path, version))
            self.widget(QPushButton, "saveOriginalMpp").click()
        else:

            def configure():
                dialog = self.window.findChild(QDialog, "aviOptions")
                assert dialog is not None and dialog.isVisible()
                dialog.findChild(QComboBox, "aviVersion").setCurrentText(version)
                dialog.findChild(QComboBox, "aviCodec").setCurrentText(options["codec"])
                from PyQt6.QtWidgets import QSpinBox

                dialog.findChild(QSpinBox, "aviFps").setValue(options["fps"])
                dialog.findChild(QComboBox, "aviContrast").setCurrentIndex(
                    options["contrast"] == "movie"
                )
                dialog.findChild(QComboBox, "aviBackground").setCurrentIndex(
                    {0: 0, 128: 1, 255: 2}[options["background"]]
                )
                for name in ("aviScaleBar", "aviFrameNumber", "aviMeasurementTime"):
                    dialog.findChild(QCheckBox, name).setChecked(options["annotations"])
                QTimer.singleShot(20, lambda: self.choose_save(path))
                dialog.findChild(QDialogButtonBox).button(
                    QDialogButtonBox.StandardButton.Save
                ).click()

            QTimer.singleShot(20, configure)
            self.widget(QPushButton, "saveAvi").click()

    def export(self, path, options, *, cancel_fraction=None, expected_error=None):
        kind = options["kind"]
        prefix = "mpp" if kind == "mpp" else "avi"
        button = self.widget(
            QPushButton, "saveOriginalMpp" if kind == "mpp" else "saveAvi"
        )
        progress = self.widget(QProgressBar, prefix + "ExportProgress")
        info = self.widget(QLabel, prefix + "ExportInfo")
        cancel = self.widget(
            QPushButton, "cancelMppExport" if kind == "mpp" else "cancelAviExport"
        )
        first_sample, first_beat = len(self.resources.samples), len(self.heartbeats)
        before = self.resources.snapshot()
        started = perf_counter()
        self.begin(path, options)
        self.wait(lambda: progress.isVisible() or button.isEnabled())
        changed, stopped = False, None
        values = set()
        while not button.isEnabled():
            if perf_counter() - started > 1800:
                raise TimeoutError("Export measurement timed out.")
            total = progress.maximum()
            if total:
                fraction = progress.value() / total
                values.add(progress.value())
                if 0.05 < fraction < 0.9 and not changed and self.number.maximum() > 1:
                    previous = self.capture()
                    target = self.number.maximum() if self.number.value() == 1 else 1
                    self.select(target)
                    assert self.number.value() == target
                    self.widget(QDoubleSpinBox, "previewGamma").setValue(1.3)
                    self.widget(QPushButton, "zoomIn").click()
                    self.view.setCurrentText(
                        "original" if options["version"] == "aligned" else "aligned"
                    )
                    self.wait(lambda: self.capture() != previous, timeout=3)
                    changed = True
                if (
                    cancel_fraction is not None
                    and fraction >= cancel_fraction
                    and stopped is None
                ):
                    stopped = perf_counter()
                    cancel.click()
                    assert not cancel.isEnabled()
            QTest.qWait(5)
        seconds = perf_counter() - started
        cancel_seconds = perf_counter() - stopped if stopped else None
        text = info.text()
        if cancel_fraction is not None:
            assert stopped is not None and "Anulowano" in text, text
            status = "cancelled"
        elif expected_error is not None:
            assert expected_error in text and "Nie udało się" in text, text
            status = "expected-error"
        else:
            assert "Zapisano:" in text, text
            status = "saved"
        QTest.qWait(100)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        beats = self.heartbeats[first_beat:]
        result = dict(
            options,
            file=str(path.resolve()),
            status=status,
            seconds=seconds,
            cancel_to_finish_s=cancel_seconds,
            preview_changed_while_busy=changed,
            frames=self.number.maximum(),
            progress_values=len(values),
            heartbeat_ms=distribution(np.diff(beats) * 1000)
            if len(beats) > 1
            else None,
            rss_before=before,
            rss_after=self.resources.snapshot(),
            rss_peak=max(
                [v for t, v in self.resources.samples[first_sample:]] or [before]
            ),
        )
        if status == "saved":
            result.update(source_identity(path))
            if kind == "mpp":
                result["sidecar"] = source_identity(
                    path.with_name(path.name + ".stmviewer.json")
                )
        self.widget(QPushButton, "fitImage").click()
        return result
