"""Exercise the saved24a gallery in QtWebEngine; no inference or truth access."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-dev-shm-usage --disable-software-rasterizer")

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

from ...bundle import file_hash, write_json
from .evaluation import Budget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    html, output = args.html.resolve(), args.out.resolve()
    resource_path = html.parent / "browser.resources.json"
    if resource_path.exists() or (output / "browser-check.json").exists():
        raise FileExistsError("Preserve the previous browser audit")
    output.mkdir(parents=True, exist_ok=True)
    budget = Budget(html.parent)
    app = QApplication(["graph24a-gallery-check"])
    errors, messages, checks, screenshots = [], [], [], []

    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            entry = dict(level=level.name, message=message, line=line, source=source)
            messages.append(entry)
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(entry)

    view = QWebEngineView()
    view.setPage(Page(view))
    view.resize(1480, 1180)
    view.show()

    def wait(ms=100):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def js(code):
        result, loop = [], QEventLoop()
        view.page().runJavaScript(code, lambda value: (result.append(value), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        if not result:
            raise RuntimeError("JavaScript callback timed out")
        return result[0]

    def record(action, expected):
        for _ in range(200):
            wait()
            budget.check()
            state = js("window.galleryState||null")
            if state and state.get("ready") and all(state.get(k) == v for k, v in expected.items()):
                break
        else:
            raise AssertionError((action, expected, state))
        if errors:
            raise AssertionError(errors)
        denominators = set()
        for side in ("left", "right"):
            for stage in ("before", "after"):
                counts = state["all_stages"][side][stage]
                assert counts["assigned"] <= counts["denominator"]
                denominators.add(counts["denominator"])
        assert len(denominators) == 1
        if state["family"] == "geometry":
            assert state["all_stages"]["left"] == state["all_stages"]["right"]
        checks.append(dict(action=action, state=state, notice=js("document.getElementById('notice').textContent")))
        return state

    def select(ident, value):
        element = f"document.getElementById({json.dumps(ident)})"
        event = "input" if ident == "opacity" else "change"
        js(f"{element}.value={json.dumps(value)};{element}.dispatchEvent(new Event({json.dumps(event)}));")

    def click(ident):
        js(f"document.getElementById({json.dumps(ident)}).click()")

    def choices(ident):
        return js(f"Array.from(document.getElementById({json.dumps(ident)}).options).map(x=>x.value)")

    def screenshot(name):
        wait(200)
        path = output / name
        if not view.grab().save(str(path)):
            raise RuntimeError("Screenshot failed")
        screenshots.append(str(path))

    failure = None
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        record("initial_load", dict(family="graph_sce_scale", seed=20261101, mode="halfopen72", stage="after"))
        payload = js("({samples:Object.fromEntries(Object.entries(DATA.samples).map(([k,v])=>[k,{case:v.case}])),runs:DATA.runs,scenarios:DATA.scenarios})")
        assert len(payload["samples"]) == 93 and len(payload["runs"]) == 19
        assert set(payload["scenarios"]) == {"single", "orientation8", "phase", "phasejitter", "rows"}
        for family in choices("family"):
            select("family", family)
            for seed in choices("seed"):
                select("seed", seed)
                for mode in (["root57"] if family == "geometry" else choices("mode")):
                    if mode != "root57":
                        select("mode", mode)
                    for method in choices("partition"):
                        select("partition", method)
                        record("saved_pair", dict(family=family, seed=None if seed == "none" else int(seed),
                            mode=mode, method=method, stage="after"))
        for name, scenario in payload["scenarios"].items():
            click("scenario-" + name)
            record("scenario_" + name, dict(sample=scenario["sample"], family="graph_sce_scale",
                seed=20261101, mode="halfopen72", method="fh4", stage="after"))
            if name in ("single", "phasejitter"):
                screenshot(name + "-halfopen.png")
        click("scenario-single")
        record("single_for_ablation", dict(sample=payload["scenarios"]["single"]["sample"], mode="halfopen72"))
        select("mode", "root_only")
        record("root_only_notice", dict(mode="root_only"))
        assert "nie naprawiony" in js("document.getElementById('notice').textContent")
        screenshot("single-root-only.png")
        click("after")
        record("before_refusals", dict(stage="before"))
        click("after")
        record("after_refusals", dict(stage="after"))
        click("points")
        record("hide_points", dict(points=False))
        click("points")
        record("show_points", dict(points=True))
        select("opacity", "0.4")
        record("point_opacity", dict(opacity=.4))
        selected = js("(()=>{const s=DATA.samples[window.galleryState.sample],i=s.available.findIndex(Boolean),c=document.getElementById('right'),r=c.getBoundingClientRect(),p=s.xy[i];c.dispatchEvent(new MouseEvent('click',{clientX:r.left+p[0]/s.width*r.width,clientY:r.top+p[1]/s.height*r.height,bubbles:true}));return i;})()")
        assert selected >= 0
        record("actual_center_context", dict(contextIndex=selected))
        assert "S24" in js("document.getElementById('context').textContent")
        assert len(screenshots) == 3 and not errors
    except Exception as exc:
        failure = repr(exc)
    finally:
        write_json(output / "browser-check.json", dict(html=str(html), html_sha256=file_hash(html),
            checks=checks, screenshots=screenshots, javascript_errors=errors, console_messages=messages, failure=failure))
        write_json(resource_path, dict(status="failed" if failure else "completed", **budget.measurements()))
        view.close()
    if failure:
        raise AssertionError(failure)
    print(json.dumps(dict(checks=len(checks), javascript_errors=len(errors), screenshots=len(screenshots))))


if __name__ == "__main__":
    main()
