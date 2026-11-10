"""Exercise the prepared E2 offline viewer in QtWebEngine; never run a model."""

from __future__ import annotations

import argparse
import hashlib
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-samples", type=int, default=105)
    parser.add_argument("--expected-runs", type=int, default=25200)
    parser.add_argument("--check-plots", action="store_true")
    args = parser.parse_args()
    html, output = args.html.resolve(), args.out.resolve()
    if not html.is_file():
        raise FileNotFoundError(html)
    if (output / "browser-check.json").exists():
        raise FileExistsError("Preserve the previous browser check")
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication(["e2-gallery-check"])
    errors, checks, screenshots = [], [], []

    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(dict(message=message, line=line, source=source))

    view = QWebEngineView()
    view.setPage(Page(view))
    view.resize(1400, 1300)
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

    def record(action, *, state_name="e2State", **expected):
        deadline, state = time.monotonic() + 20, None
        while time.monotonic() < deadline:
            wait()
            state = js(f"window.{state_name}||null")
            if errors or state and state.get("error"):
                raise AssertionError((errors, state))
            if state and state.get("ready") and all(state.get(k) == v for k, v in expected.items()):
                break
        else:
            raise AssertionError((action, expected, state))
        checks.append(dict(action=action, state=state))
        return state

    def select(ident, value):
        element = f"document.getElementById({json.dumps(ident)})"
        event = "input" if ident == "frame" else "change"
        js(f"{element}.value={json.dumps(value)};{element}.dispatchEvent(new Event({json.dumps(event)}));")

    def click(ident):
        js(f"document.getElementById({json.dumps(ident)}).click()")

    def option_values(ident):
        return js(f"Array.from(document.getElementById({json.dumps(ident)}).options,o=>o.value)")

    def point_click(index):
        js(f"""(()=>{{const canvas=document.getElementById('canvas'),rect=canvas.getBoundingClientRect();
          const p=currentRows[{index}].xy;
          canvas.dispatchEvent(new MouseEvent('click',{{bubbles:true,
            clientX:rect.left+p[0]*rect.width/currentImage.naturalWidth,
            clientY:rect.top+p[1]*rect.height/currentImage.naturalHeight}}));}})()""")

    def screenshot(name):
        wait(150)
        path = output / name
        if not view.grab().save(str(path)):
            raise RuntimeError("Screenshot failed")
        screenshots.append(str(path))

    failure = None
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        initial = record("initial", sample="ttmapp-259", sampler="centers", regime="transductive",
                         family="rvae_content", seed=20261101, partition="fh4", variant="H_M1",
                         condition="actual", before=False)
        samples = js("E1_DATA.samples.map(s=>({id:s.id,kind:s.kind,case:s.case||null}))")
        assert len(samples) == args.expected_samples, (len(samples), args.expected_samples)
        assert initial["sample_count"] == len(samples)
        assert initial["run_count"] == args.expected_runs
        assert js("document.getElementById('canvas').width>0")
        assert js("document.querySelector('a[href=\"plots.html\"]')!==null")
        assert "bez bloku kąta" in js("document.getElementById('notice').textContent")
        assert "Wspólna dostępność odczytów (common)" in js("document.getElementById('edge-summary').textContent")
        screenshot("ttmapp-259-centers.png")
        click("next")
        record("next", index=initial["index"] + 1)
        click("prev")
        record("previous", sample="ttmapp-259")
        click("before")
        record("before_program_relations", before=True)
        assert "relacje programu" in js("document.getElementById('status').textContent")
        click("before")
        record("after", before=False)
        click("points")
        record("hide_points", points=False)
        click("points")
        record("show_points", points=True)

        select("sampler", "grid")
        record("grid", sampler="grid")
        assert "nie wykrytymi molekułami" in js("document.getElementById('notice').textContent")
        select("sampler", "centers")
        record("centers", sampler="centers")
        for value in option_values("regime"):
            select("regime", value)
            record("regime_" + value, regime=value)
            if value == "transfer":
                assert "historyczny transfer" in js("document.getElementById('notice').textContent")
                assert js("!currentRun.scope||currentLabels.every((x,i)=>currentRun.scope[i]||x===0)")
        conditions = option_values("condition")
        assert set(conditions) == {"actual", "shuffle-20261110"}, conditions
        for value in conditions:
            select("condition", value)
            record("condition_" + value, condition=value)
            if value != "actual":
                assert "TASOWANIE" in js("document.getElementById('notice').textContent")
        select("condition", "actual")
        record("actual", condition="actual")
        families = set()
        for value in option_values("model"):
            select("model", value)
            family, seed = json.loads(value)
            record("model", family=family, seed=seed)
            families.add(family)
            if family in {"rvae_angle", "rvae_full"}:
                assert "nie jest zwalidowanym" in js("document.getElementById('notice').textContent") or "nie zwalidowany" in js("document.getElementById('notice').textContent")
            for condition in conditions:
                select("condition", condition)
                record("model_condition", family=family, seed=seed, condition=condition)
        assert families == {"ae", "rvae_full", "rvae_content", "rvae_angle", "fft", "photometry", "geometry"}, families
        select("condition", "actual")
        record("restore_actual", condition="actual")
        for value in option_values("partition"):
            select("partition", value)
            record("partition_" + value, partition=value)
        for value in option_values("variant"):
            select("variant", value)
            record("measurement_variant_" + value, variant=value)
        select("model", json.dumps(["rvae_content", 20261101], separators=(",", ":")))
        record("content_readout", family="rvae_content", seed=20261101)
        select("variant", "H_M0")
        record("disabled_gates", variant="H_M0")
        point = js("currentRun.gate_failures.acf_below_threshold.findIndex(Boolean)")
        assert point >= 0, "Expected a stored failed ACF measurement for the disabled-gate check"
        point_click(point)
        record("disabled_gate_point", selected_point=point)
        flag_row = "Array.from(document.querySelectorAll('#detail tr')).find(r=>r.cells[0]?.textContent==='Próg ACF')"
        assert js(f"(()=>{{const r={flag_row};return r.cells[1].textContent==='niespełniony'&&r.cells[2].textContent==='wyłączona';}})()")
        screenshot("ttmapp-disabled-gate-point.png")
        select("variant", "A1S1M1")
        record("active_gates", variant="A1S1M1", selected_point=point)
        assert js(f"({flag_row}).cells[2].textContent==='aktywna'")

        synthetic = next(s for s in samples if s["kind"] == "synthetic" and s["case"] == "two_orientations")
        select("sample", synthetic["id"])
        record("synthetic", sample=synthetic["id"])
        variants = option_values("variant")
        assert set(variants) == {"H_M0", "H_M1", "A1S1M0", "A1S1M1"}, variants
        for value in variants:
            select("variant", value)
            record("synthetic_variant_" + value, variant=value)
        select("variant", "H_M1")
        state = record("synthetic_diagnostic", variant="H_M1")
        assert "H: twarde wymagania" in js("document.getElementById('notice').textContent")
        assert state["point_count"] > 0
        point = js("Math.max(0,currentRows.findIndex((r,i)=>r.available&&currentRun.scope?.[i]!==false))")
        point_click(point)
        record("point_details", selected_point=point)
        detail = js("document.getElementById('detail').textContent")
        assert all(term in detail for term in ("ACF", "Energia", "Zapisane flagi", "Pozycja raw"))
        assert js("!document.getElementById('edge-summary').textContent.includes('undefined')")
        screenshot("synthetic-content-point.png")
        js("document.getElementById('edge-summary').scrollIntoView()")
        screenshot("synthetic-edge-summary.png")
        js("window.scrollTo(0,0)")
        click("before")
        record("synthetic_before", before=True)
        assert "relacje programu" in js("document.getElementById('status').textContent")
        click("before")
        record("synthetic_after", before=False)

        empty = next(s for s in samples if s["kind"] == "synthetic" and s["case"] == "noise")
        select("sample", empty["id"])
        record("no_supported_centers", sample=empty["id"], sampler="centers", assigned_count=0)
        assert js("currentRows.every(row=>!row.available)")
        # Empty and fully unsupported point sets must both keep the image usable.
        click("canvas")
        record("empty_or_unsupported_click", sample=empty["id"], assigned_count=0)
        screenshot("noise-without-supported-centers.png")

        for sample in samples:
            select("sample", sample["id"])
            record("load_sample", sample=sample["id"])
        select("frame", len(samples) - 1)
        record("slider_last", index=len(samples) - 1)
        assert js("document.getElementById('next').disabled")
        select("frame", 0)
        record("slider_first", index=0)
        assert js("document.getElementById('prev').disabled")
        # Rapid changes must not let a late script replace the currently selected run.
        select("sample", synthetic["id"])
        select("sample", "ttmapp-259")
        record("rapid_selection", sample="ttmapp-259")
        wait(400)
        record("rapid_selection_stays_current", sample="ttmapp-259")
        if args.check_plots:
            plot_html = html.parent / "plots.html"
            assert plot_html.is_file()
            view.load(QUrl.fromLocalFile(str(plot_html)))
            record("plots_initial", state_name="e2PlotsState", count=112, kind="curves",
                   case="measurement", regime="transductive", sampler="centers", space="adapted")
            figures = js("DATA.figures")
            assert len(figures) == 112
            screenshot("plots-roc-pr.png")
            for figure in figures:
                for key in ("kind", "case", "regime", "sampler", "space"):
                    select(key, figure[key])
                record("load_plot", state_name="e2PlotsState", id=figure["id"])
                assert js("document.getElementById('figure').naturalWidth>0")
                assert js("document.getElementById('svg').getAttribute('href')") == figure["svg"]
                assert (html.parent / figure["svg"]).is_file()
            screenshot("plots-distance-quantiles.png")
        assert not errors
    except Exception as exc:
        failure = repr(exc)
    finally:
        report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                      expected_sample_count=args.expected_samples, expected_run_count=args.expected_runs,
                      plots_checked=args.check_plots, checks=checks,
                      screenshots=screenshots, javascript_errors=errors, failure=failure)
        (output / "browser-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        view.close()
        app.processEvents()
    if failure:
        raise AssertionError(failure)
    print(json.dumps(dict(checks=len(checks), screenshots=len(screenshots), javascript_errors=len(errors))))


if __name__ == "__main__":
    main()
