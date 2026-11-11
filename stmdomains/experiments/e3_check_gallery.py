"""Qt checks for the offline E3 paired viewer; optional tiny technical fixture."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-dev-shm-usage")

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

CONDITIONS = ("identity", "offset_minus", "offset_plus", "gain_minus", "gain_plus", "noise",
              "gradient_x_minus", "gradient_x_plus", "gradient_y_minus", "gradient_y_plus")
STAGES = ("H_M1", "A_fixed_M1", "A_updated_M1")
FAMILIES = ("ae", "rvae_full", "rvae_content", "rvae_angle", "fft", "photometry", "geometry")


def fixture(root):
    """Write invented UI-only data; these are not experimental E3 results."""
    import numpy as np
    from PIL import Image
    from .e3_gallery import write_gallery
    from .e3_metrics import assignment_stability

    root.mkdir(parents=True, exist_ok=False)
    (root / "images").mkdir()
    (root / "previews").mkdir()
    (root / "runs").mkdir()
    samples, runs = [], []
    for ident, kind, case, size in (("ttmapp-259", "measurement", None, 256),
                                    ("fixture-two", "synthetic", "two_orientations", 192),
                                    ("fixture-noise", "synthetic", "noise", 192)):
        yy, xx = np.mgrid[:size, :size]
        Image.fromarray(np.uint8(80 + 50 * np.sin(xx / 9) * np.cos(yy / 9))).save(root / "images" / f"{ident}.png")
        rows = {}
        for sampler in ("grid", "centers"):
            n = 0 if case == "noise" and sampler == "centers" else 3
            rows[sampler] = [dict(element_id=f"p{i}", xy=[size * t, size * t], available=True)
                             for i, t in enumerate((.2, .5, .8))][:n]
        samples.append(dict(id=ident, kind=kind, case=case, frame=259 if kind == "measurement" else None,
                            title="UI fixture " + ident, image=f"images/{ident}.png", width=size, height=size, rows=rows))
    pixels = np.tile(np.linspace(.15, .75, 64), (64, 1))
    for condition in CONDITIONS:
        Image.fromarray(np.uint8(np.clip(pixels + (0 if condition == "identity" else .1), 0, 1) * 255)).save(root / "previews" / f"{condition}.png")
    for sample, sampler, regime, family, method in itertools.product(samples, ("grid", "centers"), ("transfer", "transductive"), FAMILIES, ("fh4", "mws")):
        ident = f"fixture-{len(runs)}"
        n = len(sample["rows"][sampler])
        values = {}
        for condition in CONDITIONS:
            labels = ([1, 1, 2] if condition == "identity" else [4, 5, 6] if condition == "gain_minus" else [7, 7, 9])[:n]
            hard = ([True, False, True] if condition == "offset_minus" else [True] * 3)[:n]
            variants = {}
            for stage in STAGES:
                final = [label if stage != "A_updated_M1" or hard[i] else 0 for i, label in enumerate(labels)]
                variants[stage] = dict(labels=final, coverage=sum(x > 0 for x in final)/n if n else None, merge_rate=0 if n else None,
                    split_rate=0 if n else None, assigned=sum(x > 0 for x in final), domain_count=len(set(final)-{0}),
                    stability=assignment_stability(np.asarray([1, 1, 2][:n],int),np.asarray(final,int),np.asarray([[0, 1], [1, 2]] if n else [],int).reshape(-1,2),np.ones(n,bool)), assignment_changed=[x == 0 for x in final],
                    neighbor_relation_changed=([True, True, False] if condition == "gain_minus" else [False] * 3)[:n],
                    common_available=[True] * n)
            values[condition] = dict(before=labels, hard=hard, acf=[.6 if passed else .2 for passed in hard], ratio=[.5] * n, energy=[.1] * n,
                full_gate=hard, input_rmse=[0 if condition == "identity" else .1] * n,
                post_outside_fraction=[0.] * n, baseline_saturation_fraction=[0.] * n,
                feature_shift_native=[0.] * n, feature_shift_l2=[0.] * n, feature_shift_adapted=[0.] * n,
                preview_image=f"previews/{condition}.png" if n else None, variants=variants)
        payload = dict(id=ident, scope=[True] * n, available=[True] * n,
                       edges=[[0, 1], [1, 2]] if n else [], min_size=1,
                       threshold=.37948280732455153, preview_row_index=0 if n else None, conditions=values)
        relative = f"runs/{ident}.js"
        (root / relative).write_text("window.E3_RUN_DATA=" + json.dumps(payload) + ";\n")
        runs.append(dict(id=ident, sample_id=sample["id"], sampler=sampler, regime=regime, family=family,
                         seed=20261101 if family in FAMILIES[:4] else None, partition=method, path=relative))
    data = dict(samples=samples, runs=runs, conditions=list(CONDITIONS), variants=list(STAGES),
                gradient={key: {"value": .02} for key in ("transfer", "transductive")}, fixture=True)
    write_gallery(root / "index.html", data)
    return root / "index.html", len(samples), len(runs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, nargs="?")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--expected-samples", type=int, default=105)
    parser.add_argument("--expected-runs", type=int, default=12600)
    args = parser.parse_args()
    output = args.out.resolve()
    if (output / "browser-check.json").exists():
        raise FileExistsError("Preserve previous browser checks")
    output.mkdir(parents=True, exist_ok=True)
    if args.fixture:
        html, expected_samples, expected_runs = fixture(output / "fixture")
    else:
        if args.html is None or not args.html.is_file():
            raise FileNotFoundError(args.html)
        html, expected_samples, expected_runs = args.html.resolve(), args.expected_samples, args.expected_runs
    app = QApplication(["e3-gallery-check"])
    errors, checks, screenshots = [], [], []

    class Page(QWebEnginePage):
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
            raise RuntimeError("JavaScript callback timed out")
        return answer[0]

    def record(action, **expected):
        deadline, state = time.monotonic() + 20, None
        while time.monotonic() < deadline:
            wait()
            state = js("window.e3State||null")
            if errors or state and state.get("error"):
                raise AssertionError((errors, state))
            if state and state.get("ready") and all(state.get(key) == value for key, value in expected.items()):
                checks.append(dict(action=action, state=state))
                return state
        raise AssertionError((action, expected, state))

    def select(ident, value):
        name = f"document.getElementById({json.dumps(ident)})"
        event = "input" if ident == "frame" else "change"
        js(f"{name}.value={json.dumps(value)};{name}.dispatchEvent(new Event({json.dumps(event)}));")

    def click(ident):
        js(f"document.getElementById({json.dumps(ident)}).click()")

    def options(ident):
        return js(f"Array.from(document.getElementById({json.dumps(ident)}).options,o=>o.value)")

    def point_click(index, canvas="changed-canvas"):
        js(f"""(()=>{{const canvas=document.getElementById({json.dumps(canvas)}),rect=canvas.getBoundingClientRect(),p=currentRows[{index}].xy;
          canvas.dispatchEvent(new MouseEvent('click',{{bubbles:true,clientX:rect.left+p[0]*rect.width/currentImage.naturalWidth,
          clientY:rect.top+p[1]*rect.height/currentImage.naturalHeight}}));}})()""")

    def screenshot(name):
        wait(150)
        path = output / name
        if not view.grab().save(str(path)):
            raise RuntimeError("Screenshot failed")
        screenshots.append(str(path))

    failure, started = None, time.monotonic()
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        initial = record("initial", sample="ttmapp-259", sampler="centers", regime="transductive",
                         family="rvae_content", seed=20261101, partition="fh4", condition="offset_plus", variant="H_M1")
        assert initial["sample_count"] == expected_samples and initial["run_count"] == expected_runs
        assert "ten sam pełny obraz źródłowy" in js("document.body.textContent")
        samples = js("E3_DATA.samples.map(s=>({id:s.id,kind:s.kind,case:s.case||null}))")
        assert set(options("condition")) == set(CONDITIONS)
        assert set(options("variant")) == set(STAGES)
        screenshot("paired-ttmapp259.png")
        for condition in CONDITIONS:
            select("condition", condition)
            state = record("condition_" + condition, condition=condition)
            if condition == "identity":
                assert js("JSON.stringify(baseLabels)===JSON.stringify(changedLabels)")
                assert state["assignment_changed"] == state["neighbor_changed"] == 0
            for stage in STAGES:
                select("variant", stage)
                record("condition_stage", condition=condition, variant=stage)
        select("condition", "offset_plus")
        select("variant", "H_M1")
        record("restore_default", condition="offset_plus", variant="H_M1")
        if args.fixture:
            assert js("baseLabels.some((x,i)=>x!==changedLabels[i])")
            assert js("baseLabels.every((x,i)=>palette(baseLabels).get(x)===palette(changedLabels).get(changedLabels[i]))")
            assert js("e3State.assignment_changed===0&&e3State.neighbor_changed===0")
            record("renumbering_does_not_change_colors")
            select("condition", "offset_minus")
            select("variant", "A_fixed_M1")
            record("fixture_frozen_gate", changed_assigned=3, assignment_changed=0)
            select("variant", "A_updated_M1")
            record("fixture_updated_gate", changed_assigned=2, assignment_changed=1)
            point_click(1)
            detail = js("document.getElementById('detail').textContent")
            assert "po perturbacji" in detail and "Wejście64" in detail
            screenshot("frozen-versus-updated-gate.png")
            select("condition", "offset_plus")
            select("variant", "H_M1")
            click("preview-point")
            record("fixture_restore_preview", selected_point=initial["preview_row_index"])
        if initial["preview_row_index"] is not None:
            record("preview_ready", preview_visible=True, preview_ready=True)
            assert js("document.getElementById('base-preview').naturalWidth===64&&document.getElementById('changed-preview').naturalWidth===64")
            other = (initial["preview_row_index"] + 1) % initial["point_count"]
            point_click(other)
            record("other_point_hides_preview", selected_point=other, preview_visible=False)
            assert js("document.getElementById('preview-images').hidden")
            click("preview-point")
            record("preview_point_restored", selected_point=initial["preview_row_index"], preview_ready=True)
            js("document.getElementById('preview-images').scrollIntoView()")
            screenshot("point-measurements-preview.png")
            js("window.scrollTo(0,0)")
        for ident, state_key in (("points", "points"), ("highlight", "highlight"), ("before", "before")):
            click(ident)
            record("toggle_" + ident, **{state_key: ident == "before"})
            click(ident)
            record("restore_" + ident, **{state_key: ident != "before"})
        click("next")
        record("next", index=initial["index"] + 1)
        click("prev")
        record("previous", sample="ttmapp-259")
        for sampler in options("sampler"):
            select("sampler", sampler)
            record("sampler", sampler=sampler)
        for regime in options("regime"):
            select("regime", regime)
            record("regime", regime=regime)
            if regime == "transfer":
                assert js("baseLabels.every((x,i)=>currentRun.scope[i]||x===0)&&changedLabels.every((x,i)=>currentRun.scope[i]||x===0)")
        families = set()
        for value in options("model"):
            select("model", value)
            family, seed = json.loads(value)
            record("model", family=family, seed=seed)
            families.add(family)
        assert families == set(FAMILIES)
        for method in options("partition"):
            select("partition", method)
            record("solver", partition=method)
        select("sampler", "centers")
        record("restore_centers", sampler="centers")
        empty = next(sample for sample in samples if sample["case"] == "noise")
        select("sample", empty["id"])
        record("zero_centers", sample=empty["id"], point_count=0, base_assigned=0, changed_assigned=0,
               preview_row_index=None, preview_visible=False)
        click("changed-canvas")
        record("empty_click", selected_point=None)
        screenshot("noise-without-centers.png")
        for sample in samples:
            select("sample", sample["id"])
            record("load_sample", sample=sample["id"])
        select("frame", expected_samples - 1)
        record("slider_last", index=expected_samples - 1)
        assert js("document.getElementById('next').disabled")
        select("frame", 0)
        record("slider_first", index=0)
        assert js("document.getElementById('prev').disabled")
        select("sample", empty["id"])
        select("sample", "ttmapp-259")
        record("rapid_selection", sample="ttmapp-259")
        wait(300)
        record("rapid_selection_stays_current", sample="ttmapp-259")
        assert not errors
    except Exception as exc:
        failure = repr(exc)
    finally:
        report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                      fixture=args.fixture, expected_samples=expected_samples, expected_runs=expected_runs,
                      checks=checks, javascript_errors=errors, screenshots=screenshots, failure=failure,
                      wall_seconds=time.monotonic()-started)
        (output / "browser-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        view.close()
        app.processEvents()
    if failure:
        raise AssertionError(failure)
    print(json.dumps(dict(checks=len(checks), screenshots=len(screenshots), javascript_errors=len(errors),
                         fixture=args.fixture, wall_seconds=report["wall_seconds"])))


if __name__ == "__main__":
    main()
