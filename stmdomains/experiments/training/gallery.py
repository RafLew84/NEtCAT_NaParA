"""Standalone Polish viewer of saved issue21 predictions, without references.

Reads analysis images and already saved grid48 assignments. Optional post-freeze
metadata names fixed scenarios without opening truth rasters. The HTML embeds
its JSON and PNG backgrounds so file:// needs no server or external resources.
"""

from __future__ import annotations

import argparse
import base64
import colorsys
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ..bundle import file_hash, load_sample, write_json


def _read_json(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def _control_scenarios(output: Path, manifest_path: Path) -> dict[str, str]:
    """Name fixed examples from metadata only, after predictions are frozen."""
    if not (output / "frozen-predictions.json").is_file():
        raise ValueError("Control manifest scenarios require already frozen predictions")
    manifest = _read_json(manifest_path)
    if manifest.get("schema") != "stmdomains-evaluation-v1":
        raise ValueError("Unsupported control evaluation manifest")
    cases = {"single": "single", "boundary": "two_orientations"}
    scenarios = {"ttmapp": "ttmapp-250"}
    for scenario, case in cases.items():
        matches = [record["sample_id"] for record in manifest["controls"]
                   if record["case"] == case and record["seed"] == 920001]
        if len(matches) != 1:
            raise ValueError(f"Expected one {case} control for seed 920001, found {len(matches)}")
        scenarios[scenario] = matches[0]
    write_json(output / "gallery/scenario-map.json", scenarios)
    write_json(output / "gallery/scenario-source.json", dict(
        controls_manifest=str(manifest_path.resolve()),
        controls_manifest_sha256=file_hash(manifest_path), control_seed=920001,
        cases=cases, selection_rule="Fixed first control seed, without selection by model output",
        mapping_file="scenario-map.json",
    ))
    return scenarios


def _display_png(arrays: dict) -> tuple[bytes, dict]:
    image = np.asarray(arrays["image"], dtype=np.float64)
    measured = np.asarray(arrays["measured"], dtype=bool)
    valid = measured & np.isfinite(image)
    gray = np.full(image.shape, 127, dtype=np.uint8)
    if valid.any():
        low, high = np.quantile(image[valid], [.02, .98])
        if high > low:
            gray[valid] = np.rint(np.clip((image[valid] - low) / (high - low), 0, 1) * 255).astype(np.uint8)
    else:
        low = high = None
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    rgb[~valid] = [38, 45, 58]
    stream = io.BytesIO()
    Image.fromarray(rgb).save(stream, format="PNG")
    return stream.getvalue(), dict(low=None if low is None else float(low),
                                  high=None if high is None else float(high),
                                  purpose="display_only_percentile2_98_per_raw_frame")


def _metrics(path: Path, expected: int) -> dict:
    with np.load(path, allow_pickle=False) as arrays:
        before, after = arrays["before"], arrays["after"]
        available = arrays["available"]
    if before.shape != (expected,) or after.shape != (expected,) or available.shape != (expected,):
        raise ValueError(f"Prediction geometry mismatch: {path}")
    return dict(before=before.astype(int).tolist(), after=after.astype(int).tolist(),
                available=available.astype(bool).tolist())


def _preview_png(sample: dict, prediction: dict, path: Path, *, label: str) -> None:
    """Export a fixed saved example; never choose a model by its apparent quality."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    image = np.asarray(Image.open(io.BytesIO(base64.b64decode(sample["image"].split(",", 1)[1]))))
    figure = Figure(figsize=(10, 5.8), dpi=150, layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 2)
    xy = np.asarray(sample["xy"])
    available = np.asarray(prediction["full"]["available"], dtype=bool)
    for axis, stage, title in zip(axes, ("before", "after"), ("Przed odmowami", "Po odmowach")):
        labels = np.asarray(prediction["full"][stage])
        axis.imshow(image, extent=(0, sample["width"], sample["height"], 0), interpolation="nearest")
        for component in sorted(set(labels) - {0}):
            indices = np.flatnonzero(labels == component)
            canonical = min(sample["ids"][i] for i in indices)
            value = 2166136261
            for character in canonical:
                value = ((value ^ ord(character)) * 16777619) & 0xffffffff
            color = colorsys.hls_to_rgb((value % 360) / 360, .68, .88)
            axis.scatter(xy[indices, 0], xy[indices, 1], s=18, c=[color], edgecolors="black", linewidths=.3)
        refused = labels == 0
        if refused.any():
            axis.scatter(xy[refused, 0], xy[refused, 1], marker="x", s=8, c="#a9b2bf", linewidths=.5)
        assigned, denominator = int((labels > 0).sum()), int(available.sum())
        axis.set_title(f"{title}\n{len(set(labels) - {0})} składowych; {assigned}/{denominator} przypisań", fontsize=10)
        axis.set(xlabel="x [raw px]", ylabel="y [raw px]", xlim=(0, sample["width"]), ylim=(sample["height"], 0))
    figure.suptitle(f"{label} · {prediction['run_id']} · {prediction['partition']}\nPunkty siatki 48 px; bez referencji, konturów i powierzchni", fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path)


def build_gallery(output: Path, *, scenario_samples: dict | None = None) -> dict:
    """Render existing main-scale results; never open evaluation or references."""
    output = Path(output)
    predictions_path, cache_path = output / "predictions/index.json", output / "cache/index.json"
    selected = [record for record in _read_json(predictions_path)
                if record["scale_px"] == 48 and record["sampler"] == "grid"]
    if not selected:
        raise ValueError("No saved grid48 predictions to display")
    cache = {group["group_id"]: group for group in _read_json(cache_path)}
    samples, runs, results, backgrounds = {}, {}, [], {}
    background_dir = output / "gallery/backgrounds"
    background_dir.mkdir(parents=True, exist_ok=True)
    for entry in selected:
        sample_id = entry["sample_id"]
        group = cache[entry["cache_group"]]
        if sample_id not in samples:
            rows = _read_json(output / "cache" / entry["cache_group"] / "rows.json.gz")
            record, arrays = load_sample(Path(group["analysis"]), sample_id)
            encoded, scaling = _display_png(arrays)
            filename = hashlib.sha256(sample_id.encode()).hexdigest()[:20] + ".png"
            path = background_dir / filename
            path.write_bytes(encoded)
            backgrounds[str(path.relative_to(output))] = file_hash(path)
            samples[sample_id] = dict(
                id=sample_id, kind=entry["kind"], frame_number=record.get("frame_number"),
                width=int(arrays["image"].shape[1]), height=int(arrays["image"].shape[0]),
                image="data:image/png;base64," + base64.b64encode(encoded).decode("ascii"),
                image_content_sha256=record["content_sha256"], display=scaling,
                ids=[row["element_id"] for row in rows], xy=[row["raw_edge_xy"] for row in rows],
                measured_support=[bool(row["available"]) for row in rows],
                test_eligible=[row.get("transfer_split") == "test" and bool(row["available"]) for row in rows],
            )
        sample = samples[sample_id]
        folder = output / entry["directory"]
        full = _metrics(folder / "metrics-input.npz", len(sample["xy"]))
        heldout = None
        if entry["evaluation_input"] != "metrics-input.npz":
            heldout = _metrics(folder / entry["evaluation_input"], len(sample["xy"]))
        results.append(dict(sample_id=sample_id, run_id=entry["run_id"], partition=entry["partition"],
                            full=full, heldout=heldout))
        runs[entry["run_id"]] = {key: entry[key] for key in ("run_id", "regime", "family", "latent", "seed")}
    samples_order = sorted(samples, key=lambda key: (
        samples[key]["kind"] != "measurement", samples[key]["frame_number"] or 0, key))
    frozen_path = output / "frozen-predictions.json"
    if scenario_samples and not frozen_path.exists():
        raise ValueError("Named control scenarios require already frozen predictions")
    scenarios = {"ttmapp": next((sid for sid in samples_order if samples[sid]["frame_number"] == 250), None)}
    if scenario_samples:
        if not set(scenario_samples) <= {"single", "boundary", "ttmapp"}:
            raise ValueError("Unknown gallery scenario")
        if any(sid not in samples for sid in scenario_samples.values()):
            raise ValueError("Scenario sample is absent from saved predictions")
        scenarios.update(scenario_samples)
    payload = dict(schema="stmdomains-issue21-gallery-v1", samples=samples, sample_order=samples_order,
                   runs=list(runs.values()), predictions=results, frozen=frozen_path.exists(), scenarios=scenarios,
                   sources=dict(predictions_index_sha256=file_hash(predictions_path),
                                cache_index_sha256=file_hash(cache_path)))
    previews = {}
    # Fixed first training seed for z32, plus the classical baseline: no selection
    # using synthetic truth or TTMAPP quality. Missing runs simply omit a preview.
    preview_runs = [run for run in ("transductive/fft", "transductive/rvae/z32/seed-20261101") if run in runs]
    scenario_labels = {"single": "Pełna sieć", "boundary": "Granica", "ttmapp": "TTMAPP"}
    for scenario, sample_id in scenarios.items():
        if sample_id is None:
            continue
        for run_id in preview_runs:
            prediction = next((record for record in results if record["sample_id"] == sample_id
                               and record["run_id"] == run_id and record["partition"] == "fh4"), None)
            if prediction is None:
                continue
            path = output / "gallery/previews" / f"{scenario}-{run_id.replace('/', '-')}.png"
            _preview_png(samples[sample_id], prediction, path, label=scenario_labels[scenario])
            previews[str(path.relative_to(output))] = file_hash(path)
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    document = _HTML.replace("__GALLERY_DATA__", encoded)
    target = output / "index.html"
    target.write_text(document)
    summary = dict(schema=payload["schema"], samples=len(samples), runs=len(runs), predictions=len(results),
                   primary_scale_px=48, sampler="grid", references_included=False,
                   frozen_predictions_present=frozen_path.exists(), sources=payload["sources"],
                   html=str(target.resolve()), html_bytes=target.stat().st_size,
                   html_sha256=file_hash(target), backgrounds=backgrounds, previews=previews,
                   source_sha256=file_hash(Path(__file__)))
    write_json(output / "gallery/manifest.json", summary)
    return summary


_HTML = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>STM Domains — próba AE / rVAE</title>
<style>
:root{color-scheme:dark;--bg:#10151d;--panel:#18212d;--line:#344255;--text:#edf2f8;--muted:#b3bfd0;--accent:#8ee6d0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}
header,main,footer{max-width:1540px;margin:auto;padding:20px 28px}header{padding-bottom:12px}h1{font-size:27px;margin:0 0 6px;font-weight:650}p{margin:6px 0;color:var(--muted)}
.kicker{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--accent);margin-bottom:8px}.toolbar{display:grid;grid-template-columns:1fr 2.4fr 1fr 1.7fr;gap:12px;margin-bottom:15px}
label{display:block;font-size:12px;color:var(--muted)}select,button,input{font:inherit}select,button{background:#202c3b;color:var(--text);border:1px solid #46576d;border-radius:7px;padding:9px 10px;width:100%;margin-top:4px}button{cursor:pointer;width:auto;margin:0}button:hover{border-color:var(--accent)}button:disabled{opacity:.45;cursor:default}
.controls{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:12px 0}.controls label{font-size:13px;display:flex;gap:8px;align-items:center}.controls input[type=checkbox]{width:16px;height:16px;accent-color:var(--accent)}.controls input[type=range]{width:130px;accent-color:var(--accent)}
.notice{border-left:3px solid var(--accent);background:#1b2b34;padding:10px 14px;min-height:44px;color:#daeaf0;border-radius:3px}.notice.warning{border-color:#efbe65;background:#30291e;color:#f5dfbc}
.panels{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}.panelheader{padding:13px 16px 10px;display:flex;align-items:baseline;justify-content:space-between;gap:8px}.panel h2{font-size:17px;margin:0}.stage{color:var(--muted);font-size:12px}.canvaswrap{background:#090d13;padding:8px;display:flex;justify-content:center;min-height:300px}canvas{width:100%;max-height:610px;object-fit:contain;image-rendering:auto;display:block}.stats{padding:12px 16px;border-top:1px solid var(--line);font-variant-numeric:tabular-nums;min-height:72px}.stats strong{font-weight:650}.stats small{display:block;color:var(--muted);margin-top:3px}
.legend{display:flex;gap:22px;flex-wrap:wrap;padding:14px 0;color:var(--muted);font-size:13px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#77ddaa;margin-right:5px}.cross{font-size:17px;color:#c4cbd4;margin-right:5px}.footerline{display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}.meta{font-size:12px;color:var(--muted);overflow-wrap:anywhere}footer{padding-top:8px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media(max-width:850px){header,main,footer{padding:15px}.toolbar{grid-template-columns:1fr 1fr}.panels{grid-template-columns:1fr}.canvaswrap{min-height:230px}.panelheader{flex-wrap:wrap}}@media(max-width:450px){.toolbar{grid-template-columns:1fr}h1{font-size:23px}}
</style></head><body>
<header><div class="kicker">STM Domains · eksperyment 21</div><h1>Propozycje domen: przed i po odmowach</h1><p>Czy AE i rVAE uczą się cech, które pomagają znaleźć domeny lepiej niż klasyczna tekstura?</p><p>Po lewej są składowe podobieństwa. Po prawej — pozostałe fragmenty po ocenie porządku i spójności. Sama kolorowa składowa nie dowodzi domeny. To podgląd eksperymentu, bez konturów ani pomiaru powierzchni.</p></header>
<main><div class="toolbar">
<label>Protokół<select id="regime"><option value="transfer">Transfer w jednej akwizycji</option><option value="transductive">Transdukcja · cała obecna seria</option></select></label>
<label>Model i ziarno<select id="run"></select></label><label>Podział<select id="partition"><option value="fh4">FH · k = 4</option><option value="mws">Mutex Watershed</option></select></label>
<label>Klatka lub kontrola<select id="sample"></select></label></div>
<div class="controls" id="scenarios"><span class="meta">Scenariusze:</span><button id="scenario-single">Pełna sieć</button><button id="scenario-boundary">Granica</button><button id="scenario-ttmapp">TTMAPP</button></div>
<div class="controls"><button id="previous" aria-label="Poprzednia klatka">← Poprzednia</button><button id="next" aria-label="Następna klatka">Następna →</button>
<label><input type="checkbox" id="heldout"> Tylko osobny graf testowy</label><label><input type="checkbox" id="points" checked> Pokaż punkty</label>
<label>Widoczność punktów<input id="opacity" type="range" min="0.1" max="1" value="0.9" step="0.05"></label></div>
<div id="notice" class="notice" role="status"></div>
<div class="panels"><section class="panel"><div class="panelheader"><h2>Przed odmowami</h2><span class="stage">Składowe podobieństwa</span></div><div class="canvaswrap"><canvas id="before" aria-label="Obraz i propozycje przed odmowami"></canvas></div><div id="beforestats" class="stats"></div></section>
<section class="panel"><div class="panelheader"><h2>Po odmowach</h2><span class="stage">Porządek i spójność</span></div><div class="canvaswrap"><canvas id="after" aria-label="Obraz i kandydaci po odmowach"></canvas></div><div id="afterstats" class="stats"></div></section></div>
<div class="legend"><span><i class="dot"></i>przypisanie do składowej</span><span><b class="cross">×</b>brak przypisania / odmowa</span><span>kolory są lokalne; nie oznaczają typów struktury</span></div>
<div class="footerline"><span id="meta" class="meta"></span><span id="saved" class="meta"></span></div></main>
<footer>Kontrast obrazów: percentyle 2–98 wyłącznie do podglądu. Okna 48 px, krok siatki 16 px w jednostkach odniesienia. Brak ręcznych referencji w tej galerii. Odrzucenie miejsca nie oznacza podłoża ani dowodu nieporządku.</footer>
<script id="data" type="application/json">__GALLERY_DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id);
const images=new Map(), lookup=new Map(data.predictions.map(p=>[`${p.run_id}|${p.partition}|${p.sample_id}`,p]));
let renderSerial=0;
function option(value,label){const o=document.createElement('option');o.value=value;o.textContent=label;return o;}
function runLabel(run){if(run.family==='fft')return 'FFT48 · klasyczny punkt odniesienia';return `${run.family==='rvae'?'rVAE':'AE'} · z${run.latent} · ziarno ${run.seed}`;}
function fillRuns(){const previous=$('run').value;$('run').replaceChildren();const runs=data.runs.filter(r=>r.regime===$('regime').value).sort((a,b)=>{const f={fft:0,ae:1,rvae:2};return(f[a.family]-f[b.family])||(a.latent-b.latent)||(a.seed-b.seed);});for(const run of runs)$('run').append(option(run.run_id,runLabel(run)));if(runs.some(r=>r.run_id===previous))$('run').value=previous;}
function sampleLabel(sample){return sample.kind==='measurement'?`TTMAPP · klatka ${sample.frame_number}`:`Kontrola · ${sample.id}`;}
for(const id of data.sample_order)$('sample').append(option(id,sampleLabel(data.samples[id])));
for(const name of ['single','boundary','ttmapp']){const button=$(`scenario-${name}`),sample=data.scenarios[name];button.disabled=!sample;button.title=sample?'Pokaż zapisany przykład':'Scenariusz kontroli będzie nazwany po zamrożeniu predykcji';button.onclick=()=>{$('sample').value=sample;render();};}
function color(key){let hash=2166136261;for(let i=0;i<key.length;i++){hash^=key.charCodeAt(i);hash=Math.imul(hash,16777619);}return `hsl(${(hash>>>0)%360} 88% 68%)`;}
function imageFor(sample){if(!images.has(sample.id)){images.set(sample.id,new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=reject;image.src=sample.image;}));}return images.get(sample.id);}
function stats(labels,sample,available,heldout){let denominator=0,assigned=0;const components=new Set();for(let i=0;i<labels.length;i++){if(heldout&&!sample.test_eligible[i])continue;if(available[i])denominator++;if(labels[i]>0){assigned++;components.add(labels[i]);}}return{denominator,assigned,components:components.size,all:heldout?sample.test_eligible.filter(Boolean).length:labels.length};}
function draw(canvas,image,sample,labels,available,heldout){canvas.width=Math.max(sample.width,512);canvas.height=Math.round(canvas.width*sample.height/sample.width);const context=canvas.getContext('2d');context.clearRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);if(!$('points').checked)return;const sx=canvas.width/sample.width,sy=canvas.height/sample.height;const canonical=new Map();for(let i=0;i<labels.length;i++){if(labels[i]>0&&(!canonical.has(labels[i])||sample.ids[i]<canonical.get(labels[i])))canonical.set(labels[i],sample.ids[i]);}
for(let i=0;i<sample.xy.length;i++){const[x,y]=sample.xy[i],inside=!heldout||sample.test_eligible[i];context.globalAlpha=Number($('opacity').value)*(inside?1:.17);const px=x*sx,py=y*sy;context.lineWidth=1.4;if(labels[i]>0&&inside){context.beginPath();context.arc(px,py,3.8,0,Math.PI*2);context.fillStyle=color(canonical.get(labels[i]));context.fill();context.strokeStyle='rgba(0,0,0,.75)';context.stroke();}else{context.strokeStyle=available[i]?'#c4cbd4':'#687487';context.beginPath();context.moveTo(px-2.6,py-2.6);context.lineTo(px+2.6,py+2.6);context.moveTo(px-2.6,py+2.6);context.lineTo(px+2.6,py-2.6);context.stroke();}}context.globalAlpha=1;}
function showStats(target,value,before){target.replaceChildren();const strong=document.createElement('strong');const percent=value.denominator?`${(100*value.assigned/value.denominator).toFixed(1)}%`:'—';strong.textContent=`${before?'Składowe':'Kandydaci domen'}: ${value.components} · przypisano ${value.assigned} / ${value.denominator} (${percent})`;const detail=document.createElement('small');detail.textContent=`Mianownik: dostępne miejsca z pełnym wsparciem w wybranym zakresie. Wszystkie miejsca zakresu: ${value.all}.`;target.append(strong,detail);}
async function render(){const serial=++renderSerial;const sample=data.samples[$('sample').value],run=$('run').value,method=$('partition').value;const prediction=lookup.get(`${run}|${method}|${sample.id}`);const transfer=$('regime').value==='transfer'&&sample.kind==='measurement';const heldoutAvailable=Boolean(prediction&&prediction.heldout);$('heldout').disabled=!heldoutAvailable;if(!heldoutAvailable)$('heldout').checked=false;const heldout=$('heldout').checked&&heldoutAvailable;const warning=transfer&&!heldout;$('notice').className='notice'+(warning?' warning':'');
if(!prediction){$('notice').textContent='Brak zapisanego wyniku dla wybranego modelu i obrazu.';return;}
if(heldout){$('notice').textContent=sample.test_eligible.some(Boolean)?'Osobny graf wyłącznie z dostępnych okien testowych. Pozostałe miejsca są przyciemnione; jedna akwizycja nie potwierdza generalizacji.':'Ta klatka nie zawiera miejsc należących do części testowej. Brak wyniku testowego jest niedostępnością, nie zerowym błędem.';}
else if(warning){$('notice').textContent='Pełna klatka: kontekst do podglądu. Ocena transferu korzysta z osobnego grafu testowego; włącz przełącznik, aby zobaczyć ten wynik.';}
else if($('regime').value==='transductive'){$('notice').textContent='Transdukcja: reprezentacja i reguły dopasowane do całej obecnej serii. To opis tego zakresu, bez deklaracji generalizacji.';}
else{$('notice').textContent='Kontrola syntetyczna: zamrożony model i reguły z części uczącej. Pokazano wyłącznie predykcję, bez prawdy odniesienia.';}
const result=heldout?prediction.heldout:prediction.full;const image=await imageFor(sample);if(serial!==renderSerial)return;draw($('before'),image,sample,result.before,result.available,heldout);draw($('after'),image,sample,result.after,result.available,heldout);showStats($('beforestats'),stats(result.before,sample,result.available,heldout),true);showStats($('afterstats'),stats(result.after,sample,result.available,heldout),false);
$('meta').textContent=`${sampleLabel(sample)} · ${sample.width} × ${sample.height} px · ${run} / ${method}`;$('saved').textContent=`${data.samples?Object.keys(data.samples).length:0} obrazów · ${data.runs.length} przebiegów · ${data.frozen?'zapisane predykcje zamrożone':'podgląd przed zamrożeniem'}`;
const position=data.sample_order.indexOf(sample.id);$('previous').disabled=position===0;$('next').disabled=position===data.sample_order.length-1;window.galleryState={sample:sample.id,run,method,heldout,before:stats(result.before,sample,result.available,heldout),after:stats(result.after,sample,result.available,heldout)};}
$('regime').addEventListener('change',()=>{fillRuns();render();});for(const id of ['run','sample','partition','heldout','points','opacity'])$(id).addEventListener('input',render);
function move(delta){const index=data.sample_order.indexOf($('sample').value);const next=Math.max(0,Math.min(data.sample_order.length-1,index+delta));$('sample').value=data.sample_order[next];render();}
$('previous').onclick=()=>move(-1);$('next').onclick=()=>move(1);document.addEventListener('keydown',event=>{if(event.target.tagName==='SELECT'||event.target.tagName==='INPUT')return;if(event.key==='ArrowRight')move(1);if(event.key==='ArrowLeft')move(-1);});fillRuns();render();
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".scratch/autoencoder-21"))
    scenarios = parser.add_mutually_exclusive_group()
    scenarios.add_argument("--scenario-map", type=Path,
                           help="After freezing: JSON mapping single/boundary/ttmapp to saved sample IDs")
    scenarios.add_argument("--control-manifest", type=Path,
                           help="After freezing: name fixed seed-920001 scenarios using control metadata only")
    args = parser.parse_args()
    scenario_samples = (_control_scenarios(args.output, args.control_manifest) if args.control_manifest
                        else _read_json(args.scenario_map) if args.scenario_map else None)
    summary = build_gallery(args.output, scenario_samples=scenario_samples)
    print(json.dumps({key: summary[key] for key in ("html", "samples", "runs", "predictions", "html_bytes")}, indent=2))


if __name__ == "__main__":
    main()
