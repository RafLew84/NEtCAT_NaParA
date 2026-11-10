"""Check a prepared E0 HTML in netcat QtWebEngine without running any model."""

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
    parser.add_argument("--uncertain-id", help="ID of the ambiguous two-row example")
    args = parser.parse_args()
    html, output = args.html.resolve(), args.out.resolve()
    if not html.is_file():
        raise FileNotFoundError(html)
    if (output / "browser-check.json").exists():
        raise FileExistsError("Preserve the previous browser check")
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication(["e0-gallery-check"])
    errors, checks, screenshots = [], [], []

    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(dict(message=message, line=line, source=source))

    view = QWebEngineView()
    view.setPage(Page(view))
    view.resize(1360, 1200)
    view.show()

    def wait(milliseconds=100):
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
        deadline, state = time.monotonic() + 15, None
        while time.monotonic() < deadline:
            wait()
            state = js("window.e0State||null")
            if errors:
                raise AssertionError(errors)
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

    def screenshot(name):
        wait(200)
        path = output / name
        if not view.grab().save(str(path)):
            raise RuntimeError("Screenshot failed")
        screenshots.append(str(path))

    failure = None
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        initial = record("initial", sample="ttmapp-259", points=True, overlay=True, rois=True)
        payload = js("DATA.map(s=>({id:s.id,kind:s.kind,note:s.note,points:s.xy.length,labels:s.point_labels.length}))")
        assert all(s["points"] == s["labels"] for s in payload)
        assert {s["kind"] for s in payload} == {"measurement", "synthetic"}
        screenshot("ttmapp-259.png")
        select("frame", 0)
        record("slider_first", index=0, sample=payload[0]["id"])
        click("next")
        record("next", index=1, sample=payload[1]["id"])
        click("prev")
        record("prev", index=0)
        select("frame", len(payload) - 1)
        record("slider_last", index=len(payload) - 1)
        assert js("document.getElementById('next').disabled")
        select("sample", initial["index"])
        record("select_259", sample="ttmapp-259")
        for layer in ("points", "overlay", "rois"):
            click(layer)
            record("hide_" + layer, **{layer: False})
            click(layer)
            record("show_" + layer, **{layer: True})
        uncertain = args.uncertain_id
        if uncertain is None:
            candidates = [s["id"] for s in payload if "2rows" in s["id"] or "two_rows" in s["id"] or "two-rows" in s["id"]]
            if len(candidates) != 1:
                raise ValueError("Specify --uncertain-id to identify the ambiguous example")
            uncertain = candidates[0]
        uncertain_index = next(i for i, sample in enumerate(payload) if sample["id"] == uncertain)
        select("sample", uncertain_index)
        record("uncertain_two_rows", sample=uncertain)
        notice = js("document.getElementById('notice').textContent").lower()
        assert any(word in notice for word in ("niejednoznacz", "nierozstrzyg", "niepewn", "brak danych"))
        screenshot("two-rows.png")
        assert js("document.getElementById('canvas').width>0") and not errors
    except Exception as exc:
        failure = repr(exc)
    finally:
        report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                      checks=checks, screenshots=screenshots, javascript_errors=errors, failure=failure)
        (output / "browser-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        view.close()
        app.processEvents()
    if failure:
        raise AssertionError(failure)
    print(json.dumps(dict(checks=len(checks), screenshots=len(screenshots), javascript_errors=len(errors))))


if __name__ == "__main__":
    main()
