"""Public window workflow: save/open, draft separation and unsaved-work decisions."""

from pathlib import Path

from stmdomains.tools.auto_classes_demo import create_auto_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


class ProjectPrompts:
    def __init__(self, path):
        self.path = path
        self.selection = 'none'
        self.decision = 'cancel'
        self.asked = 0

    def choose_path(self, suggested):
        return self.path

    def choose_analysis(self, options):
        return self.selection

    def confirm_unsaved(self):
        self.asked += 1
        return self.decision


def test_window_roundtrip_view_draft_and_save_as_without_sources(qtbot, tmp_path):
    path = tmp_path / 'first.stmdomains'
    prompts = ProjectPrompts(path)
    window = STMDomainsMainWindow(prompts=Prompts(), project_prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(create_auto_demo(tmp_path / 'source'))
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.playback_controls.gamma.setValue(1.7)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.annotation_controls.centers.setChecked(False)
    window.result_controls.regions.opacity.setValue(61)
    window.analysis_dialog.class_fields.k.setValue(7)
    window.image_view.zoom_by(2)
    scale = window.image_view.transform().m11()
    assert window.project_actions.dirty
    window.project_actions.save()
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert path.exists() and not window.project_actions.dirty
    window.controller.series.source_path.unlink()
    window.controller.series.session_path.unlink()
    window.project_actions.open(path)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.controller.current_index == 1 and window.controller.gamma == 1.7
    assert window.analysis_dialog.class_fields.k.value() == 7
    assert not window.annotation_controls.centers.isChecked()
    assert window.result_controls.regions.opacity.value() == 61
    assert abs(window.image_view.transform().m11() - scale) < .0001
    assert not window.project_actions.dirty
    first = path.read_bytes()
    window.analysis_dialog.class_fields.k.setValue(4)
    prompts.path = tmp_path / 'second.stmdomains'
    window.project_actions.save(save_as=True)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert prompts.path.exists() and path.read_bytes() == first
    assert not window.project_actions.dirty
    window.close()


def test_cancel_close_and_save_before_close(qtbot, tmp_path):
    prompts = ProjectPrompts(tmp_path / 'work.stmdomains')
    window = STMDomainsMainWindow(prompts=Prompts(), project_prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(create_auto_demo(tmp_path / 'source'))
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.close()
    assert window.isVisible() and prompts.asked == 1
    prompts.decision = 'save'
    prompts.path = None
    window.close()
    assert window.isVisible()
    prompts.path = tmp_path / 'work.stmdomains'
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=15000)
    assert prompts.path.exists()


def test_discard_opens_new_work_and_failed_save_keeps_dirty_window(qtbot, tmp_path):
    prompts = ProjectPrompts(tmp_path / 'missing-directory' / 'work.stmdomains')
    imports = Prompts()
    errors = []
    imports.show_error = errors.append
    window = STMDomainsMainWindow(prompts=imports, project_prompts=prompts)
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(create_auto_demo(tmp_path / 'first'))
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    previous = window.controller.series
    target = create_auto_demo(tmp_path / 'second')
    window.project_actions.open(target)
    assert window.controller.series is previous
    prompts.decision = 'save'
    window.close()
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert errors and window.isVisible() and window.project_actions.dirty
    assert window.controller.series is previous
    prompts.decision = 'discard'
    window.project_actions.open(target)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.controller.series is not previous
    window.close()
    assert not window.isVisible()
