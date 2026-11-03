"""Weak model estimates stay distinguishable from unassessed graph solutions."""
from dataclasses import replace

from stmviewer.ui.registration_info import registration_info, registration_warnings
from test_efficient_session import evidence
from test_manual_movie import cpu_result


def weak_chain():
    base = cpu_result()
    diagnostic = replace(evidence(shape=base.frames[0].original.data.shape),
                         status='low_confidence', settings_version=2,
                         reason='Słabe poparcie: mały udział zgodnych wektorów.')
    frames = (base.frames[0],
              replace(base.frames[1], status='low_confidence', quality_score=None),
              replace(base.frames[2], status='manual_review', quality_score=None))
    return replace(base, method='EfficientLoFTR', frames=frames,
                   correspondence_diagnostics=(None, diagnostic, None))


def test_main_registration_distinguishes_weak_support_from_unverified_confidence():
    result = weak_chain()
    warnings = registration_warnings(result)
    assert 'Słabe poparcie' in warnings[1]
    assert 'pewność niezweryfikowana' in warnings[2]
    text = registration_info(result, 1, False)
    assert 'Słabe poparcie' in text.splitlines()[0]
    assert result.correspondence_diagnostics[1].reason in text
    assert result.frames[1].quality_score is None


def test_applied_graph_reports_weak_pair_count_without_relabelling_solver_confidence():
    from stmviewer.graph_application import apply_graph_to_movie
    from test_efficient_session import efficient_graph

    frames = tuple(frame.original for frame in cpu_result().frames)
    graph = efficient_graph(frames)
    first = graph.edges[0]
    weak = replace(first.correspondence_diagnostics, status='low_confidence', settings_version=2,
                   reason='Słabe poparcie: mały udział zgodnych wektorów.')
    graph = replace(graph, edges=(replace(first, status='low_confidence',
                                          correspondence_diagnostics=weak),) + graph.edges[1:])
    applied = apply_graph_to_movie(frames, graph)
    text = registration_info(applied, 1, False)
    assert 'Słabe poparcie par grafu: 1 / 3' in text
    assert 'Słabe pary zachowano w dopasowaniu' in text
    assert applied.frames[1].status == 'manual_review'
    assert applied.frames[1].quality_score is None
    assert 'pewność niezweryfikowana' in text.splitlines()[0]


def test_reopened_mpp_history_keeps_the_visible_weak_support_warning(tmp_path):
    from stmviewer.mpp import open_mpp_series
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.ui.frame_source import alignment_history_text

    path = tmp_path / 'weak-support.mpp'
    save_aligned_mpp(path, weak_chain())
    reopened = open_mpp_series(path, check_cancelled=lambda: None)
    text = alignment_history_text(reopened[1])
    assert 'Słabe poparcie' in text
    assert reopened[1].alignment.quality_score is None


def test_weak_saved_pair_shows_warning_and_remains_available_for_manual_application(qtbot):
    from PyQt6.QtWidgets import QLabel, QPushButton, QWidget
    from stmviewer.manual_movie import movie_pair_trial
    from stmviewer.ui.pair_dialog import PairComparisonDialog

    result = weak_chain()
    frames = tuple(frame.original for frame in result.frames)
    diagnostic = result.correspondence_diagnostics[1]
    trial = replace(movie_pair_trial(result, 1), method='efficient_loftr',
                    status='low_confidence', quality_score=None, correspondence=diagnostic)
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PairComparisonDialog(frames, 1, parent, initial_trial=trial, method='efficient_loftr')
    qtbot.addWidget(dialog)
    dialog.set_registration(result)
    dialog.show()
    details = dialog.findChild(QLabel, 'pairCorrespondenceDetails')
    assert details.isVisible() and diagnostic.reason in details.text()
    assert 'low_confidence' in dialog.findChild(QLabel, 'pairResult').text()
    correct = dialog.findChild(QPushButton, 'manualPairCorrect')
    assert correct.isEnabled()
    correct.click()
    dialog.findChild(QPushButton, 'manualPairXPlus').click()
    dialog.findChild(QPushButton, 'manualPairApply').click()
    apply = dialog.findChild(QPushButton, 'manualMovieApply')
    assert apply.isEnabled()
    with qtbot.waitSignal(dialog.movie_apply_requested) as emitted:
        apply.click()
    assert emitted.args[0].shift_xy == (3., -1.)
    dialog.close()
