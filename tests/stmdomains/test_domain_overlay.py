"""Region layers are rendered from the final map, independently of molecule masks."""

from dataclasses import replace

import numpy as np
from PyQt6.QtCore import QPointF

from stmdomains.ui.image_view import ImageView
from test_analysis_presentation import example_presenter, example_result


def region_result():
    labels = np.zeros((32, 32), dtype=np.int32)
    labels[4:16, 4:15] = 1
    labels[7:9, 7:9] = 0  # A real hole must not be covered by a convex outline.
    labels[4:16, 17:29] = 2
    return replace(example_result(), domain_labels=labels)


def pixel(view, x, y):
    return view.viewport().grab().toImage().pixelColor(view.mapFromScene(QPointF(x, y))).name()


def test_region_fill_respects_holes_legend_modes_and_unanalysed_frame(qtbot):
    presenter = example_presenter()
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(500, 500)
    view.show()
    result = region_result()
    view.set_frame(presenter.present(0, result=result))
    view.set_layers(centers=False, boxes=False, masks=False, opacity=0)
    view.set_domain_layers(fill=True, outlines=False, numbers=False, opacity=1)
    assert pixel(view, 12, 12) == "#5cb8ff"
    assert pixel(view, 23, 12) == "#ff9a53"
    assert pixel(view, 7.5, 7.5) == pixel(view, 2, 2) == "#808080"
    view.zoom_by(1.1)
    zoom = view.transform().m11()
    view.set_assignment_mode("classes")
    assert pixel(view, 12, 12) == pixel(view, 23, 12) == "#ff8800"
    assert view.transform().m11() == zoom
    view.set_assignment_mode("input")
    assert pixel(view, 12, 12) == "#808080"
    view.set_assignment_mode("domains")
    view.set_frame(presenter.present(1))
    assert pixel(view, 12, 12) == "#808080"
    assert result.domain_count == 2


def test_outlines_and_numbers_can_be_shown_without_fill_at_zero_opacity(qtbot):
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(500, 500)
    view.show()
    view.set_frame(example_presenter().present(0, result=region_result()))
    view.set_layers(centers=False, boxes=False, masks=False, opacity=0)
    view.set_domain_layers(fill=False, outlines=False, numbers=False, opacity=0)
    plain = view.viewport().grab().toImage()
    view.set_assignment_mode("classes")
    view.set_domain_layers(fill=False, outlines=True, numbers=False, opacity=0)
    outlined = view.viewport().grab().toImage()
    assert outlined != plain
    assert pixel(view, 12, 12) == pixel(view, 7.8, 7.8) == "#808080"
    for x, y in ((4, 12), (17, 12), (7, 7.5)):
        point = view.mapFromScene(QPointF(x, y))
        assert "#ff8800" in {outlined.pixelColor(point.x() + dx, point.y() + dy).name()
                             for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    view.set_domain_layers(fill=False, outlines=False, numbers=True, opacity=0)
    numbered = view.viewport().grab().toImage()
    assert numbered != plain and numbered != outlined
    view.set_domain_layers(fill=False, outlines=False, numbers=False, opacity=0)
    assert view.viewport().grab().toImage() == plain


def test_region_geometry_tracks_fractional_translation_gamma_and_zoom(qtbot):
    presenter = example_presenter()
    result = replace(region_result(), working_index=1, source_index=1)
    view = ImageView()
    qtbot.addWidget(view)
    view.resize(600, 600)
    view.show()
    view.set_layers(centers=False, boxes=False, masks=False, opacity=0)
    view.set_domain_layers(fill=True, outlines=False, numbers=False, opacity=1)
    view.set_frame(presenter.present(1, result=result))
    assert pixel(view, 12, 12) == "#5cb8ff"
    aligned = presenter.present(1, "expanded_aligned", gamma=2, result=result)
    assert aligned.field_rect[:2] == (.5, .25)
    view.set_frame(aligned)
    view.zoom_by(1.15)
    scale = view.transform().m11()
    assert pixel(view, 12.5, 12.25) == "#5cb8ff"
    assert pixel(view, 23.5, 12.25) == "#ff9a53"
    assert pixel(view, 8, 7.75) != "#5cb8ff"  # Hole translates with the region.
    assert pixel(view, .1, 8) not in ("#5cb8ff", "#ff9a53")  # Padding.
    view.set_frame(presenter.present(1, "expanded_aligned", gamma=.5, result=result))
    assert pixel(view, 12.5, 12.25) == "#5cb8ff"
    assert view.transform().m11() == scale
    view.set_frame(presenter.present(1, result=replace(result, status="insufficient_data")))
    assert pixel(view, 12, 12) == "#808080"
    empty = replace(result, assignments={}, domain_labels=np.zeros((32, 32), dtype=np.int32))
    view.set_frame(presenter.present(1, result=empty))
    assert pixel(view, 12, 12) == "#808080"
