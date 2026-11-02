"""Saved assignments retain their meaning in colours, legends and image clicks."""

from dataclasses import replace
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QPointF, Qt

from stmdomains.core.domain_results import FrameResult, MoleculeAssignment, ResultClass
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.series import Series
from stmdomains.ui.image_view import ImageView
from stmdomains.ui.result_controls import ResultControls
from stmdomains.ui.result_style import assignment_color, assignment_description, describe_result


def example_result():
    assignments = {
        "A": MoleculeAssignment("A", 1, "C1", "C1", "domain", "", {}),
        "B": MoleculeAssignment("B", 2, "C1", "C1", "domain", "", {}),
        "C": MoleculeAssignment("C", 0, "", "C1", "uncertain_or_small", "class_ambiguous", {}),
        "D": MoleculeAssignment("D", 0, "", "", "suppressed_duplicate", "suppressed_duplicate", {}),
    }
    return FrameResult(True, assignments, (ResultClass("C1", "#ff8800"),))


def test_colours_distinguish_domains_without_promoting_provisional_classes():
    result = example_result()
    assert assignment_color(result, "A", "domains") != assignment_color(result, "B", "domains")
    assert assignment_color(result, "A", "classes") == "#ff8800"
    assert assignment_color(result, "B", "classes") == "#ff8800"
    assert assignment_color(result, "C", "classes") == "#969696"
    assert assignment_color(result, "D", "domains") == "#969696"


def test_legend_counts_final_assignments_and_keeps_duplicates_out_of_denominator():
    result = example_result()
    domains = describe_result(result, "domains")
    assert domains.summary == "Domeny: 2 · przypisano 2 / 3 · pominięte duplikaty: 1"
    assert [(item.label, item.count) for item in domains.legend] == [
        ("Domena 1", 1), ("Domena 2", 1), ("Nieprzypisane", 1), ("Pominięte duplikaty", 1),
    ]
    classes = describe_result(result, "classes")
    assert classes.summary == "Klasy w klatce: 1 · przypisano 2 / 3 · pominięte duplikaty: 1"
    assert [(item.label, item.count) for item in classes.legend] == [
        ("Klasa C1", 2), ("Nieprzypisane", 1), ("Pominięte duplikaty", 1),
    ]
    assert classes.legend[0].color == "#ff8800"


def test_no_attached_result_and_unanalysed_frame_are_distinct_from_zero_domains():
    assert describe_result(None, "domains").summary == "Brak dołączonego wyniku"
    absent = FrameResult(False, {}, ())
    assert describe_result(absent, "domains").summary == "Brak analizy tej klatki"
    zero = FrameResult(True, {"C": example_result().assignments["C"]}, ())
    assert describe_result(zero, "domains").summary == (
        "Domeny: 0 · przypisano 0 / 1 · pominięte duplikaty: 0"
    )
    assert assignment_color(absent, "C", "domains") == "#969696"
    assert assignment_color(None, "C", "domains") == "#46e6be"
    assert describe_result(zero, "input").summary == "Oznaczenia wejściowe · kolory wyniku wyłączone"


def test_selected_molecule_explains_final_assignment_refusal_or_suppression():
    result = example_result()
    assert assignment_description(result, "A") == "Klasa: C1 · domena lokalna: 1"
    refused = assignment_description(result, "C")
    assert "niejednoznaczna klasa" in refused
    assert "wstępna: C1" in refused
    assert "nie jest przypisaniem" in refused
    assert "Pominięty duplikat" in assignment_description(result, "D")
    assert "poza mianownikiem" in assignment_description(result, "D")
    assert "Brak analizy" in assignment_description(FrameResult(False, {}, ()), "C")


def example_presenter(*, duplicate_overlap=False):
    detections = [
        {"frame_index": 0, "detection_id": identity, "bbox_xyxy": [x - 2, y - 2, x + 2, y + 2]}
        for identity, x, y in (("A", 10, 10), ("B", 20, 10), ("C", 10, 20), ("D", 20, 20))
    ]
    if duplicate_overlap:
        detections[-1]["bbox_xyxy"] = [8.2, 8.1, 12.0, 12.0]
    payload = {
        "molecular_detections": {"frame_count": 2, "detections": detections},
        "registration": {"results_by_frame": [
            {"frame_index": 0, "shift_xy": [0, 0]},
            {"frame_index": 1, "shift_xy": [-0.5, 0.25]},
        ]},
    }
    return FramePresenter(Series(Path("input.json"), Path("input.mpp"), (0, 1), 0,
                                 np.ones((2, 32, 32)), raw_payload=payload))


def test_visible_result_colours_follow_molecules_and_selection_preserves_assignment(qtbot):
    presenter = example_presenter()
    frame = replace(presenter.present(0), result=example_result())
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(400, 400)
    view.show()
    view.set_frame(frame)
    view.set_assignment_mode("domains")

    def colour(x, y):
        point = view.mapFromScene(QPointF(x, y))
        return view.viewport().grab().toImage().pixelColor(point).name()

    assert colour(10, 10) == "#5cb8ff"
    assert colour(20, 10) == "#ff9a53"
    assert colour(10, 20) == colour(20, 20) == "#969696"
    selected = []
    view.annotation_selected.connect(lambda item: selected.append(item.detection_id))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     pos=view.mapFromScene(QPointF(10, 10)))
    assert selected == ["A"]
    assert colour(10, 10) == "#5cb8ff"
    view.zoom_by(1.1)
    zoom = view.transform().m11()
    view.set_assignment_mode("classes")
    assert colour(10, 10) == colour(20, 10) == "#ff8800"
    assert view.transform().m11() == zoom
    view.set_assignment_mode("input")
    assert colour(10, 10) == "#46e6be"
    view.set_assignment_mode("domains")
    view.set_frame(replace(presenter.present(0, "expanded_aligned", gamma=2), result=example_result()))
    assert colour(11, 10) == "#5cb8ff"
    view.set_frame(replace(frame, result=FrameResult(False, {}, frame.result.classes)))
    assert colour(10, 10) == "#969696"


def test_result_panel_switches_legend_without_changing_height(qtbot):
    frame = replace(example_presenter().present(0), result=example_result())
    panel = ResultControls()
    qtbot.addWidget(panel)
    panel.resize(650, panel.sizeHint().height())
    panel.show()
    panel.set_frame(frame)
    qtbot.wait(10)
    height = panel.height()
    assert panel.mode.currentData() == "domains"
    assert panel.summary.text() == "Domeny: 2 · przypisano 2 / 3 · pominięte duplikaty: 1"
    assert "Domena 1" in panel.legend.text()
    modes = []
    panel.mode_changed.connect(modes.append)
    panel.mode.setCurrentIndex(panel.mode.findData("classes"))
    assert modes == ["classes"]
    assert "Klasa C1" in panel.legend.text()
    assert "wstępne etykiety nie są przypisaniami" in panel.mode.toolTip()
    crowded = FrameResult(True, {
        str(index): MoleculeAssignment(str(index), index, "C1", "C1", "domain", "", {})
        for index in range(1, 21)
    }, frame.result.classes)
    panel.mode.setCurrentIndex(panel.mode.findData("domains"))
    panel.set_frame(replace(frame, result=crowded))
    qtbot.wait(10)
    assert panel.height() == height
    assert panel.legend_scroll.horizontalScrollBar().maximum() > 0
    panel.set_frame(replace(frame, result=FrameResult(False, {}, frame.result.classes)))
    qtbot.wait(10)
    assert panel.summary.text() == "Brak analizy tej klatki"
    assert panel.height() == height
    panel.set_frame(replace(frame, result=None))
    assert not panel.mode.isEnabled()
    assert panel.summary.text() == "Brak dołączonego wyniku"
    assert panel.height() == height


def test_result_details_are_available_only_with_an_attached_result(qtbot):
    panel = ResultControls()
    qtbot.addWidget(panel)
    assert not panel.details_button.isEnabled()
    frame = example_presenter().present(0)
    panel.set_frame(replace(frame, result=example_result()))
    assert panel.details_button.isEnabled()
    panel.set_frame(replace(frame, result=FrameResult(False, {}, ())))
    assert panel.details_button.isEnabled()
    panel.set_frame(frame)
    assert not panel.details_button.isEnabled()


def test_suppressed_overlap_cannot_cover_or_steal_selection_of_assigned_molecule(qtbot):
    frame = replace(example_presenter(duplicate_overlap=True).present(0), result=example_result())
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(400, 400)
    view.show()
    view.set_frame(frame)
    point = view.mapFromScene(QPointF(10, 10))
    assert view.viewport().grab().toImage().pixelColor(point).name() == "#5cb8ff"
    selected = []
    view.annotation_selected.connect(lambda item: selected.append(item.detection_id))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert selected == ["A"]
    view.set_assignment_mode("input")
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert selected == ["A", "D"]
