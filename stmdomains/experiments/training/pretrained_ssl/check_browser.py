"""Local visual QA of the saved issue26 gallery (no evaluation input access)."""

import argparse
import hashlib
import json
import os
import resource
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-dev-shm-usage --disable-software-rasterizer")

from .common import Budget

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    html, output = args.html.resolve(), args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    budget = Budget(html.parent)
    resource_path = html.parent / "browser.resources.json"
    if resource_path.exists() or (output / "browser-check.json").exists():
        raise FileExistsError("Preserve previous browser audit")
    app = QApplication(["issue26-gallery-check"])
    errors, messages, checks, screenshots = [], [], [], []

    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            record = dict(level=level.name, message=message, line=line, source=source)
            messages.append(record)
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(record)

    view = QWebEngineView()
    view.setPage(Page(view))
    view.resize(1400, 1250)
    view.show()

    def wait(milliseconds=120):
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

    def state_matches(expected):
        state = js("window.galleryState||null")
        return state if state and all(state.get(key) == value for key, value in expected.items()) else None

    def record(label, expected):
        budget.check()
        deadline = time.monotonic() + 20
        state = None
        while time.monotonic() < deadline:
            wait()
            state = state_matches(expected)
            if state:
                break
        if not state:
            raise AssertionError((label, expected, js("window.galleryState||null")))
        if errors:
            raise AssertionError(errors)
        checks.append(dict(action=label, state=state, notice=js("document.getElementById('notice').textContent")))
        return state

    def select(ident, value):
        code = f"document.getElementById({json.dumps(ident)})"
        js(f"{code}.value={json.dumps(value)};{code}.dispatchEvent(new Event({'change' if ident == 'regime' else 'input'!r}));")

    def click(ident):
        js(f"document.getElementById({json.dumps(ident)}).click()")

    def screenshot(name):
        wait(250)
        destination = output / name
        if not view.grab().save(str(destination)):
            raise RuntimeError(f"Cannot save screenshot: {destination}")
        screenshots.append(str(destination))

    failure = None
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        record("initial_load", {"method": "fh4", "heldout": False})
        payload = js("JSON.parse(document.getElementById('data').textContent)")
        expected_counts = {regime: sum(r["regime"] == regime for r in payload["runs"]) for regime in ("transfer", "transductive")}
        primary_run = next((r for r in sorted(r["run_id"] for r in payload["runs"]) if r.startswith("transfer/dino_adapted/")), "transfer/dino_frozen")
        scenario_map = js("JSON.parse(document.getElementById('data').textContent).scenarios")
        assert set(scenario_map) == {"single", "boundary", "phase", "orientation8", "missing", "artifact", "ttmapp"}, scenario_map
        select("run", "transfer/fft")
        click("scenario-ttmapp")
        record("ttmapp_fft_full", {"sample":scenario_map["ttmapp"], "run":"transfer/fft", "heldout":False})
        click("heldout")
        record("ttmapp_fft_heldout", {"sample":scenario_map["ttmapp"], "heldout":True})
        screenshot("ttmapp-transfer-fft-heldout.png")
        click("heldout")
        record("ttmapp_fft_full_again", {"heldout":False})
        regimes = js("Array.from(document.getElementById('regime').options).map(o=>o.value)")
        assert regimes == ["transfer", "transductive"]
        counts={}
        for regime in regimes:
            select("regime",regime)
            run_ids=js("Array.from(document.getElementById('run').options).map(o=>o.value)")
            counts[regime]=len(run_ids)
            assert {"fft", "dino_frozen"} <= {run.split("/")[1] for run in run_ids} <= {"fft", "dino_frozen", "dino_adapted"}
            click("scenario-ttmapp")
            for run_id in run_ids:
                select("run",run_id)
                for partition in ('fh4','mws'):
                    select("partition",partition)
                    state=record("all_models_full", {"sample":scenario_map["ttmapp"], "run":run_id,"method":partition,"heldout":False})
                    assert state['after']['assigned'] <= state['after']['denominator']
                    if regime=='transfer':
                        click("heldout")
                        record("all_models_heldout", {"run":run_id,"method":partition,"heldout":True})
                        click("heldout")
                        record("all_models_back_to_full", {"run":run_id,"method":partition,"heldout":False})
                    else:
                        assert js("document.getElementById('heldout').disabled") is True
        assert counts == expected_counts,counts
        select("regime","transfer")
        select("run",primary_run)
        select("partition","fh4")
        for name,sample in scenario_map.items():
            click("scenario-"+name)
            record("scenario_"+name, {"sample":sample,"run":primary_run,"method":"fh4","heldout":False})
            if name in ('phase','missing','ttmapp'):
                screenshot(name+"-transfer-dino-fh4.png")
        click("points")
        wait()
        assert js("document.getElementById('points').checked") is False
        click("points")
        select("opacity","0.5")
        wait()
        assert js("document.getElementById('points').checked") is True
        select("opacity","0.9")
        click("scenario-ttmapp")
        previous_sample=js("window.galleryState.sample")
        click("next")
        wait()
        moved_sample=js("window.galleryState.sample")
        assert moved_sample!=previous_sample
        record("next_sample",{"sample":moved_sample})
        click("previous")
        record("previous_sample",{"sample":previous_sample})
        figure_count = js("document.querySelectorAll('details').length")
        assert figure_count >= 2
        for index in range(figure_count):
            js(f"document.querySelectorAll('details')[{index}].open=true;document.querySelectorAll('details')[{index}].scrollIntoView()")
            wait(250)
            assert js(f"document.querySelectorAll('details')[{index}].querySelector('img').naturalWidth")>100
            checks.append(dict(action="scientific_figure_open",index=index))
            if index==0:screenshot("adaptation-figure.png")
            js(f"document.querySelectorAll('details')[{index}].open=false")
        assert not errors, errors
    except Exception as exception:
        failure = repr(exception)
    finally:
        report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                      checks=checks, screenshots=screenshots, javascript_errors=errors,
                      console_messages=messages, failure=failure)
        (output / "browser-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        view.close()
        resource_path.write_text(json.dumps(dict(status="failed" if failure else "completed", **budget.measurements()), indent=2))
    if failure:
        raise AssertionError(failure)
    print(json.dumps(dict(interactions=len(checks), javascript_errors=len(errors), screenshots=len(screenshots),
                          report=str(output / "browser-check.json"))))


if __name__ == "__main__":
    main()
