"""Document lifecycle: explicit result selection and asynchronous save-before-leave."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMenu

from stmdomains.core.project import ProjectSnapshot
from stmdomains.ui.project_prompts import ProjectPrompts
from stmdomains.ui.project_selection import analysis_identifier
from stmdomains.ui.project_view import capture_view, capture_draft, restore_view, restore_draft

if TYPE_CHECKING:
    from stmdomains.ui.main_window import STMDomainsMainWindow


class ProjectActions:
    def __init__(self, window: 'STMDomainsMainWindow', prompts: ProjectPrompts, menu: QMenu | None) -> None:
        self.window, self.controller, self.prompts = window, window.controller, prompts
        self._baseline: tuple | None = None
        self._saving_state: tuple | None = None
        self._after_save: Callable[[], object] | None = None
        self._revision = 0
        self.controller.series_analysis_changed.connect(self._analysis_changed)
        self.controller.project_opened.connect(self._opened)
        self.controller.project_saved.connect(self._saved)
        self.save_actions = []
        if menu is not None:
            for label, shortcut, save_as in (('Zapisz projekt…', QKeySequence.StandardKey.Save, False),
                                             ('Zapisz projekt jako…', QKeySequence.StandardKey.SaveAs, True)):
                action = menu.addAction(label)
                if action is not None:
                    action.setShortcut(shortcut)
                    action.triggered.connect(lambda checked=False, variant=save_as: self.save(save_as=variant))
                    self.save_actions.append(action)
        self.controller.busy_changed.connect(lambda *_: self._refresh())
        self._refresh()

    def _analysis_changed(self) -> None:
        self._revision += 1

    def _state(self) -> tuple:
        return (self.controller.series.identity if self.controller.series else None, self._revision,
                capture_view(self.window), capture_draft(self.window.analysis_dialog),
                analysis_identifier(self.controller.result) if self.controller.result else None)

    @property
    def dirty(self) -> bool:
        return self.controller.series is not None and self._state() != self._baseline

    def _refresh(self) -> None:
        for action in self.save_actions:
            action.setEnabled(self.controller.can_analyze)

    def _opened(self, snapshot: ProjectSnapshot) -> None:
        restore_view(self.window, snapshot.view)
        restore_draft(self.window.analysis_dialog, snapshot.draft)
        self._baseline = self._state()
        self._after_save = None

    def open(self, path: Path | None = None) -> None:
        self.controller.pause()
        path = path or self.controller.prompts.choose_session()
        if path is not None:
            self._leave(lambda: self.controller.open_session(path))

    def allow_close(self) -> bool:
        if not self.dirty:
            return True
        decision = self.prompts.confirm_unsaved()
        if decision == 'discard':
            return True
        if decision == 'save':
            self.controller.cancel()
            self.save(after_save=lambda: self.window.close())
        return False

    def _leave(self, action: Callable[[], object]) -> None:
        if not self.dirty:
            action()
            return
        decision = self.prompts.confirm_unsaved()
        if decision == 'discard':
            action()
        elif decision == 'save':
            self.controller.cancel()
            self.save(after_save=action)

    def save(self, *, save_as: bool = False, after_save: Callable[[], object] | None = None) -> None:
        controller = self.controller
        controller.pause()
        if not controller.can_analyze or controller.series is None:
            return
        self._after_save = None
        path = controller.project_path
        if path is None or save_as:
            suggested = path or controller.series.session_path.with_suffix('.stmdomains')
            path = self.prompts.choose_path(suggested)
        if path is None:
            return
        options = []
        result, run = controller.result, controller.series_run
        if result is not None:
            options.append(('displayed', f'Wyświetlany wynik — cały dostępny przebieg {analysis_identifier(result)[:8]}'))
        if run is not None and (result is None or analysis_identifier(result) != run.identifier):
            options.append(('latest', f'Ostatni przebieg {run.identifier[:8]} — gotowe klatki {run.processed_count}/{len(run.indices)}'))
        options.append(('none', 'Bez analizy — obrazy, oznaczenia, widok i szkic parametrów'))
        selection = self.prompts.choose_analysis(options) if len(options) > 1 else 'none'
        if selection is None:
            return
        self._saving_state = self._state()
        try:
            controller.save_project(path, view=capture_view(self.window),
                                    draft=capture_draft(self.window.analysis_dialog), selection=selection)
            self._after_save = after_save
        except ValueError as error:
            controller.prompts.show_error(str(error))

    def _saved(self, path: Path) -> None:
        self._baseline = self._saving_state
        self.window.setWindowTitle(f'STM Domains — {path.name}')
        self.window.source_label.setText(path.name)
        self.window.source_label.setToolTip(str(path))
        callback, self._after_save = self._after_save, None
        # Changes made while copying a large source remain unsaved.
        if callback is not None and not self.dirty:
            QTimer.singleShot(0, callback)
