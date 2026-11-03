"""Acceptance controls apply explicitly and compare results on the same image."""

from PyQt6.QtCore import QPointF, QTimer, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QPlainTextEdit

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def test_acceptance_dialog_requires_result_applies_draft_compares_and_restores(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    action = window.findChild(QAction, "classAcceptanceAction")
    assert action is not None and not action.isEnabled()
    window.controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    action.trigger()
    dialog = window.class_acceptance_dialog
    assert dialog.isVisible() and not dialog.isModal() and not dialog.calculate.isEnabled()
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    base = window.controller.result
    assert dialog.calculate.isEnabled()
    window.image_view.zoom_by(1.3)
    before = (window.image_view.geometry(), window.image_view.transform())
    dialog.radius.setValue(.05)
    assert window.controller.result is base and "nieprzeliczone" in dialog.validation.text()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    tuned = window.controller.result
    assert tuned.assigned_count < base.assigned_count and tuned.catalogue is base.catalogue
    assert tuned.parameters["class_radius_multiplier"] == .05
    dialog.comparison.setCurrentIndex(1)
    assert window.controller.result is base and "Poprzedni" in dialog.displayed.text()
    assert dialog.radius.value() == 1.10
    dialog.comparison.setCurrentIndex(0)
    assert dialog.radius.value() == .05
    qtbot.mouseClick(dialog.baseline, Qt.MouseButton.LeftButton)
    assert window.controller.result is tuned and dialog.radius.value() == 1.10
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    assert window.controller.result.assignments == base.assignments
    assert (window.image_view.geometry(), window.image_view.transform()) == before
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert not dialog.calculate.isEnabled() and "Klatka 2" in dialog.context.text()
    window.close()
    qtbot.waitUntil(lambda: not window.controller.pending_task_count and not window.filmstrip.pending_task_count)


def test_k1_disables_margin_and_molecule_dialog_explains_all_stages(qtbot, tmp_path):
    from stmdomains.analysis.class_settings import ClassFitSettings
    from stmdomains.tools.class_discovery_demo import create_class_discovery_demo

    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(create_class_discovery_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.controller.fit_current_classes(ClassFitSettings(k=1))
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    base = window.controller.result
    window.class_acceptance_action.trigger()
    dialog = window.class_acceptance_dialog
    assert not dialog.margin.isEnabled() and dialog.radius.isEnabled()
    assert "K1" in dialog.rule.text() and "nie dotyczy" in dialog.rule.text()
    dialog.radius.setValue(.05)
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    assert window.controller.result.catalogue is base.catalogue
    assert window.controller.result.assigned_count < base.assigned_count
    dialog.close()
    window.annotation_controls.centers.setChecked(True)
    detection = window.controller.presenter.annotations.frame(0).detections[5]
    point = window.image_view.mapFromScene(QPointF(*detection.center_xy))
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert detection.detection_id in window.selection_label.text()
    texts = []

    def inspect_and_close():
        modal = QApplication.activeModalWidget()
        try:
            texts.append(modal.findChild(QPlainTextEdit).toPlainText())
        finally:
            modal.close()

    QTimer.singleShot(0, inspect_and_close)
    qtbot.mouseClick(window.metadata_button, Qt.MouseButton.LeftButton)
    assert len(texts) == 1
    for label in ("Klasa wstępna:", "Akceptacja klasy:", "Porządek lokalny:", "Domena końcowa:",
                  "Margines: nie dotyczy (K1", "nie jest prawdopodobieństwem"):
        assert label in texts[0]
    window.close()
    qtbot.waitUntil(lambda: not window.controller.pending_task_count and not window.filmstrip.pending_task_count)
