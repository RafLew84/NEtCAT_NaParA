"""Compose the raw series browser; input parsing lives outside Qt."""

import json
from collections.abc import Mapping

from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QSignalBlocker, Qt
from PyQt6.QtGui import QCloseEvent, QKeySequence
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit,
    QProgressBar, QPushButton, QSizePolicy, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from stmdomains.core.series import Series
from stmdomains.core.annotations import Detection, Segmentation
from stmdomains.core.domain_results import DomainResult
from stmdomains.ui.annotation_controls import AnnotationControls
from stmdomains.ui.image_view import ImageView
from stmdomains.ui.filmstrip import Filmstrip
from stmdomains.ui.import_prompts import ImportPrompts, QtImportPrompts
from stmdomains.ui.playback_controls import PlaybackControls
from stmdomains.ui.result_controls import ResultControls
from stmdomains.ui.result_style import assignment_description
from stmdomains.ui.session_controller import PresentedFrame, SessionController


class STMDomainsMainWindow(QMainWindow):
    def __init__(
        self, parent: QWidget | None = None, *, prompts: ImportPrompts | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("STM Domains")
        self.resize(1100, 760)
        self.controller = SessionController(prompts or QtImportPrompts(self), self)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        files = QHBoxLayout()
        self.open_button = QPushButton("Otwórz zapis MolTrack…")
        self.open_button.setObjectName("openButton")
        self.open_button.clicked.connect(lambda: self.controller.open_session())
        files.addWidget(self.open_button)
        self.result_open_button = QPushButton("Otwórz wynik v0.4…")
        self.result_open_button.setEnabled(False)
        self.result_open_button.setToolTip("Najpierw otwórz zapis MolTrack, potem wskaż paczkę wyniku.")
        self.result_open_button.clicked.connect(lambda: self.controller.open_result())
        files.addWidget(self.result_open_button)
        self.source_label = QLabel("Brak otwartej serii")
        files.addWidget(self.source_label, 1)
        layout.addLayout(files)

        navigation = QHBoxLayout()
        self.previous_button = QPushButton("← Poprzednia")
        self.next_button = QPushButton("Następna →")
        self.frame_number = QSpinBox()
        self.frame_number.setPrefix("Klatka ")
        self.frame_number.setKeyboardTracking(False)
        self.previous_button.clicked.connect(lambda: self.controller.step_frame(-1))
        self.next_button.clicked.connect(lambda: self.controller.step_frame(1))
        self.frame_number.valueChanged.connect(self._select_frame)
        for control in (self.previous_button, self.frame_number, self.next_button):
            control.setEnabled(False)
            navigation.addWidget(control)
        navigation.addStretch()
        self.fit_button = QPushButton("Dopasuj")
        self.zoom_in_button = QPushButton("Powiększ +")
        self.zoom_out_button = QPushButton("Pomniejsz −")
        for button in (self.zoom_out_button, self.zoom_in_button, self.fit_button):
            button.setEnabled(False)
            navigation.addWidget(button)
        layout.addLayout(navigation)

        self.annotation_controls = AnnotationControls()
        self.annotation_controls.view_mode.currentIndexChanged.connect(self._select_view)
        self.annotation_controls.layers_changed.connect(self._set_layers)
        layout.addWidget(self.annotation_controls)
        self.registration_label = QLabel()
        self.registration_label.setWordWrap(True)
        layout.addWidget(self.registration_label)

        self.frame_label = QLabel("Wybierz zapis .moltrack.json; obrazy zostaną odczytane z MPP.")
        layout.addWidget(self.frame_label)
        self.image_view = ImageView(self)
        self.image_view.annotation_selected.connect(self._select_annotation)
        layout.addWidget(self.image_view, 1)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setObjectName("frameSlider")
        self.frame_slider.setAccessibleName("Klatka serii")
        self.frame_slider.setToolTip("Przeciągnij, aby przeglądać klatki")
        self.frame_slider.setRange(1, 1)
        self.frame_slider.setEnabled(False)
        self.frame_slider.setTracking(True)
        self.frame_slider.sliderPressed.connect(self.controller.pause)
        self.frame_slider.valueChanged.connect(
            lambda number: self.controller.show_frame(number - 1)
        )
        layout.addWidget(self.frame_slider)
        self.filmstrip = Filmstrip()
        self.filmstrip.frame_selected.connect(self.controller.show_frame)
        layout.addWidget(self.filmstrip)
        self.playback_controls = PlaybackControls()
        self.playback_controls.play.clicked.connect(self._toggle_playback)
        self.playback_controls.restart.clicked.connect(self.controller.restart)
        self.playback_controls.rate.currentIndexChanged.connect(
            lambda: self.controller.set_playback_rate(self.playback_controls.rate.currentData())
        )
        self.playback_controls.gamma.valueChanged.connect(self.controller.set_gamma)
        layout.addWidget(self.playback_controls)
        self.result_controls = ResultControls()
        self.result_controls.mode_changed.connect(self._select_result_mode)
        self.result_controls.details_button.clicked.connect(self._show_result_metadata)
        layout.addWidget(self.result_controls)
        for spin_control in (self.frame_number, self.playback_controls.gamma):
            spin_control.installEventFilter(self)
            editor = spin_control.lineEdit()
            if editor is not None:
                editor.installEventFilter(self)
        self.annotation_status = QLabel()
        self.annotation_status.setWordWrap(True)
        layout.addWidget(self.annotation_status)
        selection = QHBoxLayout()
        self.selection_label = QLabel("Kliknij oznaczenie, aby zobaczyć jego dane.")
        self.selection_label.setTextFormat(Qt.TextFormat.PlainText)
        self.selection_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        selection.addWidget(self.selection_label, 1)
        self.metadata_button = QPushButton("Dane oznaczenia…")
        self.metadata_button.setEnabled(False)
        self.metadata_button.clicked.connect(self._show_metadata)
        selection.addWidget(self.metadata_button)
        self.frame_info_button = QPushButton("Informacje o klatce…")
        self.frame_info_button.setEnabled(False)
        self.frame_info_button.clicked.connect(self._show_frame_info)
        selection.addWidget(self.frame_info_button)
        layout.addLayout(selection)
        self._selected: Detection | Segmentation | None = None
        self._presented: PresentedFrame | None = None
        self.fit_button.clicked.connect(self.image_view.fit_to_window)
        self.zoom_in_button.clicked.connect(lambda: self.image_view.zoom_by(1.25))
        self.zoom_out_button.clicked.connect(lambda: self.image_view.zoom_by(0.8))

        progress = QHBoxLayout()
        self.progress_label = QLabel("Gotowe")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.cancel_button = QPushButton("Anuluj")
        self.cancel_button.hide()
        for indicator in (self.progress_bar, self.cancel_button):
            policy = indicator.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            indicator.setSizePolicy(policy)
        self.cancel_button.clicked.connect(self.controller.cancel)
        progress.addWidget(self.progress_label, 1)
        progress.addWidget(self.progress_bar)
        progress.addWidget(self.cancel_button)
        layout.addLayout(progress)
        self.details_label = QLabel("Oryginał · auto kontrast osobno dla każdej klatki")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        menu_bar = self.menuBar()
        menu = menu_bar.addMenu("&Plik") if menu_bar is not None else None
        if menu is not None:
            open_action = menu.addAction("&Otwórz zapis MolTrack…")
            if open_action is not None:
                open_action.setShortcut(QKeySequence.StandardKey.Open)
                open_action.triggered.connect(lambda: self.controller.open_session())
            close_action = menu.addAction("&Zakończ")
            if close_action is not None:
                close_action.setShortcut(QKeySequence.StandardKey.Quit)
                close_action.triggered.connect(self.close)
        self.controller.series_changed.connect(self._show_series)
        self.controller.frame_changed.connect(self._show_frame)
        self.controller.busy_changed.connect(self._show_progress)
        self.controller.playback_changed.connect(self._show_playback)
        self.controller.result_changed.connect(self._result_loaded)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._finish_background_work)

    def _select_frame(self, number: int) -> None:
        # The displayed number changes together with the prepared image.
        with QSignalBlocker(self.frame_number):
            self.frame_number.setValue(self.controller.current_index + 1)
        self.controller.show_frame(number - 1)

    def _show_series(self, series: Series) -> None:
        self.filmstrip.set_series(series)
        self.setWindowTitle(f"STM Domains — {series.session_path.name}")
        self.source_label.setText(series.session_path.name)
        self.source_label.setToolTip(f"{series.session_path}\nMPP: {series.source_path}")
        with QSignalBlocker(self.frame_number):
            self.frame_number.setRange(1, series.frame_count)
        self.frame_number.setEnabled(series.frame_count > 1)
        with QSignalBlocker(self.frame_slider):
            self.frame_slider.setRange(1, series.frame_count)
        self.frame_slider.setEnabled(series.frame_count > 1)
        self.details_label.setText("Auto kontrast oryginału · jednostki obrazu: px")
        self.playback_controls.gamma.setEnabled(True)
        self.playback_controls.reset_gamma.setEnabled(True)
        for button in (self.fit_button, self.zoom_in_button, self.zoom_out_button):
            button.setEnabled(True)

    def _show_frame(self, view: PresentedFrame) -> None:
        series = self.controller.series
        if series is None:
            return
        frame = view.frame
        self.filmstrip.set_current_index(frame.working_index)
        with QSignalBlocker(self.playback_controls.gamma):
            self.playback_controls.gamma.setValue(view.gamma)
        height, width = view.rendered.rgba.shape[:2]
        self._presented = view
        self.image_view.set_frame(view)
        self.result_controls.set_frame(view)
        self._select_annotation(None)
        self.frame_info_button.setEnabled(True)
        presenter = self.controller.presenter
        controls = self.annotation_controls
        with QSignalBlocker(controls.view_mode):
            controls.view_mode.setCurrentIndex(0 if view.mode == "raw" else 1)
        controls.set_availability(
            aligned=presenter is not None and presenter.registration.available,
            detections=bool(view.annotations.detections),
            boxes=bool(view.annotations.detections) or any(
                s.bbox_xyxy is not None for s in view.annotations.segmentations
            ),
            segmentations=any(s.mask is not None or s.polygon_xy for s in view.annotations.segmentations),
        )
        self.registration_label.setText(view.registration_text)
        self.annotation_status.setText(
            f"{view.annotations.detection_message} · {view.annotations.segmentation_message}"
            + (" · Uwagi w informacjach o klatce." if view.annotations.diagnostics else "")
        )
        self._set_layers()
        self.frame_label.setText(
            f"Klatka {frame.working_index + 1} / {series.frame_count} · "
            f"źródłowa {frame.source_index + 1} · {width} × {height} px"
            + (f" · czas {frame.time_s:g} s" if frame.time_s is not None else " · czas nieznany")
        )
        with QSignalBlocker(self.frame_number):
            self.frame_number.setValue(frame.working_index + 1)
        self._sync_frame_slider()
        self.previous_button.setEnabled(frame.working_index > 0)
        self.next_button.setEnabled(frame.working_index < series.frame_count - 1)
        self._show_playback()

    def _show_progress(self, busy: bool, text: str) -> None:
        self.progress_label.setText(text)
        self.progress_bar.setVisible(busy)
        self.cancel_button.setVisible(busy)
        self.result_open_button.setEnabled(self.controller.can_open_result)
        self._show_playback()
        if not busy:
            self._sync_frame_slider()
            with QSignalBlocker(self.playback_controls.gamma):
                self.playback_controls.gamma.setValue(self.controller.gamma)
            with QSignalBlocker(self.annotation_controls.view_mode):
                self.annotation_controls.view_mode.setCurrentIndex(
                    0 if self.controller.view_mode == "raw" else 1
                )

    def _toggle_playback(self) -> None:
        if self.controller.is_playing:
            self.controller.pause()
        else:
            self.controller.play()

    def _show_playback(self, playing: bool | None = None) -> None:
        controls, controller = self.playback_controls, self.controller
        at_end = controller.series is not None and controller.current_index == controller.series.frame_count - 1
        controls.play.setText("⏸ Pauza" if controller.is_playing else (
            "▶ Od początku" if at_end else "▶ Odtwórz"
        ))
        controls.play.setEnabled(controller.can_play)
        controls.restart.setEnabled(controller.can_play)
        controls.rate.setEnabled(controller.can_play)

    def _select_view(self, index: int) -> None:
        self.controller.set_view_mode("raw" if index == 0 else "expanded_aligned")

    def _result_loaded(self, result: DomainResult | None) -> None:
        with QSignalBlocker(self.result_controls.mode):
            self.result_controls.mode.setCurrentIndex(0)
        self.image_view.set_assignment_mode("domains")
        self.details_label.setText(
            f"Wynik eksperymentalny v0.4 · analizowane klatki: {result.frame_count} · "
            "auto kontrast oryginału · px" if result is not None else
            "Auto kontrast oryginału · jednostki obrazu: px"
        )

    def _select_result_mode(self, mode: str) -> None:
        self.image_view.set_assignment_mode(mode)

    def _show_result_metadata(self) -> None:
        result = self.controller.result
        if result is not None:
            self._show_text("Dane wyniku v0.4 — wynik eksperymentalny", json.dumps(
                {"paczka": str(result.package_path), "klatki_analizowane": result.frame_count,
                 "dane_zapisanego_wyniku": dict(result.metadata)},
                ensure_ascii=False, indent=2,
                default=lambda value: dict(value) if isinstance(value, Mapping) else str(value),
            ))

    def _set_layers(self) -> None:
        controls = self.annotation_controls
        self.image_view.set_layers(
            centers=controls.centers.isChecked(), boxes=controls.boxes.isChecked(),
            masks=controls.masks.isChecked(), opacity=controls.opacity.value() / 100,
        )

    def _select_annotation(self, selected: Detection | Segmentation | None) -> None:
        self._selected = selected
        self.metadata_button.setEnabled(selected is not None)
        if selected is None:
            self.selection_label.setText("Kliknij oznaczenie, aby zobaczyć jego dane.")
            self.selection_label.setToolTip("")
            return
        metadata = selected.metadata
        if isinstance(selected, Detection):
            identity = selected.detection_id
            confidence = metadata.get("confidence")
        else:
            identity = selected.segmentation_id
            confidence = metadata.get("score")
        description = ""
        if isinstance(selected, Detection) and self._presented is not None and self._presented.result is not None:
            description = assignment_description(self._presented.result, selected.detection_id) + " · "
        text = description + (
            f"ID: {identity} · pochodzenie: {metadata.get('origin', 'nieznane')}"
            + f" · pewność: {confidence if confidence is not None else 'nieznana'}"
        )
        self.selection_label.setText(text)
        self.selection_label.setToolTip(text)

    def _show_text(self, title: str, text: str) -> None:
        self.controller.pause()
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(680, 480)
        layout = QVBoxLayout(dialog)
        contents = QPlainTextEdit()
        contents.setReadOnly(True)
        contents.setPlainText(text)
        layout.addWidget(contents)
        close = QPushButton("Zamknij")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _show_metadata(self) -> None:
        if self._selected is not None:
            metadata = dict(self._selected.metadata)
            if isinstance(self._selected, Detection) and self._presented is not None:
                result = self._presented.result
                if result is not None:
                    assignment = result.assignments.get(self._selected.detection_id)
                    metadata["wynik_v04"] = {
                        "opis": assignment_description(result, self._selected.detection_id),
                        "rekord": None if assignment is None else dict(assignment.metadata),
                    }
            self._show_text("Dane zapisanego oznaczenia", json.dumps(
                metadata, ensure_ascii=False, indent=2, default=str,
            ))

    def _show_frame_info(self) -> None:
        view, series = self._presented, self.controller.series
        if view is not None and series is not None:
            self._show_text("Informacje o klatce", "\n".join((
                self.frame_label.text(), view.registration_text,
                view.annotations.detection_message, view.annotations.segmentation_message,
                *series.diagnostics, *view.annotations.diagnostics,
            )))

    def _sync_frame_slider(self) -> None:
        with QSignalBlocker(self.frame_slider):
            self.frame_slider.setValue(self.controller.current_index + 1)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self.filmstrip.shutdown()
        self.controller.shutdown()
        super().closeEvent(event)

    def _finish_background_work(self) -> None:
        # Stop both producers before joining; workers must not outlive Qt signals.
        self.filmstrip.shutdown()
        self.controller.shutdown()
        self.filmstrip.wait_for_workers()
        self.controller.wait_for_workers()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if event is not None and event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            self.controller.pause()
        return super().eventFilter(watched, event)
