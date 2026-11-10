"""Write an offline E1 viewer; load one prepared run at a time, without inference.

The index script defines E1_DATA={samples: [...], runs: [...]}.
Run index entries contain id/sample_id/sampler/regime/family/seed/partition/path.
Each relative run script defines E1_RUN_DATA with that id and prepared arrays.
Inline run payloads are also accepted for small technical fixtures.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import re


def write_gallery(path: Path, data: dict | None = None, *, data_script="gallery-data.js") -> None:
    """Write HTML beside its local image/index/run files, never recomputing results."""
    if data is None:
        if (not isinstance(data_script, str) or not re.fullmatch(r"[\w./-]+", data_script)
                or data_script.startswith("/") or ".." in data_script.split("/")):
            raise ValueError("Expected a relative local index script")
        source = f'<script src="{html.escape(data_script, quote=True)}"></script>'
    else:
        if not data.get("samples") or not data.get("runs"):
            raise ValueError("Expected nonempty samples and run index")
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        source = f"<script>window.E1_DATA={payload};</script>"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML.replace("__INDEX_SCRIPT__", source), encoding="utf-8")


_HTML = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E1 — domeny i przyczyny odmów</title>
<style>
:root{color-scheme:dark;--bg:#101721;--card:#192431;--line:#425167;--text:#eff4fa;--muted:#bcc9d8;--accent:#92dfca}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}
main{max-width:1420px;margin:auto;padding:20px}h1{font-size:25px;line-height:1.25;margin:0 0 8px}h2{font-size:16px;margin:0 0 9px}
p{margin:7px 0}.muted,small{color:var(--muted)}.controls{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin:13px 0}
label.choice{flex:1;min-width:150px}label.wide{flex:2;min-width:230px}.choice select{display:block;width:100%;margin-top:3px}
button,select{font:inherit;color:var(--text);background:#233346;border:1px solid #6d819a;border-radius:5px;padding:7px 9px}
button{cursor:pointer}button:disabled{opacity:.4;cursor:default}button:hover:enabled{border-color:var(--accent)}
input{accent-color:var(--accent)}#frame{width:160px;vertical-align:middle}.layers{display:flex;gap:16px;flex-wrap:wrap;margin:10px 0}
.workspace{display:grid;grid-template-columns:minmax(300px,1fr) 340px;gap:16px;align-items:start}
.stage{background:#080d13;border:1px solid var(--line);padding:10px;display:flex;justify-content:center;align-items:center;min-height:220px}
canvas{display:block;max-width:100%;max-height:560px;width:auto;height:auto;cursor:crosshair}
aside{background:var(--card);border:1px solid var(--line);padding:14px;max-height:650px;overflow:auto}
#notice{border-left:3px solid #efc47e;background:#302b23;padding:10px 13px;white-space:pre-line;margin:12px 0}
#status{min-height:22px;color:var(--accent)}#legend{display:flex;flex-wrap:wrap;gap:6px 16px;max-height:140px;overflow:auto;margin:10px 0}
.key{display:inline-flex;gap:6px;align-items:center}.swatch{width:11px;height:11px;border:1px solid #c7d2df;border-radius:50%}
#summary{display:flex;flex-wrap:wrap;gap:6px 20px;margin:10px 0}.stat{white-space:nowrap}#detail{font-size:13px;overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:4px 5px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--muted)}.bad{color:#ffb4ae}.good{color:#9fe2bf}#source{overflow-wrap:anywhere;font-size:12px;color:var(--muted)}
@media(max-width:850px){.workspace{grid-template-columns:1fr}aside{max-height:none}main{padding:12px}.choice{min-width:130px!important}}
</style></head><body><main>
<h1>E1 — domeny i przyczyny odmów</h1>
<p class="muted">Wyniki istniejących modeli i kontrolowanych podmian. Domyślnie pokazujemy centra molekuł po odmowach.
Kolory oznaczają lokalne propozycje domen; szare punkty nie mają przypisania. Kliknij punkt, aby odczytać dowody.</p>
<div class="controls">
<label class="choice wide">Źródło / klatka<select id="sample"></select></label>
<button id="prev" type="button">← Poprzedni</button><button id="next" type="button">Następny →</button>
<label>Przykład <input id="frame" type="range" min="0" step="1"><span id="counter"></span></label>
</div>
<div class="controls">
<label class="choice">Miejsca<select id="sampler"></select></label>
<label class="choice">Reżim<select id="regime"></select></label>
<label class="choice wide">Cechy / ziarno<select id="model"></select></label>
<label class="choice">Podział<select id="partition"></select></label>
<label class="choice wide">Wariant<select id="variant"></select></label>
</div>
<div class="layers"><label><input id="points" type="checkbox" checked> Punkty i przypisania</label>
<label><input id="before" type="checkbox"> Przed odmowami</label><small id="dimensions"></small></div>
<div id="status" role="status">Wczytywanie indeksu…</div><div id="notice"></div>
<div class="workspace"><section><div class="stage"><canvas id="canvas" aria-label="Źródłowy obraz i przypisania domen"></canvas></div>
<div id="summary"></div><div id="legend" aria-label="Legenda domen"></div><p id="source"></p></section>
<aside><h2>Wybrany punkt</h2><div id="detail">Kliknij centrum lub punkt siatki na obrazie.</div></aside></div>
</main>__INDEX_SCRIPT__<script>
'use strict';
const $=id=>document.getElementById(id), images=new Map();
let data, samples=[], runIndex=[], sampleIndex=0, currentRun=null, currentMeta=null, currentImage=null, epoch=0, selectedPoint=null;
let currentRows=[], currentLabels=[], activeVariant=null;
const terms={centers:'Centra molekuł',grid:'Siatka — to nie molekuły',transfer:'Transfer historyczny',transductive:'Transdukcja',fh4:'FH (k=4)',mws:'MWS'};
const flagTerms={incomplete_measured_support:'Pełne wsparcie pomiaru',incomplete_support:'Pełne wsparcie pomiaru',outside_transfer_test:'Zakres historycznego testu',
  invalid_measurement:'Poprawny pomiar',nonfinite_acf:'Skończony pomiar ACF',nonfinite_spectral:'Skończony pomiar widma',nonfinite_energy:'Skończona energia',
  feature_unavailable:'Dostępne cechy',nonfinite:'Skończona wartość',nonpositive_energy:'Dodatnia energia',
  acf:'Próg ACF',acf_below_threshold:'Próg ACF',second_direction:'Drugi kierunek widma',spectral:'Drugi kierunek widma',spectral_below_threshold:'Drugi kierunek widma',
  component_below_minimum_size:'Minimum komponentu',minimum:'Minimum komponentu'};
function format(value,digits=4){return value===null||value===undefined?'brak danych':typeof value==='number'?(Number.isFinite(value)?Number(value.toFixed(digits)).toString():'brak danych'):String(value)}
function percent(value){return value===null||value===undefined?'brak danych':Number.isFinite(value)?(100*value).toFixed(1)+'%':'brak danych'}
function labelOf(value){return Number.isInteger(value)&&value>0?value:0}
function color(label){return label>0?`hsl(${(label*137.508+191)%360} 79% 69%)`:'#acb5c2'}
function setError(error){$('status').textContent='Błąd galerii: '+error.message;window.e1State={...(window.e1State||{}),ready:false,error:error.message};console.error(error.message)}
function localPath(value){return typeof value==='string'&&!/^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i.test(value)&&!value.split('/').includes('..')}
function modelKey(run){return JSON.stringify([run.family,run.seed??null])}
function modelTitle(run){return `${run.family}${run.seed===null||run.seed===undefined?'':' · '+run.seed}`}
function sampleTitle(s){return s.title||(s.kind==='measurement'?`TTMAPP · klatka ${s.frame??s.frame_number??s.id}`:`${s.case||s.id} · ${s.id}`)}
function options(id,items,preferred){
  const select=$(id),previous=preferred??select.value;select.replaceChildren();
  for(const [value,title] of items){const option=document.createElement('option');option.value=value;option.textContent=title;select.appendChild(option)}
  if(items.some(([value])=>String(value)===previous))select.value=previous;
  return select.value;
}
function unique(runs,key,title){const seen=new Set();return runs.flatMap(run=>{const value=String(key(run));if(seen.has(value))return [];seen.add(value);return [[value,title(run)]]})}
function getRows(s,sampler){const rows=s.rows?.[sampler];if(!Array.isArray(rows))throw new Error('Brak miejsc dla '+sampler);return rows}
function variantTitle(key,variant){
  if(variant.title)return variant.title;
  const gates=/^A([01])S([01])M([01])$/.exec(key);
  if(gates)return `${key} · ACF ${gates[1]==='1'?'tak':'nie'}, widmo ${gates[2]==='1'?'tak':'nie'}, minimum ${gates[3]==='1'?'tak':'nie'}`;
  const oracle=/^R([PI])_M([PI])_M([01])$/.exec(key);
  if(oracle)return `${key} · relacje ${oracle[1]==='I'?'idealne':'programu'}, maska ${oracle[2]==='I'?'idealna':'programu'}, minimum ${oracle[3]==='1'?'tak':'nie'}`;
  return key;
}
function loadImage(url){
  if(!localPath(url)&&!String(url).startsWith('data:image/png;base64,'))return Promise.reject(new Error('Obraz musi być lokalnym PNG'));
  if(!images.has(url))images.set(url,new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Nie można odczytać obrazu: '+url));im.src=url}));
  return images.get(url);
}
function loadRun(meta){
  if(meta.variants)return Promise.resolve(meta);
  if(!localPath(meta.path))return Promise.reject(new Error('Nieprawidłowa lokalna ścieżka przebiegu'));
  return new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src=meta.path;
    script.onload=()=>{const payload=window.E1_RUN_DATA;script.remove();
      if(!payload||String(payload.id)!==String(meta.id)){reject(new Error('Identyfikator danych nie odpowiada wybranemu przebiegowi'));return}
      resolve(payload);
    };
    script.onerror=()=>{script.remove();reject(new Error('Nie można odczytać przebiegu: '+meta.path))};
    document.head.appendChild(script);
  });
}
function validateRun(run,rows){
  const n=rows.length;
  if(!run.variants||!Object.keys(run.variants).length)throw new Error('Brak wariantów przebiegu');
  for(const name of ['before','hard','acf','ratio','energy'])if(!Array.isArray(run[name])||run[name].length!==n)throw new Error('Nieprawidłowa długość '+name);
  if(run.oracle_before!==null&&run.oracle_before!==undefined&&(!Array.isArray(run.oracle_before)||run.oracle_before.length!==n))throw new Error('Nieprawidłowa długość oracle_before');
  if(run.scope&&run.scope.length!==n)throw new Error('Nieprawidłowa długość scope');
  for(const [key,v] of Object.entries(run.variants))if(!Array.isArray(v.labels)||v.labels.length!==n)throw new Error('Nieprawidłowa długość etykiet '+key);
  for(const [key,flags] of Object.entries(run.gate_failures||{}))if(flags.length!==n)throw new Error('Nieprawidłowa długość flag '+key);
  for(const row of rows)if(!Array.isArray(row.xy)||row.xy.length!==2||!row.xy.every(Number.isFinite))throw new Error('Nieprawidłowe współrzędne miejsca');
}
function updateControls(){
  const s=samples[sampleIndex];let candidates=runIndex.filter(r=>r.sample_id===s.id);
  if(!candidates.length)throw new Error('Brak przebiegów dla '+s.id);
  const sampler=options('sampler',unique(candidates,r=>r.sampler,r=>terms[r.sampler]||r.sampler),$('sampler').value||'centers');
  candidates=candidates.filter(r=>r.sampler===sampler);
  const regime=options('regime',unique(candidates,r=>r.regime,r=>terms[r.regime]||r.regime),$('regime').value||'transfer');
  candidates=candidates.filter(r=>r.regime===regime);
  const model=options('model',unique(candidates,modelKey,modelTitle));candidates=candidates.filter(r=>modelKey(r)===model);
  const partition=options('partition',unique(candidates,r=>r.partition,r=>terms[r.partition]||r.partition));
  candidates=candidates.filter(r=>r.partition===partition);
  if(candidates.length!==1)throw new Error('Wybór nie wskazuje dokładnie jednego przebiegu');
  return candidates[0];
}
async function chooseRun(){
  const token=++epoch;currentRun=null;currentImage=null;selectedPoint=null;
  $('status').textContent='Wczytywanie wybranego przebiegu…';$('detail').textContent='Kliknij punkt po wczytaniu obrazu.';
  $('canvas').getContext('2d').clearRect(0,0,$('canvas').width,$('canvas').height);$('summary').replaceChildren();$('legend').replaceChildren();
  window.e1State={ready:false,sample:samples[sampleIndex].id,index:sampleIndex};
  try{
    currentMeta=updateControls();const meta=currentMeta,s=samples[sampleIndex];
    const [run,im]=await Promise.all([loadRun(meta),loadImage(s.image)]);
    if(token!==epoch)return;
    const rows=getRows(s,meta.sampler);validateRun(run,rows);
    if(s.width&&s.width!==im.naturalWidth||s.height&&s.height!==im.naturalHeight)throw new Error('Niezgodne wymiary obrazu');
    if(rows.some(r=>r.xy[0]<0||r.xy[1]<0||r.xy[0]>=im.naturalWidth||r.xy[1]>=im.naturalHeight))throw new Error('Punkt poza obrazem źródłowym');
    currentRun=run;currentImage=im;currentRows=rows;
    const keys=Object.keys(run.variants);options('variant',keys.map(k=>[k,variantTitle(k,run.variants[k])]),$('variant').value||'A1S1M1');
    render();
  }catch(error){if(token===epoch)setError(error)}
}
function textRow(table,key,value,className,decision){const tr=document.createElement('tr'),a=document.createElement('td'),b=document.createElement('td');a.textContent=key;b.textContent=value;if(className)b.className=className;tr.append(a,b);if(decision){const c=document.createElement('td');c.textContent=decision;tr.appendChild(c)}table.appendChild(tr)}
function flagDecision(name){
  const key=$('variant').value,oracleMask=/_MI_/.test(key),v=activeVariant;
  if(['acf','acf_below_threshold'].includes(name))return oracleMask?'zastąpiona maską idealną':(v.acf_enabled??/^A1|_MP_/.test(key))?'aktywna':'wyłączona';
  if(['spectral','second_direction','spectral_below_threshold'].includes(name))return oracleMask?'zastąpiona maską idealną':(v.spectral_enabled??/^A[01]S1|_MP_/.test(key))?'aktywna':'wyłączona';
  if(['minimum','component_below_minimum_size'].includes(name))return (v.minimum_enabled??/M1$/.test(key))?'aktywna':'wyłączona';
  return 'zawsze wymagana';
}
function pointDetails(){
  const panel=$('detail');panel.replaceChildren();
  if(selectedPoint===null){panel.textContent='Kliknij centrum lub punkt siatki na obrazie. Wszystkie zapisane przyczyny odmowy będą widoczne jednocześnie.';return}
  const i=selectedPoint,row=currentRows[i],run=currentRun,variant=activeVariant,table=document.createElement('table');
  textRow(table,'Miejsce',row.element_id??row.id??String(i));textRow(table,'Pozycja raw [x, y]',row.xy.map(x=>format(x,2)).join(', '));
  textRow(table,'Przypisanie w widoku',currentLabels[i]>0?'D'+currentLabels[i]:'brak');
  textRow(table,'Pełne wsparcie',row.available?'tak':'nie');textRow(table,'W przestrzennym zakresie przebiegu',run.scope?(run.scope[i]?'tak':'nie'):'nie podano osobnej maski');
  textRow(table,'Twarde wymagania H',run.hard[i]?'spełnione':'niespełnione',run.hard[i]?'good':'bad');
  textRow(table,'ACF',format(run.acf[i],6));if(run.acf_threshold!==undefined)textRow(table,'Próg ACF (ściśle >)',format(run.acf_threshold,6));
  textRow(table,'Drugi kierunek widma (≥0,25)',format(run.ratio[i],6));textRow(table,'Energia',format(run.energy[i],8));
  const truth=row.truth??row.reference_label;
  if(truth!==undefined)textRow(table,'Źródłowa referencja',String(truth));
  panel.appendChild(table);
  const heading=document.createElement('p');heading.textContent='Zapisane flagi dla wybranego wariantu po odmowach. Niespełniony pomiar przy wyłączonej decyzji nie jest aktywną przyczyną odmowy. Minimum porównuje zapisane warianty M0 i M1.';panel.appendChild(heading);
  const flags={...(run.gate_failures||{}),...(variant.failures||{})};
  if(variant.minimum_failed)flags.component_below_minimum_size=variant.minimum_failed;
  const off=run.variants[$('variant').value.replace(/M[01]$/,'M0')],on=run.variants[$('variant').value.replace(/M[01]$/,'M1')];
  if(off&&on)flags.component_below_minimum_size=currentRows.map((_,j)=>labelOf(off.labels[j])>0&&!labelOf(on.labels[j]));
  const flagTable=document.createElement('table');
  const header=document.createElement('tr');for(const title of ['Warunek','Pomiar / przesłanka','Decyzja']){const th=document.createElement('th');th.textContent=title;header.appendChild(th)}flagTable.appendChild(header);
  for(const [name,values] of Object.entries(flags)){const decision=flagDecision(name),failed=Boolean(values[i]);
    textRow(flagTable,flagTerms[name]||name,failed?'niespełniony':'bez tej przesłanki',failed&&['aktywna','zawsze wymagana'].includes(decision)?'bad':failed?'muted':'good',decision);
  }
  if(!Object.keys(flags).length)textRow(flagTable,'Flagi','Nie zapisano');panel.appendChild(flagTable);
  if(variant.reasons?.[i]){const note=document.createElement('p');note.textContent='Powód wariantu: '+variant.reasons[i];panel.appendChild(note)}
}
function render(){
  if(!currentRun||!currentImage)return;
  const s=samples[sampleIndex],run=currentRun,meta=currentMeta,key=$('variant').value;
  activeVariant=run.variants[key];if(!activeVariant){setError(new Error('Brak wybranego wariantu'));return}
  const before=$('before').checked,idealBefore=key.startsWith('RI_')&&Array.isArray(run.oracle_before);
  const rawLabels=before?(idealBefore?run.oracle_before:run.before):activeVariant.labels;
  currentLabels=rawLabels.map((x,i)=>run.scope&&!run.scope[i]?0:labelOf(x));
  const canvas=$('canvas'),im=currentImage,scale=Math.min(3,1600/Math.max(im.naturalWidth,im.naturalHeight));
  canvas.width=Math.round(im.naturalWidth*scale);canvas.height=Math.round(im.naturalHeight*scale);
  const ctx=canvas.getContext('2d');ctx.scale(canvas.width/im.naturalWidth,canvas.height/im.naturalHeight);ctx.drawImage(im,0,0);
  if($('points').checked)for(let i=0;i<currentRows.length;i++){
    const [x,y]=currentRows[i].xy;ctx.beginPath();ctx.arc(x,y,meta.sampler==='centers'?1.9:1.5,0,2*Math.PI);
    ctx.strokeStyle=color(currentLabels[i]);ctx.lineWidth=.85;ctx.stroke();
    if(i===selectedPoint){ctx.beginPath();ctx.arc(x,y,4,0,2*Math.PI);ctx.strokeStyle='#fff';ctx.lineWidth=.7;ctx.stroke()}
  }
  const counts=new Map();currentLabels.forEach(x=>counts.set(x,(counts.get(x)||0)+1));
  const assigned=currentLabels.filter(x=>x>0).length,domains=[...counts.keys()].filter(x=>x>0).length;
  $('dimensions').textContent=`${im.naturalWidth} × ${im.naturalHeight} px · ${currentRows.length} ${meta.sampler==='grid'?'miejsc siatki':'centrów'}`;
  $('status').textContent=`${before?'Przed odmowami — relacje '+(idealBefore?'idealne':'programu'):'Po odmowach · '+variantTitle(key,activeVariant)} · ${assigned} przypisanych / ${currentRows.length} pokazanych · ${domains} domen`;
  const notices=[];
  if(meta.sampler==='grid')notices.push('SIATKA: kolorowe miejsca są punktami próbkowania obrazu, nie wykrytymi molekułami.');
  if(s.kind==='measurement')notices.push(meta.regime==='transfer'?'TTMAPP: historyczny transfer obejmuje wyłącznie lewy pas testowy; miejsca poza nim są szare. Obecnie to materiał rozwojowy jednej akwizycji, nie nowy niezależny test.':'TTMAPP: transdukcja wykorzystuje obrazy tej serii podczas dopasowania. To opis jednej akwizycji rozwojowej.');
  if(/^R[PI]_M[PI]_M[01]$/.test(key))notices.push('ORACLE: kontrolowana podmiana relacji lub maski z prawdy syntetycznej; nie wynik detektora do zastosowania na STM.');
  if(before)notices.push(idealBefore?'Widok przed odmowami pokazuje podział z idealnych relacji generatora.':'Widok przed odmowami pokazuje propozycję z relacji programu.');
  notices.push('ID i kolory domen są lokalne dla tego przebiegu; nie oznaczają śledzenia domen między klatkami. Kliknięcie pokazuje także flagi bramek wyłączonych w wariancie.');
  $('notice').textContent=notices.join('\n');
  $('summary').replaceChildren();
  if(!before)for(const [title,value] of [['Pokrycie dodatniej referencji',percent(activeVariant.coverage)],['Scalenia par',percent(activeVariant.merge_rate)],['Podziały par',percent(activeVariant.split_rate)]]){
    const item=document.createElement('span');item.className='stat';item.textContent=title+': '+value;$('summary').appendChild(item);
  }
  const note=document.createElement('span');note.className='muted';note.textContent=before?'Propozycja przed odmowami; poniżej brak oceny wariantu.':'Miary z zapisanej oceny; ich mianownik może różnić się od liczby pokazanych punktów.';$('summary').appendChild(note);
  $('legend').replaceChildren();
  for(const [label,count] of [...counts].sort((a,b)=>a[0]-b[0])){
    const item=document.createElement('span'),swatch=document.createElement('span');item.className='key';swatch.className='swatch';swatch.style.backgroundColor=color(label);
    item.append(swatch,document.createTextNode((label?'D'+label:'Bez przypisania / poza zakresem')+' · '+count));$('legend').appendChild(item);
  }
  $('source').textContent=`Źródło: ${s.image} · ${meta.path||'dane osadzone'} · minimum komponentu ${run.min_size}`;
  pointDetails();
  window.e1State={ready:true,error:null,sample:s.id,index:sampleIndex,run_id:meta.id,sampler:meta.sampler,regime:meta.regime,family:meta.family,seed:meta.seed??null,
    partition:meta.partition,variant:key,before,before_source:idealBefore?'ideal':'program',points:$('points').checked,point_count:currentRows.length,assigned_count:assigned,domain_count:domains,
    selected_point:selectedPoint,variant_count:Object.keys(run.variants).length,sample_count:samples.length,run_count:runIndex.length};
}
function move(index){sampleIndex=Math.max(0,Math.min(samples.length-1,index));$('sample').value=samples[sampleIndex].id;$('frame').value=sampleIndex;
  $('counter').textContent=` ${sampleIndex+1} / ${samples.length}`;$('prev').disabled=sampleIndex===0;$('next').disabled=sampleIndex===samples.length-1;chooseRun()}
try{
  data=window.E1_DATA;if(!data||!Array.isArray(data.samples)||!Array.isArray(data.runs)||!data.samples.length||!data.runs.length)throw new Error('Brak poprawnego lokalnego indeksu gallery-data.js');
  samples=data.samples;runIndex=data.runs;
  if(new Set(samples.map(s=>s.id)).size!==samples.length||new Set(runIndex.map(r=>r.id)).size!==runIndex.length)throw new Error('Powtórzone identyfikatory źródeł lub przebiegów');
  options('sample',samples.map(s=>[s.id,sampleTitle(s)]));$('frame').max=samples.length-1;
  $('sample').onchange=()=>move(samples.findIndex(s=>s.id===$('sample').value));$('frame').oninput=()=>move(Number($('frame').value));
  $('prev').onclick=()=>move(sampleIndex-1);$('next').onclick=()=>move(sampleIndex+1);
  for(const id of ['sampler','regime','model','partition'])$(id).onchange=chooseRun;
  for(const id of ['variant','before','points'])$(id).onchange=render;
  $('canvas').onclick=event=>{
    if(!currentRun||!currentImage||!$('points').checked)return;
    const rect=$('canvas').getBoundingClientRect(),x=(event.clientX-rect.left)*currentImage.naturalWidth/rect.width,y=(event.clientY-rect.top)*currentImage.naturalHeight/rect.height;
    let nearest=null,distance=Infinity;currentRows.forEach((r,i)=>{const d=Math.hypot(r.xy[0]-x,r.xy[1]-y);if(d<distance){distance=d;nearest=i}});
    selectedPoint=distance<=10*currentImage.naturalWidth/rect.width?nearest:null;render();
  };
  move(Math.max(0,samples.findIndex(s=>s.id==='ttmapp-259')));
}catch(error){setError(error)}
</script></body></html>'''
