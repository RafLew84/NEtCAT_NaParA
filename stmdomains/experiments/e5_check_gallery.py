"""Exercise the offline E5 viewer in Qt, optionally using invented fixture data.

This is an interface check, not a scientific test. The fixture creates source
points, masks and partitions without loading models or any experimental input.
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

from .e5_catalog import CONDITIONS, CONTEXTS, STAGES, conditions

FAMILIES = ('ae', 'rvae_full', 'rvae_content', 'fft')


def fixture(root: Path):
    """Create deliberately tiny UI records, including absent context and gates."""
    import numpy as np
    from PIL import Image
    from .e5_gallery import write_gallery

    root.mkdir(parents=True, exist_ok=False)
    (root / 'images').mkdir()
    (root / 'runs').mkdir()
    samples, runs = [], []
    source_xy = [[8., 8.], [40., 40.], [44., 44.], [30., 70.], [100., 100.], [235., 235.]]
    for ident, kind, case in (('ttmapp-259', 'measurement', None),
                               ('fixture-resample2x', 'synthetic', 'resample2x'),
                               ('fixture-noise', 'synthetic', 'noise')):
        spacing = [.5, .5] if case == 'resample2x' else [1., 1.]
        size = 512 if case == 'resample2x' else 256
        yy, xx = np.mgrid[:size, :size]
        Image.fromarray(np.uint8(90 + 50 * np.sin(xx * spacing[0] / 9) * np.cos(yy * spacing[1] / 9))).save(root / 'images' / f'{ident}.png')
        rows = {}
        for sampler in ('grid', 'centers'):
            xy = [] if case == 'noise' and sampler == 'centers' else [[v / spacing[j] for j, v in enumerate(point)] for point in source_xy]
            rows[sampler] = [dict(element_id=f'p{i}', xy=point, available=True) for i, point in enumerate(xy)]
        samples.append(dict(id=ident, kind=kind, case=case, frame=259 if kind == 'measurement' else None,
                            image=f'images/{ident}.png', width=size, height=size, pixel_spacing_xy=spacing, rows=rows))

    def evaluate(labels, mask, hard, full):
        before = [label if valid else 0 for label, valid in zip(labels, mask)]
        variants = {}
        for stage in STAGES:
            gate = hard if stage == 'H_M1' else full
            final = [label if keep else 0 for label, keep in zip(before, gate)]
            count = sum(value > 0 for value in final)
            variants[stage] = dict(labels=final, assigned=count, domain_count=len(set(final) - {0}),
                                   coverage=count / len(final) if final else None,
                                   merge_rate=0 if final else None, split_rate=0 if final else None)
        return dict(comparison_available=list(mask), feature_valid=list(mask), before=before, variants=variants)

    for sample, sampler, regime, family, method in itertools.product(
            samples, ('grid', 'centers'), ('transfer', 'transductive'), FAMILIES, ('fh4', 'mws')):
        ident = f'fixture-{len(runs)}'
        xy = [row['xy'] for row in sample['rows'][sampler]]
        n = len(xy)
        spacing = sample['pixel_spacing_xy']
        dimensions = [sample['width'], sample['height']]
        scope = [regime != 'transfer' or point[0] * spacing[0] <= 128 for point in xy]
        values = {}
        for meta in conditions(family):
            centers = copy.deepcopy(xy)
            origin = 8 if meta['id'] == 'center_snap' else 16 if meta['id'] == 'center_shift' else None
            if origin is not None:
                centers = [[(origin + 16 * np.ceil((value * spacing[j] - origin) / 16 - .5)) / spacing[j]
                            for j, value in enumerate(point)] for point in xy]
            measured_scales = [48] if origin is not None else [32, 48, 64]
            supports = {str(scale): [all((scale / 2 + 3) / spacing[j] <= value <= dimensions[j] - (scale / 2 + 3) / spacing[j]
                                        for j, value in enumerate(point))
                                    for point in centers] for scale in measured_scales}
            available = [all(supports[str(scale)][i] for scale in meta['scales']) for i in range(n)]
            values[meta['id']] = dict(patch_centers_xy=centers, support_by_scale=supports, available=available, contexts={})
        gate_available = [all(27 / spacing[j] <= value <= dimensions[j] - 27 / spacing[j]
                              for j, value in enumerate(point)) for point in xy]
        hard = [valid and i != 4 for i, valid in enumerate(gate_available)]
        full = [valid and i != 2 for i, valid in enumerate(hard)]
        labels = [1, 2, 2, 3, 3, 4][:n]
        for meta in conditions(family):
            condition = values[meta['id']]
            baseline = values[meta['baseline_id']]
            group = [other for other in conditions(family) if other['contrast'] == meta['contrast']]
            def region_scope(other):
                item = values[other['id']]
                radius = max(other['scales']) / 2 + 3
                return [bool(regime != 'transfer' or point[0] * spacing[0] + radius <= 128) for point in item['patch_centers_xy']]
            common_scope = [all(region_scope(other)[i] for other in group) for i in range(n)]
            own_scope = region_scope(meta)
            base_scope = region_scope(next(other for other in group if other['id'] == meta['baseline_id']))
            common = [common_scope[i] and all(values[other['id']]['available'][i] for other in group) for i in range(n)]
            changed_labels = [value + 10 for value in labels] if meta['id'] == 'map_full' else labels
            for context in CONTEXTS:
                mask = common if context == 'common' else [own_scope[i] and condition['available'][i] for i in range(n)]
                base_mask = common if context == 'common' else [base_scope[i] and baseline['available'][i] for i in range(n)]
                output = evaluate(changed_labels, mask, hard, full)
                output['scope'] = common_scope if context == 'common' else own_scope
                output['baseline'] = evaluate(labels, base_mask, hard, full)
                output['baseline']['scope'] = common_scope if context == 'common' else base_scope
                condition['contexts'][context] = output
        payload = dict(id=ident, scope=scope, pixel_spacing_xy=spacing, edges=[[i, i + 1] for i in range(max(0, n - 1))], min_size=1,
                       threshold=.37948280732455153, conditions=values,
                       gate_source=dict(condition_id='scale_base', label='dokładne centrum · 48 px',
                                        available=gate_available, hard=hard, full_gate=full,
                                        acf=[.2 if i == 2 else .6 for i in range(n)],
                                        ratio=[.5] * n, energy=[0 if i == 4 else .1 for i in range(n)]))
        relative = f'runs/{ident}.js'
        (root / relative).write_text('window.E5_RUN_DATA=' + json.dumps(payload) + ';\n')
        runs.append(dict(id=ident, sample_id=sample['id'], sampler=sampler, regime=regime, family=family,
                         seed=None if family == 'fft' else 20261101, partition=method, path=relative))
    data = dict(samples=samples, runs=runs, conditions=list(CONDITIONS), contexts=list(CONTEXTS),
                variants=list(STAGES), fixture=True, support_margin_reference_px=3, default_condition='map_full',
                common_support_note='przecięcie wszystkich warunków wybranego kontrastu (mapa, skala albo centrowanie)')
    write_gallery(root / 'index.html', data)
    return root / 'index.html', len(samples), len(runs)


def main():
    """Run bounded browser checks and retain the report even after a failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path, nargs='?')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--expected-samples', type=int, default=105)
    parser.add_argument('--expected-runs', type=int, default=8400)
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
    app = QApplication(['e5-gallery-check'])
    errors, checks, screenshots = [], [], []

    class Page(QWebEnginePage):
        """Collect JavaScript errors instead of silently discarding console output."""
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
            state = js('window.e5State||null')
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

    def point_click(index, canvas='changed-canvas'):
        js(f'''(()=>{{const canvas=document.getElementById({json.dumps(canvas)}),rect=canvas.getBoundingClientRect(),p=currentRows[{index}].xy;
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
        initial = record('initial', sample='ttmapp-259', sampler='centers', regime='transductive',
                         family='ae', seed=20261101, partition='fh4', condition='map_full', context='common', variant='H_M1')
        assert initial['sample_count'] == expected_samples and initial['run_count'] == expected_runs
        assert 'te same węzły grafu' in js('document.body.textContent')
        samples = js('E5_DATA.samples.map(s=>({id:s.id,kind:s.kind,case:s.case||null}))')
        assert set(options('condition')) == {condition['id'] for condition in CONDITIONS}
        assert set(options('context')) == set(CONTEXTS)
        assert set(options('variant')) == set(STAGES)
        screenshot('paired-map-ttmapp259.png')
        for condition in CONDITIONS:
            select('condition', condition['id'])
            for context in CONTEXTS:
                select('context', context)
                for stage in STAGES:
                    select('variant', stage)
                    record('condition_context_gate', condition=condition['id'], context=context, variant=stage)
                    if context == 'common':
                        assert js('JSON.stringify(baseView.comparison_available)===JSON.stringify(changedView.comparison_available)')
                    assert js('baseLabels.every((value,i)=>!value||baseView.comparison_available[i])&&changedLabels.every((value,i)=>!value||changedView.comparison_available[i])')
        if args.fixture:
            select('condition', 'map_full')
            select('context', 'common')
            select('variant', 'H_M1')
            record('fixture_renumbering')
            assert js('baseLabels.some((value,i)=>value!==changedLabels[i])')
            assert js('baseLabels.every((value,i)=>palette(baseLabels).get(value)===palette(changedLabels).get(changedLabels[i]))')
            select('condition', 'scale32')
            select('context', 'own')
            record('fixture_own_context_without_gate')
            assert js('changedCondition.available[5]&&!currentRun.gate_source.available[5]&&changedView.before[5]>0&&changedLabels[5]===0')
            assert js('baseView.comparison_available[5]===false&&changedView.comparison_available[5]===true')
            point_click(5)
            record('fixture_point_missing_gate', selected_point=5)
            assert 'brak pomiaru nie jest odmową struktury' in js("document.getElementById('detail').textContent")
            click('before')
            record('fixture_before_gate_has_proposal', before=True)
            assert js('changedLabels[5]>0&&baseLabels[5]===0')
            click('before')
            select('context', 'common')
            record('fixture_common_excludes_extra', before=False, context='common')
            assert js('!changedView.comparison_available[5]&&changedCondition.available[5]')
        select('condition', 'center_snap')
        select('context', 'common')
        record('centering_inspection', condition='center_snap', context='common')
        if initial['point_count'] > 1:
            point_index = 2 if args.fixture else 1
            point_click(point_index)
            record('selected_source_node', selected_point=point_index)
            assert 'Centrum wycinka raw' in js("document.getElementById('detail').textContent")
            assert 'nie obliczano' in js("document.getElementById('detail').textContent")
            assert 'nieużywana' in js("document.getElementById('detail').textContent")
            if args.fixture:
                assert js('JSON.stringify(changedCondition.patch_centers_xy[1])===JSON.stringify(changedCondition.patch_centers_xy[2])')
                assert js('JSON.stringify(currentRows[1].xy)!==JSON.stringify(currentRows[2].xy)')
                record('fixture_duplicate_patch_centers_keep_source_nodes')
            screenshot('centering-with-support.png')
            js("document.getElementById('detail').scrollIntoView()")
            screenshot('point-support-and-gates.png')
            js('window.scrollTo(0,0)')
        for ident in ('points', 'support', 'before'):
            click(ident)
            record('toggle_' + ident, **{ident: ident == 'before'})
            click(ident)
            record('restore_' + ident, **{ident: ident != 'before'})
        click('next')
        record('next', index=initial['index'] + 1)
        click('prev')
        record('previous', sample='ttmapp-259')
        for sampler in options('sampler'):
            select('sampler', sampler)
            record('sampler', sampler=sampler)
        for regime in options('regime'):
            select('regime', regime)
            record('regime', regime=regime)
            if regime == 'transfer':
                assert js('baseLabels.every((value,i)=>scopeFor(baseView)[i]||value===0)&&changedLabels.every((value,i)=>scopeFor(changedView)[i]||value===0)')
                if args.fixture:
                    select('condition', 'scale64')
                    select('context', 'own')
                    record('fixture_condition_specific_scope', condition='scale64', context='own')
                    assert js("currentRun.scope[4]&&baseView.scope[4]&&!changedView.scope[4]&&contextStatus(changedCondition,changedView,4)==='outside'")
                    select('condition', 'scale32')
                    record('fixture_scope_returns_for_smaller_window', condition='scale32')
                    assert js("changedView.scope[4]&&contextStatus(changedCondition,changedView,4)==='available'")
        families = set()
        for value in options('model'):
            select('model', value)
            family, seed = json.loads(value)
            record('model', family=family, seed=seed)
            assert set(options('condition')) == {condition['id'] for condition in conditions(family)}
            families.add(family)
        assert families == set(FAMILIES)
        for method in options('partition'):
            select('partition', method)
            record('solver', partition=method)
        resampled = next((sample for sample in samples if sample['case'] in ('resample2x', 'resample_2x')), None)
        if resampled is not None:
            select('sample', resampled['id'])
            select('condition', 'scale_base')
            select('regime', 'transductive')
            record('resampled_reference_scale', sample=resampled['id'], condition='scale_base',
                   pixel_spacing_xy=[.5, .5], regime='transductive')
            if args.fixture:
                point_click(2)
                record('resampled_source_node', selected_point=2)
                assert js('currentRows[2].xy[0]===88&&changedCondition.patch_centers_xy[2][0]===88')
            assert 'px odniesienia' in js("document.getElementById('scale48-key').textContent")
            assert '96×96 px raw' in js("document.getElementById('detail').textContent")
            rectangles = js('''(()=>{const ctx=document.getElementById('changed-canvas').getContext('2d'),original=ctx.strokeRect,boxes=[];
              ctx.strokeRect=function(...args){boxes.push(args);return original.apply(this,args)};
              try{render()}finally{ctx.strokeRect=original}return boxes;})()''')
            assert any(box[2:] == [96, 96] for box in rectangles), rectangles
            assert any(box[2:] == [108, 108] for box in rectangles), rectangles
            record('resampled_drawn_nominal_and_support_boxes')
            screenshot('resample2x-reference-windows.png')
        select('sampler', 'centers')
        record('restore_centers', sampler='centers')
        empty = next(sample for sample in samples if sample['case'] == 'noise')
        select('sample', empty['id'])
        record('zero_centers', sample=empty['id'], point_count=0, base_assigned=0, changed_assigned=0)
        click('changed-canvas')
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
