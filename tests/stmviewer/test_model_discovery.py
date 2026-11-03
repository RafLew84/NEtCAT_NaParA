"""Portable bundle defaults and explicit user/session choices at the model-control boundary."""
from pathlib import Path
import subprocess

import pytest
from PyQt6.QtWidgets import QLineEdit, QWidget

from stmviewer import model_paths
from stmviewer.deep_matcher import DeepMatcherOptions, default_deep_options
from stmviewer.efficient_matcher import default_efficient_options
from stmviewer.lightglue_matcher import default_lightglue_options
from stmviewer.matchanything_matcher import default_matchanything_options
from stmviewer.roma_matcher import default_roma_options
from stmviewer.ui.deep_matcher_controls import DeepMatcherControls


LAYOUTS = (
    ('deep_matcher_translation', 'loftr', default_deep_options,
     ('weights/loftr_outdoor.ckpt',)),
    ('efficient_loftr', 'efficientloftr', default_efficient_options,
     ('weights/eloftr_outdoor.ckpt', 'source/src/loftr/loftr.py')),
    ('lightglue_superpoint', 'lightglue', default_lightglue_options,
     ('weights/superpoint_lightglue.pth', 'weights/superpoint_v1.pth',
      'source/lightglue/__init__.py')),
    ('matchanything_eloftr', 'matchanything', default_matchanything_options,
     ('weights/matchanything_eloftr.ckpt', 'source/src/loftr/loftr.py')),
    ('roma_v2', 'romav2', default_roma_options,
     ('weights/romav2.0.1.pt', 'dinov3/hubconf.py', 'dinov3/dinov3/__init__.py')),
)


def create_files(root, names):
    for name in names:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'layout marker; not a model')


@pytest.fixture
def locations(tmp_path, monkeypatch):
    home = tmp_path / 'użytkownik'
    app = home / 'OneDrive - Laboratorium' / 'Dokumenty' / 'moja paczka' / 'NEtCAT'
    app.mkdir(parents=True)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setattr(model_paths, '__file__', str(app / 'stmviewer/model_paths.py'))
    monkeypatch.setattr(model_paths.sys, 'prefix', str(home / 'miniforge3/envs/stmviewer'))
    monkeypatch.delenv('STMVIEWER_LOFTR_WEIGHTS', raising=False)
    monkeypatch.chdir(tmp_path)  # Discovery follows the application, not the current directory.
    return home, app


@pytest.mark.parametrize('method,model,factory,files', LAYOUTS)
def test_portable_models_fill_ui_and_take_precedence_over_cache(
        qtbot, locations, monkeypatch, method, model, factory, files):
    home, app = locations
    create_files(app / 'models' / model, files)
    create_files(home / '.cache/stmviewer' / model, files)
    def no_process(*args, **kwargs):
        raise AssertionError('Discovery must not run an interpreter or model.')
    monkeypatch.setattr(subprocess, 'Popen', no_process)
    expected = factory()
    assert expected.weights.is_relative_to(app)
    parent = QWidget()
    qtbot.addWidget(parent)
    controls = DeepMatcherControls(parent)
    controls.set_method(method)
    assert controls.options() == expected
    # Explicit user or restored session paths must win, even when missing.
    explicit = DeepMatcherOptions(weights=home / 'missing.ckpt', device='cpu',
                                  source=home / 'missing-code', interpreter=home / 'python',
                                  extractor_weights=home / 'missing-extractor.pth')
    controls.set_options(explicit)
    controls.findChild(QLineEdit, 'deepWeights').clear()
    selected = controls.options()
    controls.set_method('phase_correlation' if method != 'deep_matcher_translation' else 'roma_v2')
    controls.set_method(method)
    assert controls.options() == selected
    assert controls.options().weights is None


@pytest.mark.parametrize('method,model,factory,files', LAYOUTS)
def test_incomplete_bundle_uses_complete_cache_without_mixing_files(locations, method, model, factory, files):
    home, app = locations
    # Incomplete bundle: create only the containing directory (or just its weights).
    (app / 'models' / model).mkdir(parents=True)
    if len(files) > 1:
        create_files(app / 'models' / model, files[:1])
    cache = home / '.cache/stmviewer' / model
    create_files(cache, files)
    options = factory()
    assert options.weights.is_relative_to(cache)
    if options.source is not None:
        assert options.source.is_relative_to(cache)
    if options.extractor_weights is not None:
        assert options.extractor_weights.is_relative_to(cache)


def test_explicit_loftr_environment_path_wins_even_when_missing(locations, monkeypatch):
    home, app = locations
    create_files(app / 'models/loftr', ('weights/loftr_outdoor.ckpt',))
    monkeypatch.setenv('STMVIEWER_LOFTR_WEIGHTS', str(home / 'custom/missing.ckpt'))
    assert default_deep_options().weights == home / 'custom/missing.ckpt'


def test_absent_models_keep_editable_defaults_and_no_implicit_download(locations):
    home, _ = locations
    assert default_deep_options().weights is None
    assert default_efficient_options().source == home / '.cache/stmviewer/efficientloftr/source'
    assert default_lightglue_options().extractor_weights == (
        home / '.cache/stmviewer/lightglue/weights/superpoint_v1.pth')


@pytest.mark.parametrize('platform,suffix', [('win32', 'python.exe'), ('linux', 'bin/python')])
def test_finds_documented_miniforge_roma_environment(locations, monkeypatch, platform, suffix):
    home, _ = locations
    monkeypatch.setattr(model_paths.sys, 'platform', platform)
    env = home / 'miniforge3/envs/stmviewer-roma'
    create_files(env, (suffix,))
    assert default_roma_options().interpreter == env / suffix


def test_roma_uses_registered_nonstandard_location_and_ignores_stale_entries(locations, monkeypatch):
    home, _ = locations
    monkeypatch.setattr(model_paths.sys, 'platform', 'win32')
    env = home / 'inny dysk' / 'środowiska' / 'netcat-romav2'
    create_files(env, ('python.exe',))
    registry = home / '.conda/environments.txt'
    registry.parent.mkdir()
    registry.write_text(f'{home}/absent/stmviewer-roma\nrelative/stmviewer-roma\n{env}\n')
    assert default_roma_options().interpreter == env / 'python.exe'


def test_roma_finds_sibling_of_main_conda_environment(locations, monkeypatch):
    home, _ = locations
    envs = home / 'custom-conda/envs'
    monkeypatch.setattr(model_paths.sys, 'prefix', str(envs / 'netcat'))
    monkeypatch.setattr(model_paths.sys, 'platform', 'linux')
    create_files(envs / 'netcat-romav2', ('bin/python',))
    assert default_roma_options().interpreter == envs / 'netcat-romav2/bin/python'


def test_roma_does_not_choose_current_environment_as_worker(locations, monkeypatch):
    home, _ = locations
    envs = home / 'miniforge3/envs'
    monkeypatch.setattr(model_paths.sys, 'prefix', str(envs / 'stmviewer-roma'))
    monkeypatch.setattr(model_paths.sys, 'platform', 'linux')
    create_files(envs / 'stmviewer-roma', ('bin/python',))
    create_files(envs / 'netcat-romav2', ('bin/python',))
    assert default_roma_options().interpreter == envs / 'netcat-romav2/bin/python'


def test_invalid_conda_registry_does_not_prevent_manual_setup(locations, monkeypatch):
    home, _ = locations
    monkeypatch.setattr(model_paths.sys, 'platform', 'linux')
    registry = home / '.conda/environments.txt'
    registry.parent.mkdir()
    registry.write_bytes(b'\xff')
    assert default_roma_options().interpreter == home / 'miniconda3/envs/netcat-romav2/bin/python'
