"""Bounded Qt checks of the offline E7 viewer and invented technical fixture.

The fixture does not load checkpoints, perform inference or fit classifiers.
Successful UI checks are separate from scientific validation and user acceptance.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_OPENGL', 'software')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --disable-dev-shm-usage')

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

GATES = ('H_M1', 'A_fixed_M1')
COMPARISONS = ('geometry', 'historical')


def fixture(root: Path):
    """Create tiny illustrative records for masks, geometry identity and scores."""
    import numpy as np
    from PIL import Image
    from .e7_gallery import write_gallery

    root.mkdir(parents=True, exist_ok=False)
    (root / 'images').mkdir()
    (root / 'runs').mkdir()
    models = [dict(id='geometry', label='Uczona geometria', family='geometry', seed=None),
              dict(id='geometry_photometry', label='Geometria + fotometria', family='geometry_photometry', seed=None)]
    for family, label in (('geometry_ae', 'Geometria + AE'), ('geometry_rvae', 'Geometria + rVAE')):
        for seed in (20261101, 20261102, 20261103):
            models.append(dict(id=f'{family}_seed{seed}', label=f'{label} · {seed}', family=family, seed=seed))
    samples, runs = [], []
    for ident, kind, case, size in (('ttmapp-259', 'measurement', None, 256),
                                    ('fixture-resample', 'synthetic', 'resample_2x', 384),
                                    ('fixture-noise', 'synthetic', 'noise', 192)):
        yy, xx = np.mgrid[:size, :size]
        Image.fromarray(np.uint8(90 + 50 * np.sin(xx / 9) * np.cos(yy / 9))).save(root / 'images' / f'{ident}.png')
        xy = [] if case == 'noise' else [[size * x, size * y] for x, y in ((.2, .2), (.35, .35), (.5, .5), (.65, .65), (.8, .8), (.9, .4))]
        samples.append(dict(id=ident, title='TTMAPP · klatka 259' if kind == 'measurement' else f'{case} · techniczny',
                            kind=kind, case=case, role='known_stm_development' if kind == 'measurement' else 'synthetic_validation',
                            image=f'images/{ident}.png', width=size, height=size, xy=xy,
                            element_ids=[f'p{i}' for i in range(len(xy))]))

    def head(n, labels):
        before = labels[:n]
        stages = dict(H_M1=[label if i < 3 else 0 for i, label in enumerate(before)],
                      A_fixed_M1=[label if i in (0, 2) else 0 for i, label in enumerate(before)])
        stats = {name: dict(coverage=sum(value > 0 for value in result) / n if n else None,
                            merge_rate=0 if n else None, split_rate=0 if n else None,
                            assigned=sum(value > 0 for value in result), domain_count=len(set(result) - {0}))
                 for name, result in stages.items()}
        return dict(before=before, valid=[True, True, True, True, False, False][:n], stats=stats, **stages)

    for sample, model, method in itertools.product(samples, models, ('fh4', 'mws')):
        n = len(sample['xy'])
        ident = f'fixture-{len(runs)}'
        geometry = head(n, [1, 1, 2, 3, 0, 0])
        learned = copy.deepcopy(geometry) if model['family'] == 'geometry' else head(n, [8, 8, 8, 9, 0, 0])
        historical = head(n, [4, 4, 0 if model['family'] == 'geometry_photometry' else 5, 6, 0, 0])
        if n and model['family'] == 'geometry_photometry':
            historical['valid'][2] = False
        payload = dict(id=ident, available=[True, True, True, True, False, True][:n],
                       common_valid=[True, True, True, True, False, False][:n],
                       hard=[True, True, True, False, False, False][:n],
                       full_gate=[True, False, True, False, False, False][:n],
                       edges=[[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]] if n else [],
                       learned_score=[.9, .4, .2, None, None] if n else [], learned=learned,
                       geometry=geometry, historical=historical,
                       pair_stats=dict(n_same=2 if n else 0, n_different=1 if n else 0,
                                       boundary_prevalence=1 / 3 if n else None,
                                       roc_auc=.75 if n else None, average_precision=.5 if n else None))
        relative = f'runs/{ident}.js'
        (root / relative).write_text('window.E7_RUN_DATA=' + json.dumps(payload) + ';\n')
        runs.append(dict(id=ident, sample_id=sample['id'], model_id=model['id'], family=model['family'],
                         seed=model['seed'], partition=method, path=relative))
    data = dict(samples=samples, runs=runs, models=models, score_kind='p_same',
                default_model_id='geometry_rvae_seed20261101', fixture=True)
    write_gallery(root / 'index.html', data)
    return root / 'index.html', len(samples), len(runs)


def main():
    """Check supplied prepared artifacts; retain JSON and screenshots on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path, nargs='?')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--expected-samples', type=int, default=105)
    parser.add_argument('--expected-runs', type=int, default=1680)
    args = parser.parse_args()
    output = args.out.resolve()
    if (output / 'browser-check.json').exists():
        raise FileExistsError('Preserve previous browser checks')
    output.mkdir(parents=True, exist_ok=True)
    if args.fixture:
        html, expected_samples, expected_runs = fixture(output / 'fixture')
    else:
        if args.html is None or not args.html.is_file():
            raise FileNotFoundError(args.html)
        html, expected_samples, expected_runs = args.html.resolve(), args.expected_samples, args.expected_runs
    app = QApplication(['e7-gallery-check'])
    errors, checks, screenshots = [], [], []

    class Page(QWebEnginePage):
        """Retain console errors as explicit test failures."""
        def javaScriptConsoleMessage(self, level, message, line, source):
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(dict(message=message, line=line, source=source))

    view = QWebEngineView()
    view.setPage(Page(view))
    view.resize(1480, 1300)
    view.show()

    def wait(milliseconds=25):
        loop = QEventLoop()
        QTimer.singleShot(milliseconds, loop.quit)
        loop.exec()

    def js(code):
        answer, loop = [], QEventLoop()
        view.page().runJavaScript(code, lambda value: (answer.append(value), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        if not answer:
            raise RuntimeError('JavaScript callback timed out')
        return answer[0]

    def record(action, **expected):
        deadline, state = time.monotonic() + 20, None
        while time.monotonic() < deadline:
            wait()
            state = js('window.e7State||null')
            if errors or state and state.get('error'):
                raise AssertionError((errors, state))
            if state and state.get('ready') and all(state.get(key) == value for key, value in expected.items()):
                checks.append(dict(action=action, state=state))
                return state
        raise AssertionError((action, expected, state))

    def select(ident, value):
        name = f'document.getElementById({json.dumps(ident)})'
        event = 'input' if ident == 'frame' else 'change'
        js(f'{name}.value={json.dumps(value)};{name}.dispatchEvent(new Event({json.dumps(event)}));')

    def click(ident):
        js(f'document.getElementById({json.dumps(ident)}).click()')

    def options(ident):
        return js(f'Array.from(document.getElementById({json.dumps(ident)}).options,o=>o.value)')

    def point_click(index, canvas='learned-canvas'):
        js(f'''(()=>{{const canvas=document.getElementById({json.dumps(canvas)}),rect=canvas.getBoundingClientRect(),p=currentSample.xy[{index}];
          canvas.dispatchEvent(new MouseEvent('click',{{bubbles:true,clientX:rect.left+p[0]*rect.width/currentImage.naturalWidth,
          clientY:rect.top+p[1]*rect.height/currentImage.naturalHeight}}));}})()''')

    def screenshot(name):
        wait(150)
        path = output / name
        if not view.grab().save(str(path)):
            raise RuntimeError('Screenshot failed')
        screenshots.append(str(path))

    failure, started = None, time.monotonic()
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        initial = record('initial', sample='ttmapp-259', partition='fh4', gate='H_M1', comparison='geometry', before=False)
        assert initial['sample_count'] == expected_samples and initial['run_count'] == expected_runs
        assert 'rvae' in initial['family'] and initial['seed'] == 20261101
        assert 'syntetykach' in js('document.body.textContent')
        samples = js('E7_DATA.samples.map(s=>({id:s.id,kind:s.kind,case:s.case||null,width:s.width,height:s.height}))')
        models = js('E7_DATA.models')
        assert len(models) == 8 and set(options('model')) == {model['id'] for model in models}
        assert set(options('comparison')) == set(COMPARISONS) and set(options('gate')) == set(GATES)
        screenshot('paired-learned-stm.png')
        geometry = next(model for model in models if model['family'] == 'geometry')
        for model in models:
            select('model', model['id'])
            record('model', model_id=model['id'])
            for comparison, gate in itertools.product(COMPARISONS, GATES):
                select('comparison', comparison)
                select('gate', gate)
                record('model_comparison_gate', model_id=model['id'], comparison=comparison, gate=gate)
                if model['id'] == geometry['id'] and comparison == 'geometry':
                    assert js('JSON.stringify(baseLabels)===JSON.stringify(learnedLabels)')
                    click('before')
                    record('geometry_identity_before', before=True)
                    assert js('JSON.stringify(baseLabels)===JSON.stringify(learnedLabels)')
                    click('before')
                    record('geometry_identity_after', before=False)
        if args.fixture:
            select('model', geometry['id'])
            select('comparison', 'historical')
            select('gate', 'H_M1')
            record('fixture_renumbering')
            assert js('baseLabels.some((value,i)=>value!==learnedLabels[i])')
            assert js('baseLabels.every((value,i)=>palette(baseLabels).get(value)===palette(learnedLabels).get(learnedLabels[i]))')
            point_click(5)
            record('fixture_missing_common_feature', selected_point=5)
            assert js('currentRun.available[5]&&!currentRun.common_valid[5]&&learnedLabels[5]===0')
            select('model', 'geometry_photometry')
            record('fixture_legacy_specific_validity', model_id='geometry_photometry', base_valid=3, learned_valid=4)
            point_click(2)
            record('fixture_legacy_missing_descriptor', selected_point=2)
            assert js('currentRun.common_valid[2]&&!baseHead.valid[2]&&learnedHead.valid[2]&&baseLabels[2]===0')
        select('model', initial['model_id'])
        select('comparison', 'geometry')
        select('gate', 'H_M1')
        record('restore_default_model', model_id=initial['model_id'], comparison='geometry', gate='H_M1')
        if initial['point_count']:
            point_click(min(1, initial['point_count'] - 1))
            record('point_click', selected_point=min(1, initial['point_count'] - 1))
            assert 'Pozycja raw' in js("document.getElementById('detail').textContent")
            assert 'tej samej domeny' in js("document.getElementById('incident').textContent")
            js("document.getElementById('detail').scrollIntoView()")
            screenshot('point-gates-and-relations.png')
            js('window.scrollTo(0,0)')
        for ident in ('points', 'before'):
            click(ident)
            record('toggle_' + ident, **{ident: ident == 'before'})
            if ident == 'before':
                assert 'ukryte' in js("document.getElementById('learned-metrics').textContent")
                if args.fixture:
                    assert js('e7State.learned_assigned===4')
            click(ident)
            record('restore_' + ident, **{ident: ident != 'before'})
        click('next')
        record('next', index=initial['index'] + 1)
        click('prev')
        record('previous', sample='ttmapp-259')
        for method in options('partition'):
            select('partition', method)
            record('solver', partition=method)
        resampled = next((sample for sample in samples if sample['case'] in ('resample_2x', 'resample2x')), None)
        assert resampled is not None
        select('sample', resampled['id'])
        record('resampled_dimensions', sample=resampled['id'], width=resampled['width'], height=resampled['height'])
        assert js('currentSample.xy.every(xy=>xy[0]>=0&&xy[1]>=0&&xy[0]<currentImage.naturalWidth&&xy[1]<currentImage.naturalHeight)')
        screenshot('synthetic-validation-resample.png')
        empty = next(sample for sample in samples if sample['case'] == 'noise')
        select('sample', empty['id'])
        record('zero_centers', sample=empty['id'], point_count=0, base_assigned=0, learned_assigned=0)
        click('learned-canvas')
        record('empty_click', selected_point=None)
        screenshot('noise-without-centers.png')
        for sample in samples:
            select('sample', sample['id'])
            record('load_sample', sample=sample['id'])
        select('frame', expected_samples - 1)
        record('slider_last', index=expected_samples - 1)
        assert js("document.getElementById('next').disabled")
        select('frame', 0)
        record('slider_first', index=0)
        assert js("document.getElementById('prev').disabled")
        select('sample', empty['id'])
        select('sample', 'ttmapp-259')
        record('rapid_selection', sample='ttmapp-259')
        wait(300)
        record('rapid_selection_stays_current', sample='ttmapp-259')
        assert not errors
    except Exception as exc:
        failure = repr(exc)
    finally:
        report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                      fixture=args.fixture, expected_samples=expected_samples, expected_runs=expected_runs,
                      checks=checks, javascript_errors=errors, screenshots=screenshots, failure=failure,
                      wall_seconds=time.monotonic() - started)
        (output / 'browser-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        view.close()
        app.processEvents()
    if failure:
        raise AssertionError(failure)
    print(json.dumps(dict(checks=len(checks), screenshots=len(screenshots), javascript_errors=len(errors),
                         fixture=args.fixture, wall_seconds=report['wall_seconds'])))


if __name__ == '__main__':
    main()
