"""Existing GUI tests discard temporary work; lifecycle tests inject explicit decisions."""

import pytest

from stmdomains.ui.project_prompts import QtProjectPrompts


@pytest.fixture(autouse=True)
def discard_temporary_gui_work(monkeypatch):
    monkeypatch.setattr(QtProjectPrompts, 'confirm_unsaved', lambda self: 'discard')
