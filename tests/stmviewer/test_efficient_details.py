"""Recorded correspondence evidence is viewable without a model runtime."""
from PyQt6.QtWidgets import QApplication, QLabel, QTableWidget, QWidget

from stmviewer.correspondence_types import CorrespondenceDiagnostics


def test_saved_support_shows_both_original_image_grids_without_claiming_quality(qtbot):
    from stmviewer.ui.correspondence_details import CorrespondenceDetails
    parent = QWidget()
    qtbot.addWidget(parent)
    details = CorrespondenceDiagnostics(
        (-7., 5.), 72, 68, 52, 52 / 68,
        (1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 1, 2, 2, 1),
        (2, 1, 4, 3, 6, 5, 8, 7, 2, 1, 4, 3, 2, 1, 1, 2),
        (.8, .7), (.75, .65), .2, 'manual_review',
        'Spójna grupa; oceń dopasowanie struktur.', 'Konsensus v1',
    )
    widget = CorrespondenceDetails(parent)
    qtbot.addWidget(widget)
    widget.set_details(details)
    widget.show()
    summary = widget.findChild(QLabel, 'pairCorrespondenceDetails').text()
    assert '52 / 68' in summary
    assert 'bez niezależnej oceny' in summary
    assert details.reason in summary
    reference = widget.findChild(QTableWidget, 'correspondenceReferenceSupport')
    moving = widget.findChild(QTableWidget, 'correspondenceMovingSupport')
    assert (reference.rowCount(), reference.columnCount()) == (4, 4)
    assert reference.item(0, 1).text() == '2'
    assert moving.item(0, 1).text() == '1'
    assert reference.item(3, 3).text() == '1'
    widget.set_details(None)
    assert not widget.isVisible()


def test_all_support_cells_remain_visible_in_the_pair_sidebar(qtbot):
    from stmviewer.ui.correspondence_details import CorrespondenceDetails
    parent = QWidget()
    qtbot.addWidget(parent)
    widget = CorrespondenceDetails(parent)
    qtbot.addWidget(widget)
    widget.setFixedWidth(270)
    widget.set_details(CorrespondenceDiagnostics(
        (1., 2.), 32, 32, 32, 1., (2,) * 16, (2,) * 16,
        (.8, .8), (.8, .8), .1, 'manual_review', 'Poparcie.', 'v1'))
    parent.show()
    widget.show()
    QApplication.processEvents()
    for name in ('correspondenceReferenceSupport', 'correspondenceMovingSupport'):
        table = widget.findChild(QTableWidget, name)
        assert table.viewport().rect().contains(table.visualItemRect(table.item(3, 3)))
