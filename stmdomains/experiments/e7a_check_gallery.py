"""Qt checks of the saved E7a viewer; no numerical inference or fitting."""
from __future__ import annotations

import argparse
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

from .bundle import file_hash
from .e7a_predict import RULES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    app = QApplication(['e7a-check'])
    errors, checks, screenshots = [], [], []
    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            if level == self.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(dict(message=message, line=line, source=source))
    view = QWebEngineView()
    view.setPage(Page(view)); view.resize(1480, 1300); view.show()
    def wait(ms=20):
        loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()
    def js(code):
        answer, loop = [], QEventLoop()
        view.page().runJavaScript(code, lambda value: (answer.append(value), loop.quit()))
        QTimer.singleShot(5000, loop.quit); loop.exec()
        if not answer: raise RuntimeError('JS callback timeout')
        return answer[0]
    def record(action, **expected):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            wait(); state = js('window.e7State||null')
            if errors or state and state.get('error'): raise AssertionError((errors, state))
            if state and state.get('ready') and all(state.get(k) == v for k, v in expected.items()):
                checks.append(dict(action=action, state=state)); return state
        raise AssertionError((action, expected, state))
    def select(ident, value):
        event = 'input' if ident == 'frame' else 'change'
        js(f"(()=>{{const e=document.getElementById({json.dumps(ident)});e.value={json.dumps(value)};e.dispatchEvent(new Event('{event}'));}})()")
    def click(ident):
        js(f'document.getElementById({json.dumps(ident)}).click()')
    def screenshot(name):
        wait(150)
        path = out / name
        if not view.grab().save(str(path)): raise RuntimeError('Screenshot failed')
        screenshots.append(dict(path=name, sha256=file_hash(path)))
    started, failure = time.monotonic(), None
    try:
        view.load(QUrl.fromLocalFile(str(args.html.resolve())))
        initial = record('initial', sample='ttmapp-259', partition='mws_t050', comparison='historical', gate='H_M1')
        assert initial['sample_count'] == 105 and initial['run_count'] == 5040
        assert initial['model_id'] == 'geometry_rvae_seed20261101'
        assert 'E7a' in js('document.title')
        screenshot('stm-default.png')
        models = js('E7_DATA.models')
        assert len(models) == 8
        assert set(js('Array.from(document.getElementById("partition").options,o=>o.value)')) == {r['id'] for r in RULES}
        for model, rule in itertools.product(models, RULES):
            select('model', model['id']); select('partition', rule['id'])
            record('model_rule', model_id=model['id'], partition=rule['id'])
            assert rule['label'] in js('document.getElementById("learned-title").textContent')
            for comparison, gate in itertools.product(('geometry', 'historical'), ('H_M1', 'A_fixed_M1')):
                select('comparison', comparison); select('gate', gate)
                record('comparison_gate', comparison=comparison, gate=gate)
                if (rule['id'], comparison) in (('e7_fh', 'geometry'), ('e7_mws', 'historical')):
                    assert js('JSON.stringify(baseLabels)===JSON.stringify(learnedLabels)')
                    click('before'); record('identity_before', before=True)
                    assert js('JSON.stringify(baseLabels)===JSON.stringify(learnedLabels)')
                    click('before'); record('identity_after', before=False)
        select('model', initial['model_id']); select('partition', 'mws_t050')
        select('comparison', 'historical'); select('gate', 'H_M1')
        record('restore', model_id=initial['model_id'], partition='mws_t050', gate='H_M1')
        scores = js('JSON.stringify(currentRun.learned_score)')
        for rule in RULES:
            select('partition', rule['id']); record('scores_unchanged', partition=rule['id'])
            assert scores == js('JSON.stringify(currentRun.learned_score)')
        select('partition', 'mws_t050'); record('restore_rule', partition='mws_t050')
        js("(()=>{const c=document.getElementById('learned-canvas'),r=c.getBoundingClientRect(),p=currentSample.xy[0];c.dispatchEvent(new MouseEvent('click',{clientX:r.left+p[0]*r.width/currentImage.naturalWidth,clientY:r.top+p[1]*r.height/currentImage.naturalHeight}));})()")
        record('click_source_point', selected_point=0)
        assert 'Pozycja raw' in js('document.getElementById("detail").textContent')
        assert 'tej samej domeny' in js('document.getElementById("incident").textContent')
        js('document.getElementById("detail").scrollIntoView()'); screenshot('point-details.png')
        js('window.scrollTo(0,0)')
        click('points'); record('hide', points=False); click('points'); record('show', points=True)
        click('before'); record('before', before=True); click('before'); record('after', before=False)
        click('next'); record('next', index=initial['index']+1)
        click('prev'); record('previous', sample='ttmapp-259')
        samples = js('E7_DATA.samples.map(s=>({id:s.id,case:s.case,role:s.role,width:s.width,height:s.height}))')
        assert sum(s['role'] == 'stm_development' for s in samples) == 24
        assert sum(s['role'] == 'validation' for s in samples) == 81
        for sample in samples:
            select('sample', sample['id']); record('sample', sample=sample['id'], width=sample['width'], height=sample['height'])
        for case in ('resample_2x', 'noise'):
            sample = next(s for s in samples if s['case'] == case)
            select('sample', sample['id']); record(case, sample=sample['id'])
            if case == 'noise': assert js('e7State.point_count===0&&e7State.learned_assigned===0')
            screenshot(case + '.png')
        select('frame', 104); record('slider_end', index=104)
        assert js('document.getElementById("next").disabled')
        select('frame', 0); record('slider_start', index=0)
        assert js('document.getElementById("prev").disabled')
        select('sample', 'ttmapp-259'); record('restore_stm', sample='ttmapp-259')
    except Exception as exc:
        failure = repr(exc)
    finally:
        report = dict(html=str(args.html.resolve()), html_sha256=file_hash(args.html), checks=checks,
            javascript_errors=errors, screenshots=screenshots, failure=failure,
            all_index_runs_opened=False, wall_seconds=time.monotonic()-started)
        (out / 'browser-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        view.close(); app.processEvents()
    if failure: raise AssertionError(failure)
    print(json.dumps(dict(checks=len(checks), javascript_errors=len(errors), screenshots=len(screenshots))))


if __name__ == '__main__':
    main()
