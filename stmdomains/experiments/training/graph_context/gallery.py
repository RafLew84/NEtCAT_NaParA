"""Read-only, self-contained comparison of saved issue-24a control results."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from ..gallery import _display_png
from ..graph_ssl.gallery import CASE_LABELS
from .evaluation import Budget


FAMILIES = {
    "geometry": "Geometria centrum — bez encodera",
    "graph_untrained": "Graf — wagi przed uczeniem",
    "graph_sce_scale": "Graf — wagi po uczeniu 24",
}
SCENARIOS = {
    "single": ("single", "Pełna sieć"),
    "orientation8": ("orientation_8deg", "Obrót 8°"),
    "phase": ("phase_boundary", "Przesunięcie"),
    "phasejitter": ("phase_centers_jitter_072", "Przesunięcie i jitter"),
    "rows": ("independent_rows", "Niezależne rzędy"),
}


def read(path):
    return json.loads(Path(path).read_text())


def _build(root, budget):
    frozen_path = root / "frozen-predictions.json"
    evidence_path = root / "evaluation/evidence.json"
    frozen, evidence = read(frozen_path), read(evidence_path)
    if evidence["frozen_manifest_sha256"] != file_hash(frozen_path):
        raise ValueError("Evaluation belongs to another prediction freeze")
    checked = {}

    def pinned(relative):
        budget.check()
        path = root / relative
        digest = file_hash(path)
        if frozen["files"].get(relative) != digest:
            raise ValueError("Changed or unpinned gallery input: " + relative)
        checked[relative] = digest
        return path

    plan = read(pinned("plan.json"))
    prepared = read(pinned("prepared/manifest.json"))
    index = read(pinned("predictions/index.json"))
    source_root = Path(plan["source_root"])
    if not source_root.is_absolute():
        raise ValueError("The original24 source root must be absolute")
    controls_path = source_root / "controls/evaluation/manifest.json"
    if file_hash(controls_path) != evidence["controls_manifest_sha256"]:
        raise ValueError("Control display metadata differs from the completed evaluation")
    # Read names/seeds only after completed evaluation. No truth array is opened.
    controls = {row["sample_id"]: row for row in read(controls_path)["controls"]}
    samples = {}
    for item in budget.checked(prepared["samples"]):
        ident = item["sample_id"]
        control = controls[ident]
        source = Path(item.get("source_analysis", source_root / "controls/analysis"))
        record, arrays = load_sample(source, ident)
        rows = read(pinned("prepared/" + item["rows_file"]))
        png, display = _display_png(arrays)
        samples[ident] = dict(
            id=ident, case=control["case"], control_seed=control["seed"],
            label=f"{CASE_LABELS[control['case']]} · ziarno {control['seed']}",
            width=int(arrays["image"].shape[1]), height=int(arrays["image"].shape[0]),
            image="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
            image_content_sha256=record["content_sha256"], display=display,
            ids=[r["element_id"] for r in rows], xy=[r["raw_edge_xy"] for r in rows],
            support=[r["support_xyxy"] for r in rows], available=[bool(r["available"]) for r in rows])
    runs, predictions = {}, []
    if isinstance(index, dict):
        index = index["entries"]
    for entry in budget.checked(index):
        sample = samples[entry["sample_id"]]
        with np.load(pinned(entry["file"]), allow_pickle=False) as archive:
            before, after, states = archive["before"], archive["after"], archive["states"]
        if any(a.shape != (len(sample["ids"]),) for a in (before, after, states)):
            raise ValueError("Prediction rows do not align with original input centres")
        available = np.asarray(sample["available"], dtype=bool)
        if ((before > 0) & ~available).any() or ((after > 0) & ~available).any():
            raise ValueError("Prediction assigned a centre outside original S24 support")
        predictions.append(dict(variant_id=entry["variant_id"], sample_id=entry["sample_id"],
                                partition=entry["partition"], before=before.tolist(), after=after.tolist()))
        runs[entry["variant_id"]] = {name: entry.get(name) for name in
                                     ("variant_id", "base_variant_id", "mode", "family", "seed")}
    if len(samples) != 93 or len(runs) != 19 or len(predictions) != 3534:
        raise ValueError("Expected complete19-variant, two-solver,93-control gallery")
    scenarios = {}
    for name, (case, label) in SCENARIOS.items():
        chosen = min((s for s in samples.values() if s["case"] == case), key=lambda s: s["control_seed"])
        scenarios[name] = dict(sample=chosen["id"], label=label)
    payload = dict(samples=samples, runs=list(runs.values()), predictions=predictions,
                   sample_order=sorted(samples, key=lambda sid: (samples[sid]["case"], samples[sid]["control_seed"])),
                   scenarios=scenarios, families=FAMILIES)
    target = root / "index.html"
    if target.exists() or (root / "gallery/manifest.json").exists():
        raise FileExistsError("Preserve the previous exported gallery")
    document = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    target.write_text(document)
    manifest = dict(schema="stmdomains-graph24a-gallery-v1", html_sha256=file_hash(target),
        html_bytes=target.stat().st_size, source_sha256=file_hash(Path(__file__)),
        display_source_sha256=file_hash(Path(__file__).parent.parent / "gallery.py"),
        samples=len(samples), variants=len(runs), predictions=len(predictions), scenarios=scenarios,
        frozen_manifest_sha256=file_hash(frozen_path), evidence_sha256=file_hash(evidence_path),
        control_display_manifest_sha256=file_hash(controls_path), checked_inputs=checked,
        interpretation="Known controls; zero new fits; original S24 denominator; root_only is an ablation; no material area or detection recall.")
    write_json(root / "gallery/manifest.json", manifest)
    budget.check()
    return manifest


def build(output):
    root = Path(output).resolve()
    resource_path = root / "gallery.resources.json"
    if resource_path.exists():
        raise FileExistsError(resource_path)
    budget, status = Budget(root), "failed"
    try:
        result = _build(root, budget)
        status = "completed"
        return result
    finally:
        write_json(resource_path, dict(status=status, **budget.measurements()))


HTML = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>STM Domains — kontekst grafu 24a</title>
<style>
:root{color-scheme:dark;--bg:#10151d;--panel:#17212d;--text:#e8eef7;--muted:#a6b7ca;--accent:#8ce7d3;--line:#35475c}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:25px 30px}h1{font-size:27px;margin:3px 0 8px}h2{font-size:17px;margin:0}.eyebrow{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:.07em}.intro{color:var(--muted);max-width:1190px;margin:0 0 18px}.selectors{display:grid;grid-template-columns:1.5fr 1.4fr .7fr .9fr 1.6fr;gap:12px}label{font-size:12px;color:var(--muted)}select,button,input{font:inherit}select,button{border:1px solid #435974;background:#202e3e;color:var(--text);border-radius:6px;padding:8px 10px}select{width:100%;display:block;margin-top:5px}button{cursor:pointer}button:hover{border-color:var(--accent)}button:disabled,select:disabled{opacity:.55}.toolbar,.scenarios{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:13px}.toolbar label{display:flex;align-items:center;gap:6px}input{accent-color:var(--accent)}input[type=range]{width:120px}.notice{padding:10px 14px;margin:14px 0;background:#302b21;border-left:3px solid #e5bd67;color:#f4d797;min-height:45px}.panels{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel)}.panelhead{padding:12px 15px}.panelhead small{color:var(--muted)}.canvaswrap{padding:9px;background:#090f16}canvas{display:block;width:100%;height:auto;cursor:crosshair}.stats{padding:12px 15px;border-top:1px solid var(--line);font-variant-numeric:tabular-nums}.stats small{display:block;color:var(--muted);margin-top:3px}.context{padding:11px 14px;background:#1c2733;border:1px solid var(--line);border-radius:6px;margin-top:14px;color:var(--muted)}footer{color:var(--muted);font-size:12px;margin-top:15px}#stage-label{color:var(--accent)}@media(max-width:900px){main{padding:18px}.selectors{grid-template-columns:1fr 1fr}.panels{grid-template-columns:1fr}}
</style></head><body><main><div class="eyebrow">STM Domains · 24a · znane kontrole</div><h1>Czy sposób wycięcia otoczenia zmienia podział?</h1>
<p class="intro">Po lewej zapisany wynik zamkniętego otoczenia72 z próby24, po prawej wybrana zmiana wejścia. <strong>Zero nowych treningów.</strong> Kółka pokazują rzeczywiste centra wejściowych oznaczeń. We wszystkich porównaniach obowiązuje ten sam zbiór dostępnych centrów S24.</p>
<div class="selectors"><label>Reprezentacja<select id="family"></select></label><label>Zmiana po prawej<select id="mode"><option value="halfopen72">Półotwarte otoczenie72</option><option value="root_only">Tylko centrum — ablacja</option></select></label><label>Ziarno modelu<select id="seed"></select></label><label>Podział<select id="partition"><option value="fh4">FH · k = 4</option><option value="mws">Mutex Watershed</option></select></label><label>Kontrola<select id="sample"></select></label></div>
<div class="scenarios"><span>Scenariusze:</span><span id="scenario-buttons" class="scenarios" style="margin:0"></span></div>
<div class="toolbar"><button id="previous">← Poprzednia</button><button id="next">Następna →</button><label><input id="after" type="checkbox" checked>Po odmowach</label><strong id="stage-label"></strong><label><input id="points" type="checkbox" checked>Pokaż oznaczenia</label><label>Widoczność <input id="opacity" type="range" min="0.1" max="1" step="0.05" value="0.85"></label><button id="clear-context">Wyczyść wybór</button></div>
<div id="notice" class="notice"></div><div class="panels"><section class="panel"><div class="panelhead"><h2 id="left-title">Zamknięte otoczenie72 — baza24</h2><small>Ten sam zapisany wynik dla wybranych wag i solvera</small></div><div class="canvaswrap"><canvas id="left"></canvas></div><div id="left-stats" class="stats"></div></section><section class="panel"><div class="panelhead"><h2 id="right-title"></h2><small>Te same wagi, adapter, korzenie i reguły podziału</small></div><div class="canvaswrap"><canvas id="right"></canvas></div><div id="right-stats" class="stats"></div></section></div>
<div id="context" class="context">Najedź na oznaczenie lub kliknij je. Żółta ramka pokaże pierwotne wsparcie S24 72 × 72, nie kontur molekuły ani domeny.</div>
<footer>Wypełnione kółko: przypisane centrum. Puste kółko: odmowa. Przerywane: poza pierwotnym dostępnym wsparciem. Kolor oznacza składową, nie fizyczny typ. Udział przypisań nie jest wykrywalnością molekuł ani powierzchnią materiału. Znane syntetyki służą diagnozie; nie stanowią nowego testu generalizacji. Przeglądarka wyświetla zapisane wyniki, bez inferencji.</footer></main>
<script id="data" type="application/json">__DATA__</script><script>
'use strict';
const DATA=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id),lookup=new Map(DATA.predictions.map(p=>[`${p.variant_id}|${p.partition}|${p.sample_id}`,p])),images=new Map();let token=0,chosen=-1,hover=-1;
function options(el,rows,preferred){el.replaceChildren(...rows.map(([v,t])=>{const o=document.createElement('option');o.value=v;o.textContent=t;return o}));if(rows.some(r=>r[0]===preferred))el.value=preferred;}
function refresh(){const family=$('family').value,old=$('seed').value,seeds=[...new Set(DATA.runs.filter(r=>r.family===family).map(r=>r.seed))].sort((a,b)=>(a||0)-(b||0));options($('seed'),seeds.map(s=>[s===null?'none':String(s),s===null?'Bez treningu':String(s)]),old);$('seed').disabled=seeds.length===1;$('mode').disabled=family==='geometry';}
function runs(){const family=$('family').value,seed=$('seed').value==='none'?null:Number($('seed').value),mode=family==='geometry'?'root57':$('mode').value;const candidates=DATA.runs.filter(r=>r.family===family&&r.seed===seed),right=candidates.find(r=>r.mode===mode),left=candidates.find(r=>r.mode===(family==='geometry'?'root57':'closed72'));if(!left||!right)throw new Error('Brak zapisanej pary wariantów');return{left,right,mode,family,seed};}
function counts(labels,sample){let assigned=0;const parts=new Set();labels.forEach((v,i)=>{if(sample.available[i]&&v>0){assigned++;parts.add(v)}});const denominator=sample.available.filter(Boolean).length;return{assigned,denominator,parts:parts.size,coverage:denominator?assigned/denominator:null};}
function colors(labels,ids){const canonical=new Map();labels.forEach((v,i)=>{if(v>0&&(!canonical.has(v)||ids[i]<canonical.get(v)))canonical.set(v,ids[i])});return new Map([...canonical].map(([v,id])=>{let h=2166136261;for(const c of id)h=Math.imul(h^c.charCodeAt(0),16777619)>>>0;return[v,`hsl(${h%360} 72% 68%)`]}));}
function contextIndex(){return chosen>=0?chosen:hover;}
function paint(canvas,image,sample,labels){const k=3;canvas.width=sample.width*k;canvas.height=sample.height*k;const ctx=canvas.getContext('2d');ctx.scale(k,k);ctx.imageSmoothingEnabled=false;ctx.drawImage(image,0,0,sample.width,sample.height);if($('points').checked){const color=colors(labels,sample.ids);sample.xy.forEach((p,i)=>{const available=sample.available[i];ctx.globalAlpha=Number($('opacity').value)*(available?1:.25);ctx.beginPath();ctx.arc(p[0],p[1],available?1.8:1.4,0,Math.PI*2);ctx.lineWidth=.65;ctx.setLineDash(available?[]:[.6,.6]);if(available&&labels[i]>0){ctx.fillStyle=color.get(labels[i]);ctx.fill();ctx.strokeStyle='#19252c'}else ctx.strokeStyle=available?'#cbd4df':'#7e8c9d';ctx.stroke()});ctx.setLineDash([]);ctx.globalAlpha=1;}const i=contextIndex();if(i>=0){const b=sample.support[i];ctx.strokeStyle='#ffe18a';ctx.lineWidth=.7;ctx.setLineDash([2,1.2]);ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.setLineDash([]);ctx.beginPath();ctx.arc(sample.xy[i][0],sample.xy[i][1],3.3,0,Math.PI*2);ctx.stroke();}}
function render(){const id=++token,sample=DATA.samples[$('sample').value],selected=runs(),stage=$('after').checked?'after':'before',values={},summaries={};for(const side of ['left','right']){const run=selected[side],prediction=lookup.get(`${run.variant_id}|${$('partition').value}|${sample.id}`);if(!prediction)throw new Error('Brak zapisanego wyniku');values[side]=prediction[stage];summaries[side]={before:counts(prediction.before,sample),after:counts(prediction.after,sample)};const c=summaries[side][stage];$(side+'-stats').innerHTML=`<strong>${stage==='after'?'Kandydaci domen':'Składowe'}: ${c.parts} · przypisano ${c.assigned} / ${c.denominator} (${c.coverage===null?'—':(100*c.coverage).toFixed(1)+'%'})</strong><small>Mianownik: niezmieniony zbiór dostępnych centrów S24. Wszystkie oznaczenia: ${sample.ids.length}.</small>`;}$('stage-label').textContent=stage==='after'?'Po odmowach':'Przed odmowami';$('left-title').textContent=selected.family==='geometry'?'Cechy centrum — baza24':'Zamknięte otoczenie72 — baza24';$('right-title').textContent=selected.mode==='root57'?'Te same cechy centrum':selected.mode==='halfopen72'?'Półotwarte otoczenie72':'Tylko centrum — ablacja';let notice=selected.mode==='root_only'?'Ablacja root_only: wyłączono przekazywanie informacji między węzłami. To diagnoza udziału kontekstu, nie naprawiony ani ponownie wytrenowany model.':selected.mode==='halfopen72'?'Półotwarte otoczenie: wyłączono centra na prawym i dolnym końcu +36. Promień krawędzi pozostaje przypięty z zamkniętego otoczenia72.':'Kontrola geometryczna: oba panele pokazują ten sam opis57 cech centrum; nie stosuje się zmian message passing.';if(!sample.ids.length)notice+=' Brak oznaczeń tworzy pusty graf; nie dowodzi rozpoznania pustego podłoża.';$('notice').textContent=notice;const ci=contextIndex();$('context').textContent=ci<0?'Najedź na oznaczenie lub kliknij je. Żółta ramka pokaże pierwotne wsparcie S24 72 × 72, nie kontur molekuły ani domeny.':`Oznaczenie ${sample.ids[ci]} · (${sample.xy[ci][0].toFixed(2)}, ${sample.xy[ci][1].toFixed(2)}) px · ${sample.available[ci]?'dostępne w S24':'poza dostępnym S24'}. Ramka pokazuje niezmienione wsparcie oceny72, także dla ablacji jednego centrum.`;const state={ready:false,sample:sample.id,family:selected.family,seed:selected.seed,mode:selected.mode,method:$('partition').value,stage,points:$('points').checked,opacity:Number($('opacity').value),contextIndex:ci,left:summaries.left[stage],right:summaries.right[stage],all_stages:summaries,left_variant:selected.left.variant_id,right_variant:selected.right.variant_id};window.galleryState=state;let image=images.get(sample.id);const finish=()=>{if(token!==id)return;paint($('left'),image,sample,values.left);paint($('right'),image,sample,values.right);window.galleryState={...state,ready:true};};if(!image){image=new Image();images.set(sample.id,image);image.onload=finish;image.onerror=()=>{throw new Error('Błąd odczytu obrazu')};image.src=sample.image;}else if(image.complete&&image.naturalWidth)finish();else image.onload=finish;}
function scenario(name){$('family').value='graph_sce_scale';refresh();$('seed').value='20261101';$('mode').value='halfopen72';$('partition').value='fh4';$('sample').value=DATA.scenarios[name].sample;$('after').checked=true;chosen=hover=-1;render();}
for(const [name,value] of Object.entries(DATA.scenarios)){const button=document.createElement('button');button.id='scenario-'+name;button.textContent=value.label;button.onclick=()=>scenario(name);$('scenario-buttons').append(button)}
$('family').onchange=()=>{refresh();render()};for(const id of ['mode','seed','partition','after','points'])$(id).onchange=render;$('sample').onchange=()=>{chosen=hover=-1;render()};$('opacity').oninput=render;$('clear-context').onclick=()=>{chosen=hover=-1;render()};for(const [id,offset] of [['previous',-1],['next',1]])$(id).onclick=()=>{const i=DATA.sample_order.indexOf($('sample').value);$('sample').value=DATA.sample_order[(i+offset+DATA.sample_order.length)%DATA.sample_order.length];chosen=hover=-1;render()};
function nearest(event,canvas){const s=DATA.samples[$('sample').value],r=canvas.getBoundingClientRect(),x=(event.clientX-r.left)/r.width*s.width,y=(event.clientY-r.top)/r.height*s.height;let index=-1,distance=7;s.xy.forEach((p,i)=>{const d=Math.hypot(p[0]-x,p[1]-y);if(d<distance){index=i;distance=d}});return index;}
for(const id of ['left','right']){const canvas=$(id);canvas.onmousemove=e=>{const i=nearest(e,canvas);if(chosen<0&&i!==hover){hover=i;render()}};canvas.onmouseleave=()=>{if(chosen<0&&hover>=0){hover=-1;render()}};canvas.onclick=e=>{chosen=nearest(e,canvas);hover=-1;render()};}
options($('family'),Object.entries(DATA.families),'graph_sce_scale');options($('sample'),DATA.sample_order.map(id=>[id,DATA.samples[id].label]),DATA.scenarios.single.sample);refresh();render();
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({key: result[key] for key in ("samples", "variants", "predictions", "html_bytes")}))


if __name__ == "__main__":
    main()
