"""Offline paired E3 viewer of prepared source images, predictions and previews.

E3_DATA contains samples, run metadata, condition IDs and variant IDs. Each
relative run script sets E3_RUN_DATA={id,scope,available,edges,min_size,threshold,
preview_row_index,conditions:{identity:...,condition:...}}. All quantitative
changes come from prepared records; the viewer only counts supplied flags.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re


def write_gallery(path: Path, data: dict | None = None, *, data_script="gallery-data.js"):
    if data is None:
        if (not isinstance(data_script, str) or not re.fullmatch(r"[\w./-]+", data_script)
                or data_script.startswith("/") or ".." in data_script.split("/")):
            raise ValueError("Expected a relative local index script")
        source = f'<script src="{html.escape(data_script, quote=True)}"></script>'
    else:
        if not data.get("samples") or not data.get("runs"):
            raise ValueError("Expected nonempty samples and runs")
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        source = f"<script>window.E3_DATA={payload};</script>"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML.replace("__INDEX__", source), encoding="utf-8")


_HTML = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>E3 — wpływ fotometrii na domeny</title>
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
</style></head><body><main><h1>E3 — wpływ fotometrii na domeny</h1>
<p class="muted">Oba panele pokazują ten sam pełny obraz źródłowy. Perturbacja dotyczy wycinków wejściowych, więc nie tworzy drugiego pełnego skanu.
Wagi modeli i adaptery pozostają zamrożone. Domyślny H_M1 jest diagnostyką bez progów ACF/widma.</p>
<div class="controls"><label class="choice wide">Źródło / klatka<select id="sample"></select></label><button id="prev">← Poprzedni</button><button id="next">Następny →</button>
<label>Przykład <input id="frame" type="range" min="0" step="1"><span id="counter"></span></label></div>
<div class="controls"><label class="choice">Miejsca<select id="sampler"></select></label><label class="choice">Reżim<select id="regime"></select></label>
<label class="choice wide">Cechy / ziarno<select id="model"></select></label><label class="choice">Podział<select id="partition"></select></label></div>
<div class="controls"><label class="choice wide">Perturbacja<select id="condition"></select></label><label class="choice wide">Bramka<select id="variant"></select></label></div>
<div class="layers"><label><input id="points" type="checkbox" checked> Punkty i domeny</label><label><input id="highlight" type="checkbox" checked> Zaznacz zmiany</label>
<label><input id="before" type="checkbox"> Propozycje przed odmowami</label><small id="dimensions"></small></div>
<div id="status" role="status">Wczytywanie…</div><div id="notice"></div>
<div class="comparison"><section class="image-panel"><h2>Bazowe wycinki</h2><p class="counts" id="base-counts"></p><div class="stage"><canvas id="base-canvas" aria-label="Obraz źródłowy, domeny bazowe"></canvas></div><div class="metrics" id="base-metrics"></div></section>
<section class="image-panel"><h2 id="changed-title">Po perturbacji wycinków</h2><p class="counts" id="changed-counts"></p><div class="stage"><canvas id="changed-canvas" aria-label="Ten sam obraz źródłowy, domeny po perturbacji"></canvas></div><div class="metrics" id="changed-metrics"></div></section></div>
<div class="legend"><span><i class="dot"></i>Szary: brak przypisania / poza zakresem</span><span><i class="dot assignment"></i>Przypisanie ↔ odmowa</span><span><i class="dot relation"></i>Zmieniona relacja sąsiedztwa</span></div>
<div id="changes"></div><div id="stability" class="card"></div><p id="source"></p>
<div class="details"><section class="card"><h2>Wybrany punkt — pomiary i decyzje</h2><div id="detail"></div></section>
<aside class="card"><h2>Podgląd wejścia 64×64</h2><p id="preview-note"></p><button id="preview-point">Wskaż punkt podglądu</button>
<div class="previews" id="preview-images" hidden><div><p>Bazowe</p><img id="base-preview" alt="Bazowy wycinek wejściowy 64 na64"></div><div><p>Po perturbacji</p><img id="changed-preview" alt="Zmieniony wycinek wejściowy 64 na64"></div></div>
<p class="muted">Oba PNG mają stałą skalę [0,1]. Przycięcie dotyczy tylko wyświetlania: inferencja używa pełnych wartości, także poza [0,1].</p><p id="preview-source"></p></aside></div>
</main>__INDEX__<script>'use strict';
const $=id=>document.getElementById(id),imageCache=new Map();
let data,samples,runIndex,sampleIndex=0,currentMeta=null,currentRun=null,currentImage=null,currentRows=[],selectedPoint=null,epoch=0,previewEpoch=0;
let baseLabels=[],changedLabels=[],baseVariant=null,changedVariant=null,baseCondition=null,changedCondition=null;
const terms={centers:'Centra molekuł',grid:'Siatka — nie molekuły',transfer:'Transfer historyczny',transductive:'Transdukcja',fh4:'FH (k=4)',mws:'MWS'};
const families={ae:'AE',rvae_full:'rVAE · treść + kąt',rvae_content:'rVAE · treść',rvae_angle:'rVAE · sam kąt',fft:'FFT',photometry:'Jasność / kontrast',geometry:'Geometria ACF'};
const conditionNames={identity:'Bez perturbacji',offset_minus:'Offset −0,1',offset_plus:'Offset +0,1',gain_minus:'Gain ×0,9',gain_plus:'Gain ×1,1',noise:'Szum σ=0,03',gradient_x_minus:'Gradient X −g',gradient_x_plus:'Gradient X +g',gradient_y_minus:'Gradient Y −g',gradient_y_plus:'Gradient Y +g'};
const variantNames={H_M1:'H_M1 · bazowe H, bez progów ACF/widma',A_fixed_M1:'A_fixed_M1 · pełna bramka bazowa',A_updated_M1:'A_updated_M1 · pełna bramka przeliczona'};
const format=(v,d=4)=>v===null||v===undefined||typeof v==='number'&&!Number.isFinite(v)?'brak danych':typeof v==='number'?Number(v.toFixed(d)).toString():String(v);
const percent=v=>v===null||v===undefined?'brak danych':Number.isFinite(v)?(v*100).toFixed(1)+'%':'brak danych';
const positive=x=>Number.isInteger(x)&&x>0?x:0;
function localPath(value){return typeof value==='string'&&!/^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i.test(value)&&!value.split('/').includes('..')}
function errorState(error){$('status').textContent='Błąd galerii: '+error.message;window.e3State={...(window.e3State||{}),ready:false,error:error.message};console.error(error.message)}
function options(id,items,preferred){const e=$(id),previous=preferred??e.value;e.replaceChildren();for(const [value,title] of items){const o=document.createElement('option');o.value=value;o.textContent=title;e.appendChild(o)}if(items.some(([v])=>String(v)===previous))e.value=previous;return e.value}
function unique(rows,key,title){const seen=new Set();return rows.flatMap(r=>{const v=String(key(r));if(seen.has(v))return [];seen.add(v);return [[v,title(r)]]})}
const modelKey=r=>JSON.stringify([r.family,r.seed??null]);
function imageFor(path){if(!localPath(path)&&!String(path).startsWith('data:image/png;base64,'))return Promise.reject(Error('Nieprawidłowa ścieżka obrazu'));if(!imageCache.has(path))imageCache.set(path,new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Nie można odczytać obrazu: '+path));im.src=path}));return imageCache.get(path)}
function runFor(meta){if(meta.conditions)return Promise.resolve(meta);if(!localPath(meta.path))return Promise.reject(Error('Nieprawidłowa ścieżka przebiegu'));return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=meta.path;script.onload=()=>{script.remove();const run=window.E3_RUN_DATA;if(!run||run.id!==meta.id)reject(Error('Niezgodny identyfikator przebiegu'));else resolve(run)};script.onerror=()=>{script.remove();reject(Error('Nie można odczytać przebiegu'))};document.head.appendChild(script)})}
function checkVector(values,n,name){if(!Array.isArray(values)||values.length!==n)throw Error('Nieprawidłowa długość '+name)}
function validate(run,rows){const n=rows.length;for(const key of ['scope','available'])checkVector(run[key],n,key);if(!run.conditions?.identity)throw Error('Brak baseline identity');
  for(const condition of data.conditions){const c=run.conditions[condition];if(!c)throw Error('Brak warunku '+condition);
    for(const key of ['before','hard','acf','ratio','energy','full_gate','input_rmse','post_outside_fraction','baseline_saturation_fraction','feature_shift_native','feature_shift_l2','feature_shift_adapted'])checkVector(c[key],n,condition+'/'+key);
    for(const stage of data.variants){const v=c.variants?.[stage];if(!v)throw Error('Brak wariantu '+stage);for(const key of ['labels','assignment_changed','neighbor_relation_changed','common_available'])checkVector(v[key],n,condition+'/'+stage+'/'+key)}}
  if(run.preview_row_index!==null&&(!Number.isInteger(run.preview_row_index)||run.preview_row_index<0||run.preview_row_index>=n))throw Error('Nieprawidłowy punkt podglądu');
  for(const r of rows)if(!Array.isArray(r.xy)||r.xy.length!==2||!r.xy.every(Number.isFinite))throw Error('Nieprawidłowe współrzędne');
}
function controls(){let candidates=runIndex.filter(r=>r.sample_id===samples[sampleIndex].id);
  const sampler=options('sampler',unique(candidates,r=>r.sampler,r=>terms[r.sampler]||r.sampler),$('sampler').value||'centers');candidates=candidates.filter(r=>r.sampler===sampler);
  const regime=options('regime',unique(candidates,r=>r.regime,r=>terms[r.regime]||r.regime),$('regime').value||'transductive');candidates=candidates.filter(r=>r.regime===regime);
  const model=options('model',unique(candidates,modelKey,r=>(families[r.family]||r.family)+(r.seed===null||r.seed===undefined?'':' · '+r.seed)),$('model').value||'["rvae_content",20261101]');candidates=candidates.filter(r=>modelKey(r)===model);
  const partition=options('partition',unique(candidates,r=>r.partition,r=>terms[r.partition]||r.partition),$('partition').value||'fh4');candidates=candidates.filter(r=>r.partition===partition);
  if(candidates.length!==1)throw Error('Wybór nie wskazuje jednego przebiegu');return candidates[0];
}
async function chooseRun(){const token=++epoch;++previewEpoch;currentRun=null;currentImage=null;selectedPoint=null;$('status').textContent='Wczytywanie porównania…';$('detail').textContent='Wczytywanie…';$('preview-images').hidden=true;$('preview-point').disabled=true;window.e3State={ready:false,sample:samples[sampleIndex].id};
  for(const id of ['base-canvas','changed-canvas'])$(id).getContext('2d').clearRect(0,0,$(id).width,$(id).height);
  try{currentMeta=controls();const meta=currentMeta,sample=samples[sampleIndex];const [run,im]=await Promise.all([runFor(meta),imageFor(sample.image)]);if(token!==epoch)return;
    const rows=sample.rows?.[meta.sampler];if(!Array.isArray(rows))throw Error('Brak miejsc samplera');validate(run,rows);
    if(sample.width&&sample.width!==im.naturalWidth||sample.height&&sample.height!==im.naturalHeight)throw Error('Niezgodne wymiary obrazu');
    if(rows.some(r=>r.xy[0]<0||r.xy[1]<0||r.xy[0]>=im.naturalWidth||r.xy[1]>=im.naturalHeight))throw Error('Punkt poza obrazem');
    currentRun=run;currentImage=im;currentRows=rows;selectedPoint=run.preview_row_index;render();
  }catch(error){if(token===epoch)errorState(error)}
}
function palette(labels){const members=new Map();labels.forEach((label,i)=>{if(label>0){if(!members.has(label))members.set(label,[]);members.get(label).push(currentRows[i].element_id??String(i))}});const result=new Map([[0,'#acb5c2']]);
  for(const [label,ids] of members){let hash=2166136261;for(const character of ids.sort().join('|'))hash=Math.imul(hash^character.charCodeAt(0),16777619)>>>0;hash=Math.imul(hash^(hash>>>16),0x85ebca6b);hash=Math.imul(hash^(hash>>>13),0xc2b2ae35);hash=(hash^(hash>>>16))>>>0;result.set(label,`hsl(${hash%360} 79% 69%)`)}return result;
}
function draw(id,labels){const canvas=$(id),im=currentImage,scale=Math.min(3,1600/Math.max(im.naturalWidth,im.naturalHeight));canvas.width=Math.round(im.naturalWidth*scale);canvas.height=Math.round(im.naturalHeight*scale);const ctx=canvas.getContext('2d');ctx.scale(canvas.width/im.naturalWidth,canvas.height/im.naturalHeight);ctx.drawImage(im,0,0);const colors=palette(labels);
  if($('points').checked)currentRows.forEach((r,i)=>{const [x,y]=r.xy;ctx.beginPath();ctx.arc(x,y,currentMeta.sampler==='centers'?1.9:1.5,0,Math.PI*2);ctx.strokeStyle=colors.get(labels[i]);ctx.lineWidth=.9;ctx.stroke();
    if($('highlight').checked&&!$('before').checked){if(changedVariant.assignment_changed[i]){ctx.beginPath();ctx.arc(x,y,3.4,0,Math.PI*2);ctx.strokeStyle='#ffe08a';ctx.lineWidth=.8;ctx.stroke()}
      if(changedVariant.neighbor_relation_changed[i]){ctx.beginPath();ctx.moveTo(x,y-4);ctx.lineTo(x+4,y);ctx.lineTo(x,y+4);ctx.lineTo(x-4,y);ctx.closePath();ctx.strokeStyle='#ff976d';ctx.lineWidth=.7;ctx.stroke()}}
    if(i===selectedPoint){ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.strokeStyle='#fff';ctx.lineWidth=.9;ctx.stroke()}});
}
function addRow(table,values){const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.appendChild(td)}table.appendChild(tr)}
function header(table,values){const tr=document.createElement('tr');for(const value of values){const th=document.createElement('th');th.textContent=value;tr.appendChild(th)}table.appendChild(tr)}
function yes(value){return value?'tak':'nie'}
function pointDetails(){const panel=$('detail');panel.replaceChildren();if(selectedPoint===null){panel.textContent=currentRows.length?'Kliknij ten sam punkt w dowolnym panelu.':'Brak miejsc samplera w tym obrazie; porównanie przypisań nie jest dostępne.';return}
  const i=selectedPoint,r=currentRows[i],base=baseCondition,changed=changedCondition,table=document.createElement('table'),stage=$('variant').value;
  header(table,['Pomiar / warunek','Bazowe','Po perturbacji','Decyzja dla prawego panelu']);
  addRow(table,['Miejsce',r.element_id??String(i),r.element_id??String(i),'ten sam punkt']);
  addRow(table,['Pozycja raw [x,y]',r.xy.map(x=>format(x,2)).join(', '),r.xy.map(x=>format(x,2)).join(', '),'bez zmiany położenia']);
  addRow(table,['Domena w widoku',baseLabels[i]?'D'+baseLabels[i]:'brak',changedLabels[i]?'D'+changedLabels[i]:'brak','numer ID nie mierzy zmiany']);
  addRow(table,['Pełne wsparcie',yes(currentRun.available[i]),yes(currentRun.available[i]),'stałe']);
  addRow(table,['W przestrzennym zakresie',yes(currentRun.scope[i]),yes(currentRun.scope[i]),'stały zakres']);
  addRow(table,['Dostępne cechy',yes(positive(base.before[i])>0),yes(positive(changed.before[i])>0),'bieżący odczyt w każdym panelu']);
  const source=stage==='A_updated_M1'?changed:base,sourceName=stage==='A_updated_M1'?'po perturbacji':'bazowe, zachowane';
  addRow(table,['Twarde wymagania H',yes(base.hard[i]),yes(changed.hard[i]),yes(source.hard[i])+' · '+sourceName]);
  const soft=stage==='H_M1'?'wyłączona':sourceName;
  addRow(table,['ACF > '+format(currentRun.threshold,6),format(base.acf[i],6),format(changed.acf[i],6),soft]);
  addRow(table,['Drugi kierunek widma ≥0,25',format(base.ratio[i],6),format(changed.ratio[i],6),soft]);
  addRow(table,['Energia',format(base.energy[i],8),format(changed.energy[i],8),'składowa H']);
  addRow(table,['Pełna bramka A/S/H',yes(base.full_gate[i]),yes(changed.full_gate[i]),stage==='H_M1'?'progi A/S wyłączone':yes(source.full_gate[i])+' · '+sourceName]);
  addRow(table,['Minimum komponentu',String(currentRun.min_size),String(currentRun.min_size),'aktywne po masce']);
  addRow(table,['Wspólna dostępność cech',yes(changedVariant.common_available[i]),yes(changedVariant.common_available[i]),'mianownik porównania']);
  addRow(table,['Przypisanie ↔ odmowa','—',yes(changedVariant.assignment_changed[i]),'zapisana flaga zmiany']);
  addRow(table,['Zmieniona relacja sąsiedztwa','—',yes(changedVariant.neighbor_relation_changed[i]),'niezależnie od numeracji domen']);
  addRow(table,['RMSE zmiany wejścia',format(base.input_rmse[i],6),format(changed.input_rmse[i],6),'wejście 64×64']);
  addRow(table,['Wejście64 bazowe ≤0 lub ≥1',percent(base.baseline_saturation_fraction[i]),percent(changed.baseline_saturation_fraction[i]),'nasycenie wejścia bazowego64']);
  addRow(table,['Wejście64 po zmianie <0 lub >1',percent(base.post_outside_fraction[i]),percent(changed.post_outside_fraction[i]),'nie obcięto podczas inferencji']);
  for(const [key,title] of [['feature_shift_native','native'],['feature_shift_l2','L2'],['feature_shift_adapted','po adapterze']])addRow(table,['Zmiana cech · '+title,format(base[key][i],6),format(changed[key][i],6),'bezwzględny dystans L2']);
  panel.appendChild(table);const note=document.createElement('p');note.className='muted';note.textContent='Pomiary po perturbacji pozostają widoczne także przy bramce bazowej lub wyłączonej. RMSE, udziały pikseli i podgląd dotyczą wejścia64 także dla FFT/geometrii. Pomiary ACF/widma mają własne natywne wycinki48; pola szumu48 i64 są niezależne.';panel.appendChild(note);
}
async function preview(){const token=++previewEpoch,index=currentRun.preview_row_index,valid=index!==null&&selectedPoint===index&&baseCondition.preview_image&&changedCondition.preview_image;
  $('preview-images').hidden=true;$('preview-point').disabled=index===null;$('preview-source').textContent='';window.e3State.preview_visible=false;window.e3State.preview_ready=false;
  if(index===null){$('preview-note').textContent='Brak dostępnego punktu podglądu dla tej próbki i samplera.';return}
  if(!valid){$('preview-note').textContent='Podgląd przygotowano tylko dla punktu '+(currentRows[index].element_id??index)+'. Wskaż go przyciskiem; nie pokazujemy wycinka innego punktu.';return}
  $('preview-note').textContent='Wczytywanie dwóch wycinków punktu '+(currentRows[index].element_id??index)+'…';
  try{const paths=[baseCondition.preview_image,changedCondition.preview_image];const images=await Promise.all(paths.map(imageFor));if(token!==previewEpoch)return;if(images.some(im=>im.naturalWidth!==64||im.naturalHeight!==64))throw Error('Podgląd nie ma wymiaru64×64');
    $('base-preview').src=paths[0];$('changed-preview').src=paths[1];$('preview-images').hidden=false;$('preview-note').textContent='Jeden deterministyczny punkt przykładowy: '+(currentRows[index].element_id??index)+'.';$('preview-source').textContent=paths.join(' · ');window.e3State.preview_visible=true;window.e3State.preview_ready=true;
  }catch(error){if(token===previewEpoch)errorState(error)}
}
function metrics(id,variant,before){const panel=$(id);panel.replaceChildren();if(before){panel.textContent='Propozycja przed maską i minimum; poniższe flagi zmian dotyczą wybranego wariantu po odmowach.';return}
  for(const [title,value] of [['Pokrycie dodatniej referencji',variant.coverage],['Scalenia par',variant.merge_rate],['Podziały par',variant.split_rate]]){const span=document.createElement('span');span.textContent=title+': '+percent(value);panel.appendChild(span)}}
function stability(){const panel=$('stability');panel.replaceChildren();const value=changedVariant.stability;if(!value?.counts){panel.textContent='Nie zapisano podsumowania stabilności dla tej pary.';return}const c=value.counts,title=document.createElement('h2');title.textContent='Zapisana stabilność wybranego wariantu po odmowach';panel.appendChild(title);const table=document.createElement('table');header(table,['Miara','Wartość','Licznik / mianownik']);
  for(const [title,key,numerator,denominator] of [['Jaccard przypisanych miejsc','assignment_jaccard','assigned_intersection_nodes','assigned_union_nodes'],['Zmiana statusu przypisania','assignment_status_change_fraction','assignment_status_changed_nodes','scope_nodes'],['Niezgodność podziału wszystkich par','pairwise_partition_disagreement','partition_disagreed_pairs','compared_pairs'],['Jaccard granic na krawędziach grafu','boundary_edge_jaccard','boundary_intersection_edges','boundary_union_edges']])addRow(table,[title,percent(value[key]),format(c[numerator],0)+' / '+format(c[denominator],0)]);
  panel.appendChild(table);const note=document.createElement('p');note.className='muted';note.textContent='Pary porównują wyłącznie miejsca przypisane w obu warunkach. Granice odnoszą się do istniejących krawędzi grafu, nie konturu pikselowego. Pusta suma zbiorów daje brak miary, nie idealną stabilność.';panel.appendChild(note);
}
function render(){if(!currentRun||!currentImage)return;const condition=$('condition').value,stage=$('variant').value,before=$('before').checked;
  baseCondition=currentRun.conditions.identity;changedCondition=currentRun.conditions[condition];baseVariant=baseCondition.variants[stage];changedVariant=changedCondition.variants[stage];
  const labels=(c,v)=>(before?c.before:v.labels).map((x,i)=>currentRun.scope[i]?positive(x):0);baseLabels=labels(baseCondition,baseVariant);changedLabels=labels(changedCondition,changedVariant);
  draw('base-canvas',baseLabels);draw('changed-canvas',changedLabels);const assigned=x=>x.filter(v=>v>0).length,domains=x=>new Set(x.filter(v=>v>0)).size;
  $('base-counts').textContent=`${assigned(baseLabels)} przypisanych / ${currentRows.length} miejsc · ${domains(baseLabels)} domen`;
  $('changed-counts').textContent=`${assigned(changedLabels)} przypisanych / ${currentRows.length} miejsc · ${domains(changedLabels)} domen`;
  $('changed-title').textContent='Po perturbacji: '+conditionNames[condition];$('status').textContent=(before?'Przed odmowami':'Po odmowach')+' · '+variantNames[stage];
  $('dimensions').textContent=`${currentImage.naturalWidth}×${currentImage.naturalHeight}px · ${currentRows.length} ${currentMeta.sampler==='centers'?'centrów':'miejsc siatki'}`;
  const notices=['Pełny obraz źródłowy jest wspólny. Offset/gain/szum/gradient zmieniają wycinki, bez ponownego obcinania wejścia do [0,1].'];
  if(data.fixture)notices.unshift('ZESTAW TECHNICZNY INTERFEJSU — wymyślone dane testowe, nie wyniki eksperymentu E3.');
  if(currentMeta.sampler==='grid')notices.push('SIATKA: to punkty próbkowania, nie wykryte molekuły.');
  if(samples[sampleIndex].kind==='measurement')notices.push(currentMeta.regime==='transfer'?'Transfer historyczny: przypisania tylko w dawnym lewym pasie testowym. To znana jedna akwizycja rozwojowa, nie nowy niezależny test.':'Transdukcja: dopasowanie korzystało z tej samej akwizycji. Klatki nie są niezależnymi testami.');
  notices.push(stage==='H_M1'?'H_M1: zachowano bazowe H i minimum; progi ACF/widma są wyłączone diagnostycznie.':stage==='A_fixed_M1'?'Bramka stała: użyto bazowych decyzji H/ACF/widma; zmienione pomiary są tylko pokazywane.':'Bramka przeliczona: decyzje H/ACF/widma używają pomiarów po perturbacji.');
  if(condition.startsWith('gradient_')){const g=data.gradient?.[currentMeta.regime];notices.push('Gradient ma zero średniej; amplituda g z dawnego train: '+format(g?.value??g,6)+'. Pełny rozstęp zmiany to2g.');}
  if(currentMeta.family==='rvae_angle'||currentMeta.family==='rvae_full')notices.push('Kąt rVAE jest odczytem enkodera, nie zwalidowanym pomiarem orientacji sieci.');
  notices.push('Kolor jest związany z pełnym składem komponentu, więc sama zmiana ID nie zmienia koloru. Halo pokazuje zapisane zmiany decyzji/relacji, nie różnicę numerów domen.');$('notice').textContent=notices.join('\n');
  const assignment=changedVariant.assignment_changed.filter(Boolean).length,neighbors=changedVariant.neighbor_relation_changed.filter(Boolean).length,common=changedVariant.common_available.filter(Boolean).length;
  $('changes').textContent=`Wybrany wariant po odmowach: ${assignment} miejsc ze zmianą przypisanie↔odmowa; ${neighbors} ze zmianą relacji sąsiedztwa; ${common} ze wspólną dostępnością cech. Flagi mogą się nakładać.`;
  metrics('base-metrics',baseVariant,before);metrics('changed-metrics',changedVariant,before);$('source').textContent='Źródło obu paneli: '+samples[sampleIndex].image+' · '+(currentMeta.path||'dane osadzone');
  window.e3State={ready:true,error:null,sample:samples[sampleIndex].id,index:sampleIndex,run_id:currentMeta.id,sampler:currentMeta.sampler,regime:currentMeta.regime,family:currentMeta.family,seed:currentMeta.seed??null,partition:currentMeta.partition,condition,variant:stage,before,points:$('points').checked,highlight:$('highlight').checked,point_count:currentRows.length,base_assigned:assigned(baseLabels),changed_assigned:assigned(changedLabels),assignment_changed:assignment,neighbor_changed:neighbors,selected_point:selectedPoint,preview_row_index:currentRun.preview_row_index,preview_visible:false,preview_ready:false,sample_count:samples.length,run_count:runIndex.length};
  pointDetails();stability();preview();
}
function move(index){sampleIndex=Math.max(0,Math.min(samples.length-1,index));$('sample').value=samples[sampleIndex].id;$('frame').value=sampleIndex;$('counter').textContent=` ${sampleIndex+1}/${samples.length}`;$('prev').disabled=sampleIndex===0;$('next').disabled=sampleIndex===samples.length-1;chooseRun()}
try{data=window.E3_DATA;if(!Array.isArray(data?.samples)||!data.samples.length||!Array.isArray(data.runs)||!data.runs.length||!Array.isArray(data.conditions)||!Array.isArray(data.variants))throw Error('Brak poprawnego indeksu E3');samples=data.samples;runIndex=data.runs;
  if(new Set(samples.map(s=>s.id)).size!==samples.length||new Set(runIndex.map(r=>r.id)).size!==runIndex.length)throw Error('Powtórzone identyfikatory');
  options('sample',samples.map(s=>[s.id,s.kind==='measurement'?'TTMAPP · klatka '+(s.frame??s.frame_number??s.id):(s.case||s.id)+' · '+s.id]));options('condition',data.conditions.map(x=>[x,conditionNames[x]||x]),'offset_plus');options('variant',data.variants.map(x=>[x,variantNames[x]||x]),'H_M1');$('frame').max=samples.length-1;
  $('sample').onchange=()=>move(samples.findIndex(s=>s.id===$('sample').value));$('frame').oninput=()=>move(Number($('frame').value));$('prev').onclick=()=>move(sampleIndex-1);$('next').onclick=()=>move(sampleIndex+1);
  for(const id of ['sampler','regime','model','partition'])$(id).onchange=chooseRun;for(const id of ['condition','variant','points','highlight','before'])$(id).onchange=render;
  for(const id of ['base-canvas','changed-canvas'])$(id).onclick=event=>{if(!currentRun||!currentImage||!$('points').checked)return;const r=$(id).getBoundingClientRect(),x=(event.clientX-r.left)*currentImage.naturalWidth/r.width,y=(event.clientY-r.top)*currentImage.naturalHeight/r.height;let selected=null,nearest=Infinity;currentRows.forEach((row,i)=>{const distance=Math.hypot(row.xy[0]-x,row.xy[1]-y);if(distance<nearest){nearest=distance;selected=i}});selectedPoint=nearest<=10*currentImage.naturalWidth/r.width?selected:null;render()};
  $('preview-point').onclick=()=>{if(currentRun&&currentRun.preview_row_index!==null){selectedPoint=currentRun.preview_row_index;render()}};move(Math.max(0,samples.findIndex(s=>s.id==='ttmapp-259')));
}catch(error){errorState(error)}
</script></body></html>'''
