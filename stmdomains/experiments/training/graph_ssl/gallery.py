"""Self-contained post-freeze viewer of saved graph24 centre assignments.

The gallery does no inference. Circles are actual input annotation centres;
hover/click reveals the bounded context used by the graph encoder.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import resource
import time

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from ..gallery import _display_png


FAMILY_LABELS = {
    "geometry": "Cechy geometrii bez uczenia",
    "graph_untrained": "Graf — przed uczeniem",
    "graph_sce_scale": "Graf — po uczeniu, kształt i odległości",
    "graph_sce": "Graf — po uczeniu, sam kierunek cech",
    "legacy15": "Zachowana procedura geometryczna 15",
}
CASE_LABELS = {
    "single": "Jedna pełna sieć", "two_orientations": "Dwie orientacje",
    "orientation_8deg": "Mała różnica orientacji: 8°", "different_spacing": "Różne rozstawy",
    "phase_boundary": "Granica przesunięcia", "disjoint": "Rozłączne płaty",
    "empty_gap": "Pusta przerwa", "missing_10": "Brak 10% oznaczeń",
    "missing_30": "Brak 30% oznaczeń", "missing_50": "Brak 50% oznaczeń",
    "missing_band": "Brak oznaczeń w pasie", "missing_local": "Lokalny brak oznaczeń",
    "noise": "Szum — brak oznaczeń", "stripes": "Paski — brak oznaczeń",
    "random": "Losowe pozycje", "random_gradient": "Losowe pozycje i gradient",
    "random_minsep": "Losowe pozycje z minimalnym odstępem", "independent_rows": "Niezależne rzędy",
    "insufficient_field": "Niedostateczne pole", "single_defect": "Pojedynczy defekt",
    "inverted": "Odwrócony kontrast", "contrast": "Zmieniony kontrast", "crop": "Ucięte pole",
    "disordered_band": "Pas nieuporządkowania", "larger_spacing": "Większy rozstaw",
    "oblique": "Sieć ukośna", "resample_2x": "Techniczny resampling ×2",
    "centers_jitter_036": "Błąd pozycji centrów: 0,36 px",
    "centers_jitter_072": "Błąd pozycji centrów: 0,72 px",
    "centers_duplicates_10": "Duplikaty oznaczeń: 10%",
    "phase_centers_jitter_072": "Granica przesunięcia i błąd centrów",
}
SCENARIOS = {
    "single": ("single", "Pełna sieć", "Jedna regularna sieć powinna pozostać jedną domeną. Porównaj wpływ samej architektury i uczenia."),
    "phase": ("phase_boundary", "Przesunięcie", "Obie części mają tę samą orientację, lecz wzór nie łączy się spójnie. Sam podobny wygląd otoczeń nie wystarcza."),
    "missing": ("missing_band", "Braki oznaczeń", "Obraz zachowuje molekuły, lecz zapisane centra znikają w pasie. Rozłączenie grafu nie dowodzi przerwy materiału."),
    "jitter": ("phase_centers_jitter_072", "Błędy centrów", "Sprawdź, czy niewielki błąd położenia oznaczeń zmienia podział przy granicy przesunięcia."),
    "rows": ("independent_rows", "Niezależne rzędy", "Regularność pojedynczych rzędów nie potwierdza wspólnej sieci dwuwymiarowej."),
    "ttmapp": (None, "TTMAPP", "Punkty pokazują wejściowe oznaczenia molekuł. W transferze pełne pole jest kontekstem; ocena korzysta z osobnego grafu części testowej."),
}


def read(path):
    return json.loads(Path(path).read_text())


def build(output, evaluation=None, controls_evaluation=None):
    root = Path(output).resolve()
    freeze_path = root / "frozen-predictions.json"
    evidence_path = Path(evaluation or root / "evaluation") / "evaluation-evidence.json"
    if not freeze_path.exists() or not evidence_path.exists():
        raise ValueError("Graph gallery requires frozen predictions and completed evaluation")
    frozen, evidence = read(freeze_path), read(evidence_path)
    if evidence["frozen_manifest_sha256"] != file_hash(freeze_path):
        raise ValueError("Evaluation refers to another prediction freeze")
    # Control names and generator seeds are deliberately absent from analysis
    # inputs. Read only their display metadata after the prediction/evaluation
    # audit; do not open the truth arrays or compute any new scientific result.
    control_manifest_path = Path(controls_evaluation or root / "controls/evaluation") / "manifest.json"
    if file_hash(control_manifest_path) != evidence["controls_manifest_sha256"]:
        raise ValueError("Gallery control names differ from the completed evaluation")
    control_metadata = {row["sample_id"]: row for row in read(control_manifest_path)["controls"]}
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    prior = sum(read(p)["cpu_seconds"] for p in root.glob("*resources.json"))
    checked = {}

    def check_budget():
        if prior + time.process_time() - cpu_start > 7200:
            raise RuntimeError("Graph24 postprocessing CPU cap exceeded")
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > 12 * 1024**3:
            raise MemoryError("Graph24 postprocessing RSS cap exceeded")

    def pinned(relative):
        check_budget()
        path = root / relative
        actual = file_hash(path)
        if frozen["files"].get(relative) != actual:
            raise ValueError("Changed or unpinned gallery input: " + relative)
        checked[relative] = actual
        return path

    index = read(pinned("predictions/index.json"))
    if isinstance(index, dict):
        index = index["entries"]
    prepared = read(pinned("prepared/manifest.json"))
    gallery = root / "gallery"
    gallery.mkdir(exist_ok=True)
    samples = {}
    for item in prepared["samples"]:
        record, arrays = load_sample(Path(item["source_analysis"]), item["sample_id"])
        rows = read(pinned("prepared/" + item["rows_file"]))
        png, display = _display_png(arrays)
        control = control_metadata.get(item["sample_id"], {})
        if record["kind"] == "synthetic" and not control:
            raise ValueError("Missing evaluated control display metadata")
        case, control_seed = control.get("case"), control.get("seed")
        frame = record.get("frame_number")
        name = (f"TTMAPP · klatka {frame}" if record["kind"] == "measurement" else
                f"{CASE_LABELS.get(case, case or item['sample_id'])} · ziarno {control_seed}")
        samples[item["sample_id"]] = dict(
            id=item["sample_id"], label=name, kind=record["kind"], case=case,
            frame=frame, control_seed=control_seed,
            width=int(arrays["image"].shape[1]), height=int(arrays["image"].shape[0]),
            image="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
            image_content_sha256=record["content_sha256"], display=display,
            ids=[r["element_id"] for r in rows], xy=[r["raw_edge_xy"] for r in rows],
            support=[r["support_xyxy"] for r in rows],
            available=[bool(r["available"]) for r in rows],
            test=[r.get("transfer_split") == "test" for r in rows],
            node_count=[r["observed_ego_nodes"] for r in rows],
            unavailable_reason=[r.get("unavailable_reason") for r in rows])
    runs, predictions = {}, []
    for entry in index:
        sample = samples[entry["sample_id"]]
        result = {name: entry.get(name) for name in
                  ("sample_id", "variant_id", "family", "regime", "seed", "partition")}
        for field, label in (("file", "full"), ("heldout_file", "heldout")):
            if field not in entry:
                result[label] = None
                continue
            with np.load(pinned(entry[field]), allow_pickle=False) as archive:
                before, after, states = archive["before"], archive["after"], archive["states"]
            if any(a.shape != (len(sample["ids"]),) for a in (before, after, states)):
                raise ValueError("Saved predictions do not align with input centres")
            scope = states != "not_evaluated"
            if np.any((before > 0) & ~scope) or np.any((after > 0) & ~scope):
                raise ValueError("Assigned labels outside saved scope")
            result[label] = dict(before=before.astype(int).tolist(), after=after.astype(int).tolist(),
                                 scope=scope.tolist())
        runs[entry["variant_id"]] = {name: entry.get(name) for name in
                                     ("variant_id", "family", "regime", "seed")}
        predictions.append(result)
    scenarios = {}
    for scenario, (case, label, explanation) in SCENARIOS.items():
        if scenario == "ttmapp":
            selected = "ttmapp-250"
        else:
            matches = [s for s in samples.values() if s["case"] == case]
            if not matches:
                raise ValueError("Missing fixed gallery scenario: " + case)
            selected = min(matches, key=lambda s: (s["control_seed"], s["id"]))["id"]
        if selected not in samples:
            raise ValueError("Missing TTMAPP scenario")
        scenarios[scenario] = dict(sample=selected, label=label, explanation=explanation)
    sample_order = sorted(samples, key=lambda sid: (samples[sid]["kind"] != "measurement",
        samples[sid]["frame"] or 0, samples[sid]["case"] or "", samples[sid]["control_seed"] or 0))
    payload = dict(schema="stmdomains-graph24-gallery-v1", samples=samples, sample_order=sample_order,
                   runs=list(runs.values()), predictions=predictions, scenarios=scenarios,
                   family_labels=FAMILY_LABELS, freeze_sha256=file_hash(freeze_path))
    document = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    target = root / "index.html"
    if target.exists():
        raise FileExistsError("Gallery already exists; preserve the previous exported artifact")
    target.write_text(document)
    manifest = dict(schema="stmdomains-graph24-gallery-manifest-v1", html=str(target),
        html_bytes=target.stat().st_size, html_sha256=file_hash(target), source_sha256=file_hash(Path(__file__)),
        display_source_sha256=file_hash(Path(__file__).parent.parent / "gallery.py"),
        samples=len(samples), variants=len(runs), predictions=len(predictions),
        feature_variants=sum(r["family"] != "legacy15" for r in runs.values()),
        legacy_variants=sum(r["family"] == "legacy15" for r in runs.values()),
        scenarios=scenarios, frozen_manifest_sha256=file_hash(freeze_path),
        evaluation_evidence_sha256=file_hash(evidence_path), checked_input_sha256=checked,
        control_display_manifest_sha256=file_hash(control_manifest_path),
        interpretation="Actual annotation centres; assignment proportions, not molecule detection or material area. Legacy15 has no separate before-refusal result.")
    write_json(gallery / "manifest.json", manifest)
    check_budget()
    write_json(root / "gallery.resources.json", dict(status="completed", cpu_seconds=time.process_time() - cpu_start,
        wall_seconds=time.perf_counter() - wall_start, max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        prior_cpu_seconds=prior))
    return manifest


HTML = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>STM Domains — grafy otoczeń molekuł</title>
<style>
:root{color-scheme:dark;--bg:#10151d;--panel:#17212d;--text:#e8eef7;--muted:#a4b3c8;--accent:#8ce7d3;--line:#34475f}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,sans-serif}main{max-width:1520px;margin:auto;padding:26px 30px}h1{font-size:27px;margin:0 0 7px}h2{font-size:17px;margin:0}.eyebrow{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:.08em}.intro{max-width:1100px;margin:8px 0 20px;color:var(--muted)}.selectors{display:grid;grid-template-columns:1.2fr 2fr .9fr 1.1fr 2fr;gap:12px}label{color:var(--muted);font-size:12px}select,button,input{font:inherit}select,button{border:1px solid #435873;border-radius:6px;background:#202d3d;color:var(--text);padding:9px 10px}select{width:100%;display:block;margin-top:5px}button{cursor:pointer}button:hover,button.active{border-color:var(--accent)}button.active{background:#203d43}button:disabled{opacity:.5;cursor:default}.toolbar,.scenarios,.steps{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}.toolbar label{display:flex;align-items:center;gap:6px}input[type=range]{accent-color:var(--accent);width:120px}input[type=checkbox]{accent-color:var(--accent)}.walkthrough{background:#17242f;border:1px solid var(--line);border-radius:7px;margin-top:16px;padding:12px 16px}.walkthrough p{margin:0}.steps button{padding:6px 10px;font-size:12px}.notice{margin:14px 0;border-left:3px solid #e8be65;background:#302b21;padding:11px 14px;color:#f4d595}.panels{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}.panelhead{padding:12px 16px;display:flex;justify-content:space-between;align-items:center}.panelhead small{color:var(--muted)}.canvaswrap{padding:8px;background:#0b1017}canvas{width:100%;height:auto;display:block;cursor:crosshair}.stats{padding:12px 16px;border-top:1px solid var(--line);font-variant-numeric:tabular-nums}.stats small{display:block;color:var(--muted);margin-top:3px}.legend{display:flex;gap:20px;flex-wrap:wrap;margin:14px 0;color:var(--muted);font-size:12px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--accent);margin-right:6px}.dot.hollow{border:1px solid #bcc5d1;background:transparent}.dot.faint{border:1px dotted #7a8798;background:transparent}.context{padding:11px 14px;background:#1c2530;border:1px solid var(--line);border-radius:7px;color:var(--muted);min-height:66px}footer{margin-top:18px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}#scenario-label{color:var(--accent)}@media(max-width:900px){main{padding:18px}.selectors{grid-template-columns:1fr 1fr}.panels{grid-template-columns:1fr}.panelhead small{display:none}}
</style></head><body><main>
<div class="eyebrow">STM Domains · eksperyment 24 · prototyp badawczy</div>
<h1>Czy uczenie grafu pomaga rozdzielić domeny?</h1>
<p class="intro">Porównaj zapisaną geometrię, ten sam graf przed i po uczeniu oraz procedurę z próby 15. Każde kółko jest <strong>środkiem wejściowego oznaczenia molekuły</strong>. Udział przypisań opisuje te oznaczenia — nie wykrywalność molekuł ani powierzchnię materiału.</p>
<div class="selectors">
<label>Protokół<select id="regime"><option value="transfer">Transfer w jednej akwizycji</option><option value="transductive">Opis całej bieżącej serii</option></select></label>
<label>Model<select id="family"></select></label><label>Ziarno modelu<select id="seed"></select></label>
<label>Podział<select id="partition"></select></label><label>Klatka lub kontrola<select id="sample"></select></label>
</div>
<div class="scenarios"><span>Scenariusze:</span><span id="scenario-buttons" class="scenarios" style="margin:0"></span></div>
<div class="walkthrough"><p><strong id="scenario-label">Swobodne porównanie</strong> <span id="scenario-explanation">Wybierz obraz i wariant. Najedź na oznaczenie lub kliknij je, aby zobaczyć okno kontekstu.</span></p>
<div class="steps"><span>Kroki porównania:</span><button id="step-geometry">1. Cechy geometrii</button><button id="step-untrained">2. Graf przed uczeniem</button><button id="step-trained">3. Graf po uczeniu</button><button id="step-legacy">4. Procedura 15</button><button id="step-test">5. Część testowa</button></div></div>
<div class="toolbar"><button id="previous">← Poprzednia</button><button id="next">Następna →</button>
<label><input id="heldout" type="checkbox">Tylko osobny graf testowy</label><label><input id="points" type="checkbox" checked>Pokaż oznaczenia</label><label>Widoczność <input id="opacity" type="range" min="0.1" max="1" step="0.05" value="0.85"></label><button id="clear-context">Wyczyść wybór otoczenia</button></div>
<div id="notice" class="notice"></div>
<div class="panels"><section class="panel"><div class="panelhead"><h2 id="before-title">Przed odmowami</h2><small id="before-subtitle">Składowe podobieństwa</small></div><div class="canvaswrap"><canvas id="before"></canvas></div><div id="before-stats" class="stats"></div></section>
<section class="panel"><div class="panelhead"><h2 id="after-title">Po odmowach</h2><small>Porządek i spójność</small></div><div class="canvaswrap"><canvas id="after"></canvas></div><div id="after-stats" class="stats"></div></section></div>
<div class="legend"><span><i class="dot"></i>Przypisane oznaczenie</span><span><i class="dot hollow"></i>Bez przypisania</span><span><i class="dot faint"></i>Brak pełnego wsparcia / poza zakresem</span><span>Kolor oznacza składową, nie fizyczny typ sieci.</span></div>
<div id="context" class="context">Najedź na kółko lub kliknij je. Żółta ramka pokaże kontekst 72 × 72 jednostki odniesienia; nie jest konturem molekuły ani domeny.</div>
<footer><strong>Zapisane wyniki, bez obliczania nowych domen w przeglądarce.</strong> Jedna akwizycja TTMAPP, częściowe referencje i kontrolowane syntetyki. Brak domeny nie dowodzi braku materiału. Brak oznaczeń nie dowodzi pustego podłoża. Obrazy mają kontrast podglądu 2–98%; geometria oznaczeń pozostaje w oryginalnych współrzędnych obrazu. Okno kontekstu grafu jest większe niż pojedyncza molekuła.</footer>
<script id="data" type="application/json">__DATA__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const FAMILIES=['geometry','graph_untrained','graph_sce_scale','graph_sce','legacy15'];
const lookup=new Map(DATA.predictions.map(p=>[`${p.variant_id}|${p.partition}|${p.sample_id}`,p]));
const images=new Map();let token=0,chosen=-1,hover=-1,scenario=null;
function options(element,rows,preferred){element.replaceChildren(...rows.map(([value,label])=>{const o=document.createElement('option');o.value=value;o.textContent=label;return o}));if(rows.some(r=>r[0]===preferred))element.value=preferred;}
function availableRuns(){return DATA.runs.filter(r=>r.regime===$('regime').value)}
function refreshFamily(){const present=new Set(availableRuns().map(r=>r.family));options($('family'),FAMILIES.filter(f=>present.has(f)).map(f=>[f,DATA.family_labels[f]]),$('family').value);refreshSeed();}
function refreshSeed(){const old=$('seed').value;const rows=availableRuns().filter(r=>r.family===$('family').value).sort((a,b)=>(a.seed||0)-(b.seed||0));options($('seed'),rows.map(r=>[r.seed===null?'none':String(r.seed),r.seed===null?'Bez treningu':String(r.seed)]),old);$('seed').disabled=rows.length===1;const legacy=$('family').value==='legacy15';options($('partition'),legacy?[['legacy15','Pełna procedura 15']]:[['fh4','FH · k = 4'],['mws','Mutex Watershed']],$('partition').value);$('partition').disabled=legacy;}
function currentRun(){const seed=$('seed').value==='none'?null:Number($('seed').value);return availableRuns().find(r=>r.family===$('family').value&&r.seed===seed);}
function currentPrediction(){const run=currentRun();return run?lookup.get(`${run.variant_id}|${$('partition').value}|${$('sample').value}`):null;}
function stageCounts(labels,scope,sample){let assigned=0,denominator=0;const parts=new Set();labels.forEach((v,i)=>{if(scope[i]&&sample.available[i]){denominator++;if(v>0){assigned++;parts.add(v)}}});return{assigned,denominator,parts:parts.size,coverage:denominator?assigned/denominator:null};}
function colorMap(labels,ids){const canonical=new Map();labels.forEach((v,i)=>{if(v>0&&(!canonical.has(v)||ids[i]<canonical.get(v)))canonical.set(v,ids[i])});return new Map([...canonical].map(([v,id])=>{let h=2166136261;for(const c of id)h=Math.imul(h^c.charCodeAt(0),16777619)>>>0;return[v,`hsl(${h%360} 72% 68%)`]}));}
function contextIndex(){return chosen>=0?chosen:hover;}
function contextText(sample){const i=contextIndex();if(i<0){$('context').textContent='Najedź na kółko lub kliknij je. Żółta ramka pokaże kontekst 72 × 72 jednostki odniesienia; nie jest konturem molekuły ani domeny.';return;}const p=sample.xy[i];$('context').textContent=`Oznaczenie ${sample.ids[i]} · środek (${p[0].toFixed(2)}, ${p[1].toFixed(2)}) px · ${sample.node_count[i]} oznaczeń w kontekście · ${sample.available[i]?'pełne wsparcie':'brak pełnego wsparcia'}${chosen>=0?' · wybór przypięty kliknięciem':''}. Ramka pokazuje wejście lokalnego grafu.`;}
function paint(canvas,image,sample,labels,scope){const k=3;canvas.width=sample.width*k;canvas.height=sample.height*k;const ctx=canvas.getContext('2d');ctx.scale(k,k);ctx.imageSmoothingEnabled=false;ctx.drawImage(image,0,0,sample.width,sample.height);if($('points').checked){const colors=colorMap(labels,sample.ids);sample.xy.forEach((p,i)=>{const available=scope[i]&&sample.available[i];ctx.globalAlpha=Number($('opacity').value)*(scope[i]?1:.15);ctx.beginPath();ctx.arc(p[0],p[1],available?1.9:1.5,0,Math.PI*2);ctx.lineWidth=.65;ctx.setLineDash(available?[]:[.6,.6]);if(labels[i]>0&&available){ctx.fillStyle=colors.get(labels[i]);ctx.fill();ctx.strokeStyle='#18252b';}else{ctx.strokeStyle=available?'#d0d7e0':'#7d8a9c';}ctx.stroke();});ctx.setLineDash([]);ctx.globalAlpha=1;}const i=contextIndex();if(i>=0){const b=sample.support[i],p=sample.xy[i];ctx.strokeStyle='#ffe18a';ctx.lineWidth=.7;ctx.setLineDash([2,1.3]);ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.setLineDash([]);ctx.beginPath();ctx.arc(p[0],p[1],3.4,0,Math.PI*2);ctx.stroke();}}
function render(){const id=++token,sample=DATA.samples[$('sample').value],run=currentRun(),prediction=currentPrediction();if(!sample||!run||!prediction)throw new Error('Brak zapisanego wariantu');const heldoutPossible=Boolean(prediction.heldout);$('heldout').disabled=!heldoutPossible;$('step-test').disabled=!heldoutPossible;if(!heldoutPossible)$('heldout').checked=false;const heldout=$('heldout').checked,values=heldout?prediction.heldout:prediction.full,legacy=run.family==='legacy15';const before=stageCounts(values.before,values.scope,sample),after=stageCounts(values.after,values.scope,sample);$('before-title').textContent=legacy?'Procedura 15 — wynik końcowy':'Przed odmowami';$('before-subtitle').textContent=legacy?'Brak osobnego wyniku surowego':'Składowe podobieństwa';$('after-title').textContent=legacy?'Procedura 15 — ten sam wynik':'Po odmowach';for(const [name,count] of [['before',before],['after',after]]){$(name+'-stats').innerHTML=`<strong>${name==='before'&&!legacy?'Składowe':'Kandydaci domen'}: ${count.parts} · przypisano ${count.assigned} / ${count.denominator} (${count.coverage===null?'—':(100*count.coverage).toFixed(1)+'%'})</strong><small>Mianownik: oznaczenia z pełnym wsparciem w wybranym zakresie. Wszystkie zapisane oznaczenia obrazu: ${sample.ids.length}.</small>`;}let notice=sample.kind==='measurement'?(run.regime==='transfer'?(heldout?'Osobny graf testowy: węzły i połączenia wyłącznie części testowej. Pełny obraz pozostaje tłem.':'Pełna klatka: kontekst do podglądu. Ocena transferu korzysta z osobnego grafu testowego; włącz przełącznik, aby go zobaczyć.'):'Transdukcja: opis bieżącej serii użytej do treningu. To nie jest test przenoszenia na nowe akwizycje.'):'Kontrola syntetyczna: zapisany wynik zamrożonej procedury; ziarno kontroli jest osobne od ziarna modelu.';if(legacy)notice+=' Oba panele przedstawiają pełną procedurę 15. Nie zapisano osobnego etapu przed jej odmowami.';if(!sample.ids.length)notice+=' Brak zapisanych oznaczeń: graf nie ma węzłów. Nie jest to rozpoznanie pustego podłoża.';$('notice').textContent=notice;contextText(sample);const state={ready:false,sample:sample.id,regime:run.regime,family:run.family,seed:run.seed,variant:run.variant_id,method:$('partition').value,heldout,points:$('points').checked,opacity:Number($('opacity').value),contextIndex:contextIndex(),before,after,legacy};window.galleryState=state;let image=images.get(sample.id);const finish=()=>{if(id!==token)return;paint($('before'),image,sample,values.before,values.scope);paint($('after'),image,sample,values.after,values.scope);window.galleryState={...state,ready:true};};if(!image){image=new Image();images.set(sample.id,image);image.onload=finish;image.onerror=()=>{throw new Error('Nie można odczytać obrazu podglądu')};image.src=sample.image;}else if(image.complete&&image.naturalWidth)finish();else image.onload=finish;}
function chooseFamily(family){$('family').value=family;refreshSeed();render();}
function chooseScenario(name){scenario=name;const value=DATA.scenarios[name];$('regime').value='transfer';refreshFamily();$('family').value='graph_sce_scale';refreshSeed();$('seed').value='20261101';$('partition').value='fh4';$('sample').value=value.sample;$('heldout').checked=false;$('points').checked=true;chosen=hover=-1;document.querySelectorAll('[data-scenario]').forEach(b=>b.classList.toggle('active',b.dataset.scenario===name));$('scenario-label').textContent=value.label+' —';$('scenario-explanation').textContent=value.explanation;render();}
for(const [name,value] of Object.entries(DATA.scenarios)){const button=document.createElement('button');button.id='scenario-'+name;button.dataset.scenario=name;button.textContent=value.label;button.onclick=()=>chooseScenario(name);$('scenario-buttons').append(button);}
$('regime').onchange=()=>{refreshFamily();chosen=hover=-1;render();};$('family').onchange=()=>{refreshSeed();render();};for(const id of ['seed','partition','heldout','points'])$(id).onchange=render;$('sample').onchange=()=>{chosen=hover=-1;render();};$('opacity').oninput=render;
for(const [id,offset] of [['previous',-1],['next',1]])$(id).onclick=()=>{const index=DATA.sample_order.indexOf($('sample').value);$('sample').value=DATA.sample_order[(index+offset+DATA.sample_order.length)%DATA.sample_order.length];chosen=hover=-1;render();};
$('step-geometry').onclick=()=>chooseFamily('geometry');$('step-untrained').onclick=()=>chooseFamily('graph_untrained');$('step-trained').onclick=()=>chooseFamily('graph_sce_scale');$('step-legacy').onclick=()=>chooseFamily('legacy15');$('step-test').onclick=()=>{$('heldout').checked=true;render();};$('clear-context').onclick=()=>{chosen=hover=-1;render();};
function nearest(event,canvas){const sample=DATA.samples[$('sample').value],rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width*sample.width,y=(event.clientY-rect.top)/rect.height*sample.height;let selected=-1,distance=8;sample.xy.forEach((p,i)=>{const d=Math.hypot(p[0]-x,p[1]-y);if(d<distance){distance=d;selected=i}});return selected;}
for(const id of ['before','after']){const canvas=$(id);canvas.onmousemove=event=>{const i=nearest(event,canvas);if(i!==hover&&chosen<0){hover=i;render();}};canvas.onmouseleave=()=>{if(chosen<0&&hover>=0){hover=-1;render();}};canvas.onclick=event=>{chosen=nearest(event,canvas);hover=-1;render();};}
options($('sample'),DATA.sample_order.map(id=>[id,DATA.samples[id].label]),'ttmapp-250');refreshFamily();render();
</script></main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, help="Completed evaluation directory; defaults to OUTPUT/evaluation")
    parser.add_argument("--controls-evaluation", type=Path, help="Control display metadata directory; defaults to OUTPUT/controls/evaluation")
    args = parser.parse_args()
    result = build(args.output, args.evaluation, args.controls_evaluation)
    print(json.dumps({key: result[key] for key in ("html", "samples", "variants", "predictions", "html_bytes")}))


if __name__ == "__main__":
    main()
