"""Computed memberships keep their meaning in colours, counts and image clicks."""

from dataclasses import replace
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QPointF, Qt

from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.series import Series
from stmdomains.ui.image_view import ImageView
from stmdomains.ui.result_controls import ResultControls
from stmdomains.ui.result_style import assignment_color, assignment_description, describe_result


def example_result():
    assignments = {
        "A": MoleculeAssignment("A", 1, "1", "1", "domain"),
        "B": MoleculeAssignment("B", 2, "1", "1", "domain"),
        "C": MoleculeAssignment("C", provisional_class_id="1", rejection_reason="class_ambiguous"),
        "D": MoleculeAssignment("D", status="suppressed_duplicate", rejection_reason="suppressed_duplicate"),
    }
    return FrameAnalysis("example", 0, 0, "complete", assignments=assignments,
                         classes=(ResultClass("1", "#ff8800"),))


def test_colours_distinguish_domains_without_promoting_provisional_classes():
    result = example_result()
    assert assignment_color(result, "A", "domains") != assignment_color(result, "B", "domains")
    assert assignment_color(result, "A", "classes") == "#ff8800"
    assert assignment_color(result, "B", "classes") == "#ff8800"
    assert assignment_color(result, "C", "classes") == "#969696"
    assert assignment_color(result, "D", "domains") == "#969696"


def test_legends_count_final_memberships_and_keep_duplicates_out_of_denominator():
    result = example_result()
    domains = describe_result(result, "domains")
    assert domains.summary == "Domeny: 2 · przypisano 2 / 3"
    assert [(item.label, item.count) for item in domains.legend] == [
        ("Domena 1", 1), ("Domena 2", 1), ("Nieprzypisane", 1), ("Duplikaty", 1),
    ]
    classes = describe_result(result, "classes")
    assert classes.summary == "Klasy: 1 · przypisano 2 / 3"
    assert [(item.label, item.count) for item in classes.legend] == [
        ("Klasa 1", 2), ("Nieprzypisane", 1), ("Duplikaty", 1),
    ]
    assert classes.legend[0].color == "#ff8800"
    assert "lokalne" in classes.note
    assert "wstępne" in classes.note


def test_no_analysis_insufficient_fit_and_no_annotations_do_not_claim_zero_domains():
    assert describe_result(None, "domains").summary == "Brak analizy tej klatki"
    insufficient = replace(example_result(), status="insufficient_data", classes=(),
                           message="Za mało różnych otoczeń dla K5.")
    description = describe_result(insufficient, "domains")
    assert description.summary == "Brak dopasowania klas"
    assert "Za mało różnych otoczeń" in description.note
    no_annotations = FrameAnalysis("example", 0, 0, "no_annotations")
    assert describe_result(no_annotations, "domains").summary == "Brak oznaczeń do analizy"
    zero = replace(example_result(), assignments={"C": example_result().assignments["C"]})
    assert describe_result(zero, "domains").summary == "Domeny: 0 · przypisano 0 / 1"
    assert assignment_color(None, "C", "domains") == "#46e6be"
    assert assignment_color(insufficient, "C", "domains") == "#969696"
    assert describe_result(zero, "input").summary == "Oznaczenia wejściowe"


def test_molecule_details_explain_refusal_and_distinguish_missing_fit():
    result = example_result()
    assert assignment_description(result, "A") == "Klasa lokalna: 1 · domena lokalna: 1"
    refused = assignment_description(result, "C")
    assert "niejednoznaczna klasa" in refused
    assert "wstępna: 1" in refused
    assert "nie jest przypisaniem" in refused
    assert "Pominięty duplikat" in assignment_description(result, "D")
    assert "poza mianownikiem" in assignment_description(result, "D")
    failed = replace(result, status="insufficient_data", message="Za mało próbek dla K5.")
    assert "Za mało próbek dla K5" in assignment_description(failed, "A")
    assert assignment_description(None, "A") == "Brak analizy tej klatki"


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
                                 np.ones((2, 32, 32)), raw_payload=payload, identity="example"))


def test_visible_memberships_survive_selection_zoom_gamma_and_registration(qtbot):
    presenter = example_presenter()
    frame = presenter.present(0, result=example_result())
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
    view.set_frame(presenter.present(0, "expanded_aligned", gamma=2, result=example_result()))
    assert colour(11, 10) == "#5cb8ff"
    view.set_frame(presenter.present(0))
    assert colour(10, 10) == "#46e6be"


def test_suppressed_overlap_cannot_cover_or_steal_selection_of_assigned_molecule(qtbot):
    frame = example_presenter(duplicate_overlap=True).present(0, result=example_result())
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


def test_input_colours_and_legend_agree_even_when_fitting_is_unavailable():
    result = replace(example_result(), status="insufficient_data")
    display = describe_result(result, "input")
    assert display.summary == "Oznaczenia wejściowe"
    assert [(item.label, item.color, item.count) for item in display.legend] == [
        ("Oznaczenia", "#46e6be", 4),
    ]
    assert assignment_color(result, "C", "input") == "#46e6be"


def test_result_panel_is_compact_and_keeps_height_while_legend_and_status_change(qtbot):
    presenter = example_presenter()
    panel = ResultControls()
    qtbot.addWidget(panel)
    panel.resize(850, panel.sizeHint().height())
    panel.show()
    panel.set_frame(presenter.present(0, result=example_result()))
    qtbot.wait(10)
    height = panel.height()
    assert height < 48
    assert panel.mode.currentData() == "domains"
    assert panel.summary.text() == "Domeny: 2 · przypisano 2 / 3"
    assert "Domena 1" in panel.legend.text()
    assert panel.details_button.isEnabled()
    modes = []
    panel.mode_changed.connect(modes.append)
    panel.mode.setCurrentIndex(panel.mode.findData("classes"))
    assert modes == ["classes"]
    assert "Klasa 1" in panel.legend.text()
    assert "lokalne" in panel.mode.toolTip()
    crowded = replace(example_result(), assignments={
        str(index): MoleculeAssignment(str(index), index, "1", "1", "domain")
        for index in range(1, 21)
    })
    panel.mode.setCurrentIndex(panel.mode.findData("domains"))
    panel.set_frame(presenter.present(0, result=crowded))
    qtbot.wait(10)
    assert panel.height() == height
    assert panel.legend_scroll.horizontalScrollBar().maximum() > 0
    panel.set_frame(presenter.present(0, result=replace(example_result(), status="insufficient_data")))
    qtbot.wait(10)
    assert panel.summary.text() == "Brak dopasowania klas"
    assert panel.height() == height
    panel.set_frame(presenter.present(0))
    assert not panel.mode.isEnabled() and not panel.details_button.isEnabled()
    assert panel.summary.text() == "Brak analizy tej klatki"
    assert panel.height() == height


def test_outside_field_annotations_are_reported_separately_from_active_molecules():
    result = example_result()
    outside = MoleculeAssignment("E", status="outside_field", rejection_reason="outside_field")
    result = replace(result, assignments=dict(result.assignments, E=outside))
    display = describe_result(result, "domains")
    assert display.summary == "Domeny: 2 · przypisano 2 / 3"
    assert display.legend[-1].label == "Poza polem"
    assert display.legend[-1].count == 1
    assert "poza mianownikiem" in assignment_description(result, "E")
