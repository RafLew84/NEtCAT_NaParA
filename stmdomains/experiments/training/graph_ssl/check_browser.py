"""Drive the saved graph24 gallery; never runs an analysis or opens truth."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-dev-shm-usage --disable-software-rasterizer")

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    html,output=args.html.resolve(),args.out.resolve()
    output.mkdir(parents=True,exist_ok=True)
    started,wall=time.process_time(),time.monotonic()
    prior=sum(json.loads(p.read_text())["cpu_seconds"] for p in html.parent.glob("*resources.json"))
    index=1
    while (html.parent/f"browser-{index}.resources.json").exists():index+=1
    resource_path=html.parent/f"browser-{index}.resources.json"
    app=QApplication(["graph24-gallery-check"])
    errors,messages,checks,screenshots=[],[],[],[]
    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self,level,message,line,source):
            entry=dict(level=level.name,message=message,line=line,source=source)
            messages.append(entry)
            if level==QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:errors.append(entry)
    view=QWebEngineView();view.setPage(Page(view));view.resize(1480,1180);view.show()

    def wait(ms=100):
        loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
    def js(code):
        result=[];loop=QEventLoop()
        view.page().runJavaScript(code,lambda value:(result.append(value),loop.quit()))
        QTimer.singleShot(5000,loop.quit);loop.exec()
        if not result:raise RuntimeError("JavaScript callback timed out")
        return result[0]
    def record(action,expected):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            wait()
            state=js("window.galleryState||null")
            if state and state.get("ready") and all(state.get(k)==v for k,v in expected.items()):break
        else:raise AssertionError((action,expected,js("window.galleryState||null")))
        if errors:raise AssertionError(errors)
        for stage in ("before","after"):
            assert state[stage]["assigned"]<=state[stage]["denominator"]
        if state["legacy"]:assert state["before"]==state["after"]
        if prior+time.process_time()-started>7200:raise RuntimeError("CPU cap exceeded")
        checks.append(dict(action=action,state=state,notice=js("document.getElementById('notice').textContent")))
        return state
    def select(ident,value):
        el=f"document.getElementById({json.dumps(ident)})"
        event="input" if ident=="opacity" else "change"
        js(f"{el}.value={json.dumps(value)};{el}.dispatchEvent(new Event({json.dumps(event)}));")
    def click(ident):js(f"document.getElementById({json.dumps(ident)}).click()")
    def choices(ident):return js(f"Array.from(document.getElementById({json.dumps(ident)}).options).map(x=>x.value)")
    def screenshot(name):
        wait(200);path=output/name
        if not view.grab().save(str(path)):raise RuntimeError("Screenshot failed")
        screenshots.append(str(path))

    failure=None
    try:
        view.load(QUrl.fromLocalFile(str(html)))
        record("initial_load",dict(regime="transfer",family="geometry",method="fh4",heldout=False))
        payload=js("({samples:Object.fromEntries(Object.entries(DATA.samples).map(([k,v])=>[k,{case:v.case}])),runs:DATA.runs,scenarios:DATA.scenarios})")
        assert len(payload["samples"])==117
        assert len(payload["runs"])==19
        assert set(payload["scenarios"])=={"single","phase","missing","jitter","rows","ttmapp"}
        for regime in choices("regime"):
            select("regime",regime)
            for family in choices("family"):
                select("family",family)
                for seed in choices("seed"):
                    select("seed",seed)
                    for method in choices("partition"):
                        select("partition",method)
                        expected=dict(regime=regime,family=family,seed=None if seed=="none" else int(seed),method=method,heldout=False)
                        record("saved_variant_full",expected)
                        if regime=="transfer" and method in ("fh4","legacy15"):
                            click("heldout");record("saved_variant_test",expected|dict(heldout=True))
                            if family=="geometry":screenshot("ttmapp-geometry-test.png")
                            click("heldout");record("saved_variant_full_again",expected)
                        if regime=="transductive":assert js("document.getElementById('heldout').disabled") is True
        for name,scenario in payload["scenarios"].items():
            click("scenario-"+name)
            record("scenario_"+name,dict(sample=scenario["sample"],regime="transfer",family="graph_sce_scale",seed=20261101,method="fh4",heldout=False))
            if name in ("phase","missing","jitter"):screenshot(name+"-trained.png")
        click("scenario-ttmapp")
        record("ttmapp_for_context",dict(sample="ttmapp-250",family="graph_sce_scale",heldout=False))
        selected=js("(()=>{const s=DATA.samples[window.galleryState.sample],i=s.available.findIndex(Boolean),c=document.getElementById('after'),r=c.getBoundingClientRect(),p=s.xy[i];c.dispatchEvent(new MouseEvent('click',{clientX:r.left+p[0]/s.width*r.width,clientY:r.top+p[1]/s.height*r.height,bubbles:true}));return i;})()")
        record("clicked_actual_annotation",dict(contextIndex=selected))
        assert abs(js("(()=>{const b=DATA.samples[window.galleryState.sample].support[window.galleryState.contextIndex];return b[2]-b[0]})()")-72)<1e-8
        assert "oznaczeń w kontekście" in js("document.getElementById('context').textContent")
        screenshot("ttmapp-trained-context.png")
        click("clear-context");record("clear_context",dict(contextIndex=-1))
        for ident,family in (("step-geometry","geometry"),("step-untrained","graph_untrained"),("step-trained","graph_sce_scale"),("step-legacy","legacy15")):
            click(ident);record("walkthrough_"+ident,dict(family=family))
        click("points");record("hide_points",dict(points=False))
        click("points");record("show_points",dict(points=True))
        select("opacity","0.4");record("point_opacity",dict(opacity=.4))
        click("next");state=record("next_sample",{});assert state["sample"]!="ttmapp-250"
        click("previous");record("previous_sample",dict(sample="ttmapp-250"))
        noise=next(k for k,v in payload["samples"].items() if v["case"]=="noise")
        select("sample",noise);state=record("empty_annotation_input",dict(sample=noise))
        assert state["after"]["denominator"]==0 and state["after"]["coverage"] is None
        assert "Brak zapisanych oznaczeń" in js("document.getElementById('notice').textContent")
        assert len(screenshots)==5
        assert not errors
    except Exception as exc:
        failure=repr(exc)
    finally:
        report=dict(html=str(html),html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
            checks=checks,screenshots=screenshots,javascript_errors=errors,console_messages=messages,failure=failure)
        (output/"browser-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
        resource_path.write_text(json.dumps(dict(status="failed" if failure else "completed",
            cpu_seconds=time.process_time()-started,wall_seconds=time.monotonic()-wall,
            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,prior_cpu_seconds=prior),indent=2))
        view.close()
    if failure:raise AssertionError(failure)
    print(json.dumps(dict(interactions=len(checks),javascript_errors=len(errors),screenshots=len(screenshots))))


if __name__=="__main__":main()
