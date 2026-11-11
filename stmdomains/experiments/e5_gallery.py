"""Offline E5 comparison viewer for already computed domains and support masks.

The viewer changes no predictions or metrics. Source molecule coordinates stay
fixed; extracted patch centers and raw support boxes are separate overlays.
Index and per-run payloads use local JavaScript files to work under file://.

E5_DATA stores samples (E1 rows), runs, condition metadata, contexts and variants.
A condition has id/label/baseline_id/scales/centering/readout; only conditions
present in the selected E5_RUN_DATA are offered. Each run supplies scope, graph,
fixed gate_source (including its availability), and conditions with patch centers,
per-scale support, own availability and contexts.common/own. Each context supplies
comparison_available, optional scope, before and variants, plus a nested baseline with those same
fields. Baseline results are therefore matched to the selected contrast group.
The browser renders these saved arrays and never recomputes graph partitions.
run.pixel_spacing_xy converts reference-pixel scales and margins into raw image
coordinates: width/spacing_x and height/spacing_y. Source centers stay in raw xy.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re


def write_gallery(path: Path, data: dict | None = None, *, data_script="gallery-data.js"):
    """Write a standalone viewer; optionally embed a small technical data index."""
    if data is None:
        if (not isinstance(data_script, str) or not re.fullmatch(r"[\w./-]+", data_script)
                or data_script.startswith("/") or ".." in data_script.split("/")):
            raise ValueError("Expected a relative local index script")
        source = f'<script src="{html.escape(data_script, quote=True)}"></script>'
    else:
        if not data.get("samples") or not data.get("runs"):
            raise ValueError("Expected nonempty samples and runs")
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        source = f"<script>window.E5_DATA={payload};</script>"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML.replace("__INDEX__", source), encoding="utf-8")


_HTML = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>E5 — lokalność, skala i centrowanie</title>
<style>
:root{color-scheme:dark;--bg:#101721;--card:#192431;--line:#425167;--text:#eff4fa;--muted:#bcc9d8;--accent:#92dfca}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}
main{max-width:1480px;margin:auto;padding:20px}h1{font-size:25px;margin:0 0 8px}h2{font-size:17px;margin:0 0 8px}p{margin:7px 0}
.muted,small{color:var(--muted)}a{color:var(--accent)}button,select{font:inherit;color:inherit;background:#233346;border:1px solid #6d819a;border-radius:5px;padding:7px 9px}
button{cursor:pointer}button:disabled{opacity:.45;cursor:default}button:hover:enabled{border-color:var(--accent)}input{accent-color:var(--accent)}
.controls{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin:13px 0}.choice{flex:1;min-width:150px}.choice.wide{flex:2;min-width:230px}.choice select{display:block;width:100%;margin-top:3px}
#frame{width:155px;vertical-align:middle}.layers{display:flex;gap:16px;flex-wrap:wrap;margin:10px 0}
#notice{white-space:pre-line;border-left:3px solid #efc47e;background:#302b23;padding:10px 13px;margin:12px 0}#status{color:var(--accent);min-height:22px}
.comparison{display:grid;grid-template-columns:1fr 1fr;gap:16px}.image-panel{min-width:0}.stage{background:#080d13;border:1px solid var(--line);padding:10px;display:flex;justify-content:center;align-items:center;min-height:200px}
canvas{display:block;max-width:100%;max-height:530px;width:auto;height:auto;cursor:crosshair}.counts{min-height:22px;color:var(--accent)}.metrics{display:flex;gap:5px 16px;flex-wrap:wrap;margin-top:8px;font-size:13px}
#changes{padding:9px 12px;background:var(--card);margin:12px 0}.details{display:grid;grid-template-columns:minmax(400px,1fr) 360px;gap:16px;margin-top:16px}
.card{background:var(--card);border:1px solid var(--line);padding:14px;min-width:0;overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:left;overflow-wrap:anywhere}th{color:var(--muted)}
.bad{color:#ffb4ae}.good{color:#9fe2bf}.previews{display:grid;grid-template-columns:1fr 1fr;gap:10px}.previews img{display:block;width:100%;height:auto;image-rendering:pixelated;background:#080d13;border:1px solid var(--line)}
#preview-source,#source{font-size:12px;overflow-wrap:anywhere;color:var(--muted)}#preview-images[hidden]{display:none}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:13px;margin:10px 0}.dot{display:inline-block;width:11px;height:11px;border-radius:50%;border:2px solid #acb5c2;margin-right:4px}.assignment{border-color:#ffe08a}.relation{border-color:#ff976d;border-radius:0;transform:rotate(45deg)}
@media(max-width:900px){.details{grid-template-columns:1fr}.choice{min-width:135px!important}main{padding:12px}}
@media(max-width:650px){.comparison{grid-template-columns:1fr}.details{display:block}.card{margin-top:12px}}

.details{grid-template-columns:1fr} .support-key{font-family:monospace} .cross{color:#e9b4ff}
.legend .mark{font-size:17px;line-height:1;vertical-align:middle;margin-right:4px}
</style></head><body><main>
<h1>E5 — lokalność, skala i centrowanie</h1>
<p class="muted">Ten sam pełny obraz źródłowy i te same węzły grafu w obu panelach.
Zmienia się odczyt cech lub położenie wycinka; punkty domen pozostają w pozycjach źródłowych.
Wagi enkodera są zamrożone. Wyniki i miary pochodzą z zapisanej próby.</p>
<div class="controls"><label class="choice wide">Źródło / klatka<select id="sample"></select></label>
<button id="prev">← Poprzedni</button><button id="next">Następny →</button>
<label>Przykład <input id="frame" type="range" min="0" step="1"><span id="counter"></span></label></div>
<div class="controls"><label class="choice">Miejsca<select id="sampler"></select></label>
<label class="choice">Reżim<select id="regime"></select></label>
<label class="choice">Model / ziarno<select id="model"></select></label>
<label class="choice">Podział<select id="partition"></select></label></div>
<div class="controls"><label class="choice wide">Kontrast<select id="condition"></select></label>
<label class="choice">Dostępny kontekst<select id="context"></select></label>
<label class="choice wide">Bramka<select id="variant"></select></label></div>
<div class="layers"><label><input id="points" type="checkbox" checked> Punkty i domeny</label>
<label><input id="support" type="checkbox" checked> Okna wskazanego punktu</label>
<label><input id="before" type="checkbox"> Propozycje przed odmowami</label><small id="dimensions"></small></div>
<div id="status" role="status">Wczytywanie…</div><div id="notice"></div>
<div class="comparison"><section class="image-panel"><h2 id="base-title">Odczyt bazowy</h2>
<p class="counts" id="base-counts"></p><div class="stage"><canvas id="base-canvas" aria-label="Obraz źródłowy, domeny bazowe"></canvas></div><div class="metrics" id="base-metrics"></div></section>
<section class="image-panel"><h2 id="changed-title">Wariant</h2>
<p class="counts" id="changed-counts"></p><div class="stage"><canvas id="changed-canvas" aria-label="Obraz źródłowy, domeny wariantu"></canvas></div><div class="metrics" id="changed-metrics"></div></section></div>
<div class="legend"><span><i class="dot"></i>Szary: odmowa przy dostępnym kontekście</span>
<span><b class="mark cross">×</b>Brak pełnego kontekstu / cech</span>
<span><b class="mark" style="color:#f8d88a">□</b>Wyłączony przez wspólny kontekst</span>
<span><b class="mark" style="color:#9fbdff">△</b>Brak kontekstu stałej bramki 48 px</span><span>Przygaszony: poza zakresem</span></div>
<div class="legend"><span id="scale32-key" class="support-key" style="color:#81dcf4">32 px</span>
<span id="scale48-key" class="support-key" style="color:#f4d47e">48 px</span><span id="scale64-key" class="support-key" style="color:#f5a4de">64 px</span>
<span>Linia ciągła: nominalny wycinek; przerywana: dodatkowy margines</span>
<span>Krzyżyk: centrum wycinka; biały okrąg: źródłowy węzeł</span></div>
<div id="changes"></div><p id="source"></p>
<div class="details"><section class="card"><h2>Wybrany punkt — położenie, wsparcie i decyzje</h2><div id="detail"></div></section></div>
</main>__INDEX__<script>'use strict';
const $ = id => document.getElementById(id);
const imageCache = new Map();
let data, samples, runIndex, conditionIndex, sampleIndex = 0;
let currentMeta = null, currentRun = null, currentImage = null, currentRows = [];
let selectedPoint = null, epoch = 0;
let baseCondition, changedCondition, baseView, changedView, baseVariant, changedVariant;
let baseLabels = [], changedLabels = [], baselineId = null;
const terms = {centers:'Centra molekuł',grid:'Siatka — nie molekuły',
  transfer:'Transfer historyczny',transductive:'Transdukcja',fh4:'FH (k=4)',mws:'MWS'};
const families = {ae:'AE',rvae_full:'rVAE · treść + kąt',rvae_content:'rVAE · treść',fft:'FFT'};
const variantNames = {H_M1:'H_M1 · stałe H, bez progów ACF/widma',
  A_fixed_M1:'A_fixed_M1 · pełna stała bramka'};
const contextNames = {common:'Wspólny pełny kontekst',own:'Własny dostępny kontekst'};
const scaleColors = {'32':'#81dcf4','48':'#f4d47e','64':'#f5a4de'};
const format = (value, digits=4) => value === null || value === undefined ||
  typeof value === 'number' && !Number.isFinite(value) ? 'brak danych' :
  typeof value === 'number' ? Number(value.toFixed(digits)).toString() : String(value);
const percent = value => Number.isFinite(value) ? (100 * value).toFixed(1)+'%' : 'brak danych';
const yes = value => value === undefined || value === null ? 'brak danych' : value ? 'tak' : 'nie';
const positive = value => Number.isInteger(value) && value > 0 ? value : 0;
const modelKey = run => JSON.stringify([run.family,run.seed ?? null]);
const xyText = xy => Array.isArray(xy) ? xy.map(value=>format(value,3)).join(', ') : 'brak danych';
function localPath(value) {
  return typeof value === 'string' && !/^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i.test(value)
    && !value.split('/').includes('..');
}
function errorState(error) {
  $('status').textContent = 'Błąd galerii: '+error.message;
  window.e5State = {...(window.e5State||{}),ready:false,error:error.message};
  console.error(error.message);
}
function options(id, items, preferred) {
  const element=$(id), previous=preferred ?? element.value;
  element.replaceChildren();
  for(const [value,title] of items) {
    const option=document.createElement('option');
    option.value=value;option.textContent=title;element.appendChild(option);
  }
  if(items.some(([value])=>String(value)===previous))element.value=previous;
  return element.value;
}
function unique(rows, key, title) {
  const seen=new Set();
  return rows.flatMap(row=>{const value=String(key(row));if(seen.has(value))return [];
    seen.add(value);return [[value,title(row)]];});
}
function imageFor(path) {
  if(!localPath(path))return Promise.reject(Error('Nieprawidłowa ścieżka obrazu'));
  if(!imageCache.has(path))imageCache.set(path,new Promise((resolve,reject)=>{
    const image=new Image();image.onload=()=>resolve(image);
    image.onerror=()=>reject(Error('Nie można odczytać obrazu: '+path));image.src=path;
  }));
  return imageCache.get(path);
}
function runFor(meta) {
  if(meta.conditions)return Promise.resolve(meta);
  if(!localPath(meta.path))return Promise.reject(Error('Nieprawidłowa ścieżka przebiegu'));
  return new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src=meta.path;
    script.onload=()=>{script.remove();const run=window.E5_RUN_DATA;
      if(!run||run.id!==meta.id)reject(Error('Niezgodny identyfikator przebiegu'));else resolve(run);};
    script.onerror=()=>{script.remove();reject(Error('Nie można odczytać przebiegu'));};
    document.head.appendChild(script);
  });
}
function checkVector(values,n,name) {
  if(!Array.isArray(values)||values.length!==n)throw Error('Nieprawidłowa długość '+name);
}
function spacingFor(run=currentRun) {return run?.pixel_spacing_xy??samples[sampleIndex].pixel_spacing_xy??[1,1];}
function referenceUnit() {return spacingFor().some(value=>value!==1)?'px odniesienia':'px';}
function conditionLabel(meta) {return referenceUnit()==='px'?meta.label:meta.label.replaceAll(' px',' px odniesienia');}
function supportMargin() {return data.support_margin_reference_px??data.support_margin_raw_px??3;}
function validate(run, rows) {
  const n=rows.length,spacing=spacingFor(run);
  if(!Array.isArray(spacing)||spacing.length!==2||!spacing.every(value=>Number.isFinite(value)&&value>0))
    throw Error('Nieprawidłowe pixel_spacing_xy');
  checkVector(run.scope,n,'scope');
  for(const row of rows)if(!Array.isArray(row.xy)||row.xy.length!==2||!row.xy.every(Number.isFinite))
    throw Error('Nieprawidłowe współrzędne źródłowe');
  for(const meta of data.conditions) {
    const condition=run.conditions?.[meta.id];if(!condition)continue;
    if(!run.conditions[meta.baseline_id||meta.id])throw Error('Brak warunku bazowego');
    checkVector(condition.patch_centers_xy,n,meta.id+'/patch_centers_xy');
    checkVector(condition.available,n,meta.id+'/available');
    for(const xy of condition.patch_centers_xy)if(!Array.isArray(xy)||xy.length!==2||!xy.every(Number.isFinite))
      throw Error('Nieprawidłowe centrum wycinka');
    for(const scale of meta.scales)checkVector(condition.support_by_scale?.[scale],n,meta.id+'/support/'+scale);
    for(const context of data.contexts) {
      const view=condition.contexts?.[context];if(!view)throw Error('Brak kontekstu '+context);
      checkVector(view.comparison_available,n,meta.id+'/'+context+'/comparison_available');
      if(!view.baseline)throw Error('Brak sparowanego baseline');
      for(const item of [view,view.baseline]) {
        checkVector(item.comparison_available,n,'comparison_available');
        if(item.scope!==undefined)checkVector(item.scope,n,'context scope');
        if(item.feature_valid!==undefined)checkVector(item.feature_valid,n,'feature_valid');
        checkVector(item.before,n,'before');
        for(const stage of data.variants)checkVector(item.variants?.[stage]?.labels,n,'labels/'+stage);
      }
    }
  }
  for(const key of ['available','hard','full_gate','acf','ratio','energy'])checkVector(run.gate_source?.[key],n,'gate_source/'+key);
}
function controls() {
  let candidates=runIndex.filter(run=>run.sample_id===samples[sampleIndex].id);
  const sampler=options('sampler',unique(candidates,run=>run.sampler,run=>terms[run.sampler]||run.sampler),$('sampler').value||'centers');
  candidates=candidates.filter(run=>run.sampler===sampler);
  const regime=options('regime',unique(candidates,run=>run.regime,run=>terms[run.regime]||run.regime),$('regime').value||'transductive');
  candidates=candidates.filter(run=>run.regime===regime);
  const model=options('model',unique(candidates,modelKey,run=>(families[run.family]||run.family)+(run.seed==null?'':' · '+run.seed)),$('model').value||'["ae",20261101]');
  candidates=candidates.filter(run=>modelKey(run)===model);
  const partition=options('partition',unique(candidates,run=>run.partition,run=>terms[run.partition]||run.partition),$('partition').value||'fh4');
  candidates=candidates.filter(run=>run.partition===partition);
  if(candidates.length!==1)throw Error('Wybór nie wskazuje jednego przebiegu');
  return candidates[0];
}
async function chooseRun() {
  const token=++epoch;currentRun=null;currentImage=null;selectedPoint=null;
  $('status').textContent='Wczytywanie porównania…';$('detail').textContent='Wczytywanie…';
  window.e5State={ready:false,sample:samples[sampleIndex].id};
  for(const id of ['base-canvas','changed-canvas'])$(id).getContext('2d').clearRect(0,0,$(id).width,$(id).height);
  try {
    currentMeta=controls();const meta=currentMeta,sample=samples[sampleIndex];
    const [run,image]=await Promise.all([runFor(meta),imageFor(sample.image)]);
    if(token!==epoch)return;
    const rows=sample.rows?.[meta.sampler];if(!Array.isArray(rows))throw Error('Brak miejsc samplera');
    validate(run,rows);
    if(sample.width&&sample.width!==image.naturalWidth||sample.height&&sample.height!==image.naturalHeight)
      throw Error('Niezgodne wymiary obrazu');
    currentRun=run;currentImage=image;currentRows=rows;
    const offered=data.conditions.filter(meta=>run.conditions[meta.id]);
    options('condition',offered.map(meta=>[meta.id,conditionLabel(meta)]),offered.some(meta=>meta.id===$('condition').value)?$('condition').value:offered.find(meta=>meta.id==='scale_multi')?.id);
    const initialView=run.conditions[$('condition').value].contexts[$('context').value];
    const first=initialView.comparison_available.findIndex((valid,index)=>valid&&scopeFor(initialView)[index]);
    selectedPoint=first>=0?first:rows.length?0:null;render();
  } catch(error) {if(token===epoch)errorState(error);}
}
function palette(labels) {
  const members=new Map(),result=new Map([[0,'#acb5c2']]);
  labels.forEach((label,index)=>{if(label>0){if(!members.has(label))members.set(label,[]);
    members.get(label).push(currentRows[index].element_id??String(index));}});
  for(const [label,ids] of members) {
    let hash=2166136261;
    for(const character of ids.sort().join('|'))hash=Math.imul(hash^character.charCodeAt(0),16777619)>>>0;
    hash=Math.imul(hash^(hash>>>16),0x85ebca6b);hash=Math.imul(hash^(hash>>>13),0xc2b2ae35);
    hash=(hash^(hash>>>16))>>>0;result.set(label,`hsl(${hash%360} 79% 69%)`);
  }
  return result;
}
function scopeFor(view) {return view.scope??currentRun.scope;}
function contextStatus(condition,view,index) {
  if(!scopeFor(view)[index])return 'outside';
  if(!condition.available[index])return 'unavailable';
  if(!view.comparison_available[index])return 'excluded';
  return 'available';
}
function drawSupport(ctx,condition,meta) {
  if(selectedPoint===null||!$('support').checked)return;
  const [x,y]=condition.patch_centers_xy[selectedPoint],source=currentRows[selectedPoint].xy;
  const margin=supportMargin(),[sx,sy]=spacingFor();
  for(const scale of [...meta.scales].sort((a,b)=>b-a)) {
    ctx.strokeStyle=scaleColors[scale]||'#fff';ctx.lineWidth=.7;ctx.setLineDash([]);
    ctx.strokeRect(x-scale/(2*sx),y-scale/(2*sy),scale/sx,scale/sy);
    ctx.setLineDash([2,1.8]);
    ctx.strokeRect(x-(scale/2+margin)/sx,y-(scale/2+margin)/sy,(scale+2*margin)/sx,(scale+2*margin)/sy);
  }
  ctx.setLineDash([]);ctx.strokeStyle='#fff';ctx.lineWidth=.9;
  ctx.beginPath();ctx.moveTo(source[0],source[1]);ctx.lineTo(x,y);ctx.stroke();
  ctx.beginPath();ctx.moveTo(x-3,y);ctx.lineTo(x+3,y);ctx.moveTo(x,y-3);ctx.lineTo(x,y+3);ctx.stroke();
  ctx.beginPath();ctx.arc(source[0],source[1],5,0,Math.PI*2);ctx.stroke();
}
function draw(id,labels,condition,view,meta) {
  const canvas=$(id),image=currentImage,scale=Math.min(3,1600/Math.max(image.naturalWidth,image.naturalHeight));
  canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);
  const ctx=canvas.getContext('2d');ctx.scale(canvas.width/image.naturalWidth,canvas.height/image.naturalHeight);
  ctx.drawImage(image,0,0);const colors=palette(labels);
  if($('points').checked)currentRows.forEach((row,index)=>{
    const [x,y]=row.xy,status=contextStatus(condition,view,index);
    const missingFeature=status==='available'&&view.feature_valid?.[index]===false;
    const missingGate=status==='available'&&!$('before').checked&&!currentRun.gate_source.available[index];
    ctx.globalAlpha=status==='outside'?.3:1;ctx.lineWidth=.9;
    ctx.strokeStyle=status==='unavailable'||missingFeature?'#e9b4ff':status==='excluded'?'#f8d88a':missingGate?'#9fbdff':colors.get(labels[index]);
    ctx.beginPath();
    if(status==='unavailable'||missingFeature){ctx.moveTo(x-2,y-2);ctx.lineTo(x+2,y+2);ctx.moveTo(x-2,y+2);ctx.lineTo(x+2,y-2);}
    else if(status==='excluded')ctx.rect(x-2,y-2,4,4);
    else if(missingGate){ctx.moveTo(x,y-3);ctx.lineTo(x+2.6,y+2);ctx.lineTo(x-2.6,y+2);ctx.closePath();}
    else ctx.arc(x,y,currentMeta.sampler==='centers'?1.9:1.5,0,Math.PI*2);
    ctx.stroke();ctx.globalAlpha=1;
  });
  drawSupport(ctx,condition,meta);
}
function tableRow(table,values,heading=false) {
  const row=document.createElement('tr');
  for(const value of values){const cell=document.createElement(heading?'th':'td');cell.textContent=value;row.appendChild(cell);}
  table.appendChild(row);
}
function pointDetails() {
  const panel=$('detail');panel.replaceChildren();
  if(selectedPoint===null){panel.textContent=currentRows.length?'Kliknij punkt na dowolnym panelu.':'Brak miejsc samplera; nie ma wycinka do porównania.';return;}
  const index=selectedPoint,row=currentRows[index],table=document.createElement('table');
  const baseMeta=conditionIndex.get(baselineId),changedMeta=conditionIndex.get($('condition').value);
  const values=(key)=>[baseCondition[key]?.[index],changedCondition[key]?.[index]];
  tableRow(table,['Pomiar / warunek','Odczyt bazowy','Wariant','Znaczenie'],true);
  tableRow(table,['ID węzła',row.element_id??String(index),row.element_id??String(index),'stały węzeł i graf']);
  tableRow(table,['Pozycja źródłowa raw [x,y]',xyText(row.xy),xyText(row.xy),'punkt domeny nie przesuwa się']);
  tableRow(table,['Centrum wycinka raw [x,y]',...values('patch_centers_xy').map(xyText),'pozycja ekstrakcji']);
  tableRow(table,['Przesunięcie wycinka [dx,dy]',...values('patch_centers_xy').map(xy=>xyText(xy.map((v,j)=>v-row.xy[j]))),'przesunięcie względem źródłowego węzła']);
  tableRow(table,['Domena w widoku',baseLabels[index]?'D'+baseLabels[index]:'brak',changedLabels[index]?'D'+changedLabels[index]:'brak','ID domen nie mierzy zmiany']);
  tableRow(table,['W przestrzennym zakresie',yes(scopeFor(baseView)[index]),yes(scopeFor(changedView)[index]),'zakres właściwy dla warunku i kontekstu']);
  for(const scale of [32,48,64]) {
    const cell=(condition,meta)=>{const measured=condition.support_by_scale[scale];
      if(!Array.isArray(measured))return 'nie obliczano';
      return yes(measured[index])+(meta.scales.includes(scale)?'':' · nieużywana');};
    const [sx,sy]=spacingFor(),margin=supportMargin();
    tableRow(table,['Pełne wsparcie '+scale+' '+referenceUnit(),cell(baseCondition,baseMeta),cell(changedCondition,changedMeta),
      'okno '+format(scale/sx)+'×'+format(scale/sy)+' px raw; margines '+format(margin/sx)+'×'+format(margin/sy)+' px raw z każdej strony']);
  }
  tableRow(table,['Własny pełny kontekst geometryczny',...values('available').map(yes),'nie jest decyzją bramki']);
  tableRow(table,['Dostępny odczyt cech w tym kontekście',yes(baseView.feature_valid?.[index]),yes(changedView.feature_valid?.[index]),'osobno od pomiarów bramki']);
  tableRow(table,['Dopuszczony kontekst porównania',yes(baseView.comparison_available[index]),yes(changedView.comparison_available[index]),contextNames[$('context').value]]);
  const gate=currentRun.gate_source,source=gate.label||conditionIndex.get(gate.condition_id)?.label||(gate.condition_id==='exact48'?'źródłowe centrum · 48 px':gate.condition_id)||'zapisane bazowe pomiary';
  tableRow(table,['Kontekst bazowej bramki 48 px',yes(gate.available[index]),yes(gate.available[index]),'brak pomiaru nie jest odmową struktury']);
  const gateDecision=values=>gate.available[index]?yes(values[index]):'brak pomiaru';
  tableRow(table,['Twarda bramka H',gateDecision(gate.hard),gateDecision(gate.hard),'stałe źródło: '+source]);
  tableRow(table,['ACF > '+format(currentRun.threshold,6),format(gate.acf[index],6),format(gate.acf[index],6),$('variant').value==='H_M1'?'decyzja ACF wyłączona':'stała decyzja bazowa']);
  tableRow(table,['Drugi kierunek widma ≥0,25',format(gate.ratio[index],6),format(gate.ratio[index],6),$('variant').value==='H_M1'?'decyzja widma wyłączona':'stała decyzja bazowa']);
  tableRow(table,['Energia',format(gate.energy[index],8),format(gate.energy[index],8),'składowa H']);
  tableRow(table,['Pełna bramka A/S/H',gateDecision(gate.full_gate),gateDecision(gate.full_gate),$('variant').value==='H_M1'?'progi A/S wyłączone':'stała bramka aktywna']);
  tableRow(table,['Minimum komponentu',String(currentRun.min_size),String(currentRun.min_size),'aktywne po masce']);
  panel.appendChild(table);
  const note=document.createElement('p');note.className='muted';
  note.textContent='Brak pełnego kontekstu, wyłączenie przez wspólne wsparcie, brak pomiaru bazowej bramki i jej odmowa są odrębnymi stanami. Stałe pomiary bramki nie opisują nowego, przesuniętego wycinka. Kontury pokazują obszar ekstrakcji w pikselach raw, nie granicę domeny ani dokładny receptive field neuronu.';
  panel.appendChild(note);
}
function metrics(id,variant) {
  const panel=$(id);panel.replaceChildren();
  if($('before').checked){panel.textContent='Propozycja przed odmowami; miary końcowe ukryte.';return;}
  for(const [name,value] of [['Pokrycie dodatniej referencji',variant.coverage],['Scalenia par',variant.merge_rate],['Podziały par',variant.split_rate]]) {
    const span=document.createElement('span');span.textContent=name+': '+percent(value);panel.appendChild(span);
  }
}
function contextCounts(condition,view) {
  const result={available:0,unavailable:0,excluded:0,outside:0,gate_missing:0,feature_missing:0};
  currentRows.forEach((_,index)=>{const status=contextStatus(condition,view,index);result[status]++;
    if(status==='available'&&!currentRun.gate_source.available[index])result.gate_missing++;
    if(status==='available'&&view.feature_valid?.[index]===false)result.feature_missing++;});return result;
}
function render() {
  if(!currentRun||!currentImage)return;
  const conditionId=$('condition').value,context=$('context').value,stage=$('variant').value;
  const changedMeta=conditionIndex.get(conditionId);baselineId=changedMeta.baseline_id||conditionId;
  const baseMeta=conditionIndex.get(baselineId);baseCondition=currentRun.conditions[baselineId];changedCondition=currentRun.conditions[conditionId];
  changedView=changedCondition.contexts[context];baseView=changedView.baseline||baseCondition.contexts[context];
  baseVariant=baseView.variants[stage];changedVariant=changedView.variants[stage];
  const labels=view=>($('before').checked?view.before:view.variants[stage].labels).map((label,index)=>scopeFor(view)[index]?positive(label):0);
  baseLabels=labels(baseView);changedLabels=labels(changedView);
  draw('base-canvas',baseLabels,baseCondition,baseView,baseMeta);draw('changed-canvas',changedLabels,changedCondition,changedView,changedMeta);
  const assigned=labels=>labels.filter(value=>value>0).length,domains=labels=>new Set(labels.filter(value=>value>0)).size;
  const baseCounts=contextCounts(baseCondition,baseView),changedCounts=contextCounts(changedCondition,changedView);
  const countText=(labels,counts)=>`${assigned(labels)} przypisanych / ${counts.available} z dostępnym kontekstem · ${domains(labels)} domen`;
  $('base-counts').textContent=countText(baseLabels,baseCounts);$('changed-counts').textContent=countText(changedLabels,changedCounts);
  $('base-title').textContent=conditionLabel(baseMeta);$('changed-title').textContent=conditionLabel(changedMeta);
  for(const scale of [32,48,64])$('scale'+scale+'-key').textContent=scale+' '+referenceUnit();
  $('status').textContent=($('before').checked?'Przed odmowami':'Po odmowach')+' · '+contextNames[context]+' · '+variantNames[stage];
  $('dimensions').textContent=`${currentImage.naturalWidth}×${currentImage.naturalHeight} px · ${currentRows.length} ${currentMeta.sampler==='centers'?'centrów':'miejsc siatki'}`;
  const notices=['Punkty i graf pozostają źródłowe. Przesunięcie na siatkę zmienia tylko wycinek; wspólne centrum wycinka nie łączy dwóch węzłów.'];
  if(spacingFor().some(value=>value!==1))notices.push('Obraz przeskalowany: pixel_spacing_xy = ['+spacingFor().map(value=>format(value)).join(', ')+']. Skale i margines są w pikselach odniesienia; kontury w raw mają rozmiar podzielony osobno przez spacing X/Y. Pozycje źródłowe i centra wycinków pozostają raw.');
  if(data.fixture)notices.unshift('ZESTAW TECHNICZNY INTERFEJSU — wymyślone dane, nie wyniki E5.');
  if(currentMeta.sampler==='grid')notices.push('SIATKA: to punkty próbkowania, nie wykryte molekuły.');
  if(samples[sampleIndex].kind==='measurement')notices.push(currentMeta.regime==='transfer'?'Transfer historyczny: dawny lewy pas testowy jednej znanej akwizycji rozwojowej; brak nowego niezależnego testu.':'Transdukcja: dopasowanie korzystało z tej samej akwizycji; klatki nie są niezależnymi testami.');
  notices.push(context==='common'?'Wspólny kontekst: '+(data.common_support_note||'pełne wsparcie wszystkich warunków grupy: '+({map:'odczyt mapy',scale:'skale 32/48/64 i ich połączenie',center:'centrowanie źródłowe i obie siatki'}[changedMeta.contrast]||changedMeta.contrast)):'Własny kontekst: dostępność może różnić się między panelami; różnicy pokrycia nie przypisuj wyłącznie jakości cech.');
  notices.push(stage==='H_M1'?'H_M1: stałe H i minimum; progi ACF/widma są wyłączone diagnostycznie.':'Pełna bramka pozostaje stała; porównanie nie przelicza jej na nowych wycinkach.');
  notices.push('Własne okno 32 px może istnieć bez bazowego kontekstu bramki 48 px. Wtedy widoczna może być tylko propozycja przed bramką; brak pomiaru nie dowodzi braku domeny.');
  if(changedMeta.note)notices.push(changedMeta.note);
  notices.push('Kolor wynika z pełnego składu komponentu; sama zmiana ID nie zmienia koloru. Rozszerzona referencja granic STM nie została dodana.');
  $('notice').textContent=notices.join('\n');
  $('changes').textContent=`Brak własnego kontekstu: bazowe ${baseCounts.unavailable}, wariant ${changedCounts.unavailable}. Wyłączone przez kontekst porównania: ${baseCounts.excluded} / ${changedCounts.excluded}. Brak odczytu cech przy dostępnym kontekście: ${baseCounts.feature_missing} / ${changedCounts.feature_missing}. Brak kontekstu bramki 48 px: ${baseCounts.gate_missing} / ${changedCounts.gate_missing}. Poza zakresem: ${baseCounts.outside} / ${changedCounts.outside}.`;
  $('source').textContent='Źródło obu paneli: '+samples[sampleIndex].image+' · '+(currentMeta.path||'dane osadzone');
  metrics('base-metrics',baseVariant);metrics('changed-metrics',changedVariant);
  window.e5State={ready:true,error:null,sample:samples[sampleIndex].id,index:sampleIndex,run_id:currentMeta.id,
    sampler:currentMeta.sampler,regime:currentMeta.regime,family:currentMeta.family,seed:currentMeta.seed??null,
    partition:currentMeta.partition,condition:conditionId,baseline:baselineId,context,variant:stage,
    before:$('before').checked,points:$('points').checked,support:$('support').checked,
    pixel_spacing_xy:spacingFor(),point_count:currentRows.length,base_assigned:assigned(baseLabels),changed_assigned:assigned(changedLabels),
    base_context:baseCounts,changed_context:changedCounts,selected_point:selectedPoint,
    sample_count:samples.length,run_count:runIndex.length};
  pointDetails();
}
function move(index) {
  sampleIndex=Math.max(0,Math.min(samples.length-1,index));$('sample').value=samples[sampleIndex].id;
  $('frame').value=sampleIndex;$('counter').textContent=` ${sampleIndex+1}/${samples.length}`;
  $('prev').disabled=sampleIndex===0;$('next').disabled=sampleIndex===samples.length-1;chooseRun();
}
try {
  data=window.E5_DATA;
  if(!data?.samples?.length||!data?.runs?.length||!data?.conditions?.length)throw Error('Brak poprawnego indeksu E5');
  samples=data.samples;runIndex=data.runs;conditionIndex=new Map(data.conditions.map(meta=>[meta.id,meta]));
  if(new Set(samples.map(sample=>sample.id)).size!==samples.length||new Set(runIndex.map(run=>run.id)).size!==runIndex.length)
    throw Error('Powtórzone identyfikatory');
  options('sample',samples.map(sample=>[sample.id,sample.kind==='measurement'?'TTMAPP · klatka '+(sample.frame??sample.id):(sample.case||sample.id)+' · '+sample.id]));
  options('condition',data.conditions.map(meta=>[meta.id,meta.label]),data.default_condition||data.conditions.find(meta=>meta.id==='map_full')?.id);
  options('context',data.contexts.map(value=>[value,contextNames[value]||value]),'common');
  options('variant',data.variants.map(value=>[value,variantNames[value]||value]),'H_M1');
  $('frame').max=samples.length-1;
  $('sample').onchange=()=>move(samples.findIndex(sample=>sample.id===$('sample').value));
  $('frame').oninput=()=>move(Number($('frame').value));$('prev').onclick=()=>move(sampleIndex-1);$('next').onclick=()=>move(sampleIndex+1);
  for(const id of ['sampler','regime','model','partition'])$(id).onchange=chooseRun;
  for(const id of ['condition','context','variant','points','support','before'])$(id).onchange=render;
  for(const id of ['base-canvas','changed-canvas'])$(id).onclick=event=>{
    if(!currentRun||!currentImage||!$('points').checked)return;
    const rect=$(id).getBoundingClientRect();
    const x=(event.clientX-rect.left)*currentImage.naturalWidth/rect.width,y=(event.clientY-rect.top)*currentImage.naturalHeight/rect.height;
    let nearest=Infinity,selected=null;
    currentRows.forEach((row,index)=>{const distance=Math.hypot(row.xy[0]-x,row.xy[1]-y);if(distance<nearest){nearest=distance;selected=index;}});
    selectedPoint=nearest<=10*currentImage.naturalWidth/rect.width?selected:null;render();
  };
  move(Math.max(0,samples.findIndex(sample=>sample.id==='ttmapp-259')));
} catch(error) {errorState(error);}

</script></body></html>'''
