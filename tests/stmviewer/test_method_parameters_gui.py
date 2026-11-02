"""User-visible parameter editing and shared configuration in the Qt workflow."""
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QPushButton

from stmviewer.ui.main_window import STMViewerMainWindow


def editor(window):
    window.findChild(QAction, 'methodParametersAction').trigger()
    return next(dialog for dialog in window.findChildren(QDialog, 'methodParametersDialog')
                if dialog.isVisible())


def select(dialog, method):
    combo = dialog.findChild(QComboBox, 'parameterMethod')
    combo.setCurrentIndex(combo.findData(method))


def field(dialog, method, name):
    return dialog.findChild(QLineEdit, method + '_' + name)


def finish(qtbot, dialog, button):
    dialog.findChild(QDialogButtonBox).button(button).click()
    qtbot.waitUntil(lambda: not dialog.isVisible())


def test_menu_editor_commits_both_drafts_or_discards_them_without_changing_selected_method(qtbot):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    dialog = editor(window)
    field(dialog, 'akaze', 'threshold').setText('0.000001')
    select(dialog, 'lightglue_superpoint')
    field(dialog, 'lightglue_superpoint', 'max_keypoints').setText('4096')
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Cancel)
    dialog = editor(window)
    assert float(field(dialog, 'akaze', 'threshold').text()) == .001
    assert int(field(dialog, 'lightglue_superpoint', 'max_keypoints').text()) == 2048
    field(dialog, 'akaze', 'threshold').setText('1e-6')
    field(dialog, 'lightglue_superpoint', 'max_keypoints').setText('4096')
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    assert window.findChild(QComboBox, 'registrationMethod').currentData() == 'phase_correlation'
    dialog = editor(window)
    assert float(field(dialog, 'akaze', 'threshold').text()) == .000001
    assert int(field(dialog, 'lightglue_superpoint', 'max_keypoints').text()) == 4096
    select(dialog, 'akaze')
    dialog.findChild(QPushButton, 'resetMethodParameters').click()
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    dialog = editor(window)
    assert float(field(dialog, 'akaze', 'threshold').text()) == .001
    assert int(field(dialog, 'lightglue_superpoint', 'max_keypoints').text()) == 4096
    field(dialog, 'akaze', 'threshold').setText('nan')
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.isVisible()
    assert dialog.findChild(QLabel, 'parameterError').text()
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Cancel)
    window.close()


def test_open_pair_graph_and_movie_use_new_profile_and_keep_old_result(qtbot, monkeypatch, tmp_path):
    from test_akaze_gui import opened_window
    from test_registration_gui import image
    window = opened_window(qtbot, monkeypatch, tmp_path)
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    dialog = editor(window)
    field(dialog, 'akaze', 'threshold').setText('0.0001')
    field(dialog, 'akaze', 'radius').setText('1.5')
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    run_pair = pair.findChild(QPushButton, 'runPair')
    run_pair.click()
    qtbot.waitUntil(run_pair.isEnabled)
    assert '0.0001' in pair.findChild(QLabel, 'pairParameterStatus').text()
    assert 'inlier_radius=1.5' in pair.findChild(QLabel, 'pairResult').text()
    run_graph = graph.findChild(QPushButton, 'runGraph')
    run_graph.click()
    qtbot.waitUntil(run_graph.isEnabled)
    assert '0.0001' in graph.findChild(QLabel, 'graphParameterStatus').text()
    run = window.findChild(QPushButton, 'registerFrames')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    assert '0.0001' in window.findChild(QLabel, 'movieParameterStatus').text()
    previous = image(window)
    dialog = editor(window)
    field(dialog, 'akaze', 'threshold').setText('0.0002')
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    for parent, name in ((pair, 'pairParameterStatus'), (graph, 'graphParameterStatus'),
                         (window, 'movieParameterStatus')):
        text = parent.findChild(QLabel, name).text()
        assert '0.0001' in text and '0.0002' in text
        assert 'różnią' in text
    assert image(window) == previous
    graph.close()
    pair.close()
    window.close()


def test_gui_session_restores_inactive_profiles(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog
    from test_akaze_gui import opened_window
    window = opened_window(qtbot, monkeypatch, tmp_path)
    dialog = editor(window)
    field(dialog, 'akaze', 'threshold').setText('0.0001')
    field(dialog, 'lightglue_superpoint', 'max_keypoints').setText('1024')
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    selector = window.findChild(QComboBox, 'registrationMethod')
    selector.setCurrentIndex(selector.findData('phase_correlation'))
    path = tmp_path/'profiles.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    save = window.findChild(QPushButton, 'saveSession')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    window.close()
    restored = STMViewerMainWindow()
    qtbot.addWidget(restored)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    open_session = restored.findChild(QPushButton, 'openSession')
    open_session.click()
    qtbot.waitUntil(open_session.isEnabled)
    assert 'Otwarto sesję' in restored.findChild(QLabel, 'sessionInfo').text()
    dialog = editor(restored)
    assert float(field(dialog, 'akaze', 'threshold').text()) == .0001
    assert int(field(dialog, 'lightglue_superpoint', 'max_keypoints').text()) == 1024
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Cancel)
    restored.close()


def test_busy_task_disables_commit_and_uses_its_original_snapshot(qtbot, monkeypatch, tmp_path):
    import cv2
    from threading import Event
    from test_akaze_gui import opened_window
    window = opened_window(qtbot, monkeypatch, tmp_path)
    dialog = editor(window)
    field(dialog, 'akaze', 'threshold').setText('0.0001')
    entered, release = Event(), Event()
    factory = cv2.AKAZE_create
    observed = []
    def detector(*args, **kwargs):
        observed.append(kwargs['threshold'])
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Test OpenCV boundary timed out')
        return factory(*args, **kwargs)
    monkeypatch.setattr(cv2, 'AKAZE_create', detector)
    run = window.findChild(QPushButton, 'registerFrames')
    try:
        run.click()
        qtbot.waitUntil(entered.is_set)
        ok = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        assert not ok.isEnabled()
        dialog.accept()
        assert dialog.isVisible()
    finally:
        release.set()
        qtbot.waitUntil(run.isEnabled)
    assert observed == [.001]
    assert '0.001' in window.findChild(QLabel, 'movieParameterStatus').text()
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    assert 'różnią' in window.findChild(QLabel, 'movieParameterStatus').text()
    window.close()


def test_reopening_editor_does_not_round_small_thresholds(qtbot):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    dialog = editor(window)
    field(dialog, 'akaze', 'threshold').setText('0.000123456789123')
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Ok)
    dialog = editor(window)
    assert float(field(dialog, 'akaze', 'threshold').text()) == .000123456789123
    finish(qtbot, dialog, QDialogButtonBox.StandardButton.Cancel)
    window.close()
