"""Offline E7 viewer of saved synthetic-supervised relation probes.

E7_DATA holds samples (xy and element_ids), model metadata, run paths and an
optional default_model_id. Each local script sets E7_RUN_DATA with aligned
available/common_valid/hard/full_gate node masks, source-graph edges, learned
edge scores, and learned/geometry/historical heads. Heads provide before,
H_M1, A_fixed_M1 label arrays and per-gate stats. An optional head.valid mask overrides common_valid for
that comparison, retaining separately documented legacy feature failures. No fitting, graph partitioning
or scientific metrics are performed in the browser. Scores are explicitly
identified by E7_DATA.score_kind, currently p_same, and are not presented as
calibrated probabilities. The same raw source image and node positions appear
in both panels, including technically resampled images.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re


def write_gallery(path: Path, data: dict | None = None, *, data_script="gallery-data.js"):
    """Write local-file-compatible HTML, optionally with an embedded tiny index."""
    if data is None:
        if (not isinstance(data_script, str) or not re.fullmatch(r"[\w./-]+", data_script)
                or data_script.startswith("/") or ".." in data_script.split("/")):
            raise ValueError("Expected a relative local index script")
        source = f'<script src="{html.escape(data_script, quote=True)}"></script>'
    else:
        if not data.get("samples") or not data.get("runs") or not data.get("models"):
            raise ValueError("Expected nonempty samples, runs and models")
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        source = f"<script>window.E7_DATA={payload};</script>"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML.replace("__INDEX__", source), encoding="utf-8")


_HTML = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>E7 — uczony odczyt relacji</title>
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

.details{grid-template-columns:minmax(350px,1.5fr) minmax(260px,1fr)}
.incident{margin-top:15px}.cross{color:#e9b4ff}#pair-metrics:empty{display:none}
</style></head><body><main>
<h1>E7 — uczony odczyt relacji: syntetyki → znane STM</h1>
<p class="muted">Klasyfikatory relacji uczono na syntetykach. Enkodery pozostają zamrożone, wcześniej uczone na STM w reżimie transferowym.
To osobna gałąź E7; nie wykonano nadzorowanego uczenia odczytu na etykietach STM.</p>
<div class="controls"><label class="choice wide">Źródło / klatka<select id="sample"></select></label>
<button id="prev">← Poprzedni</button><button id="next">Następny →</button>
<label>Przykład <input id="frame" type="range" min="0" step="1"><span id="counter"></span></label></div>
<div class="controls"><label class="choice wide">Uczony odczyt / ziarno<select id="model"></select></label>
<label class="choice">Podział<select id="partition"></select></label>
<label class="choice wide">Bramka<select id="gate"><option value="H_M1">H_M1 · bez progów ACF/widma</option>
<option value="A_fixed_M1">A_fixed_M1 · pełna stała bramka</option></select></label></div>
<div class="controls"><label class="choice wide">Lewy panel<select id="comparison"><option value="geometry">Uczona geometria</option>
<option value="historical">Historyczna odległość</option></select></label>
<div class="layers"><label><input id="points" type="checkbox" checked> Punkty i domeny</label>
<label><input id="before" type="checkbox"> Propozycje przed odmowami</label></div></div>
<div id="status" role="status">Wczytywanie…</div><div id="notice"></div>
<div class="comparison"><section class="image-panel"><h2 id="base-title">Uczona geometria</h2>
<p class="counts" id="base-counts"></p><div class="stage"><canvas id="base-canvas" aria-label="Obraz źródłowy i domeny porównawcze"></canvas></div>
<div class="metrics" id="base-metrics"></div></section>
<section class="image-panel"><h2 id="learned-title">Wybrany uczony odczyt</h2>
<p class="counts" id="learned-counts"></p><div class="stage"><canvas id="learned-canvas" aria-label="Ten sam obraz źródłowy i domeny uczonego odczytu"></canvas></div>
<div class="metrics" id="learned-metrics"></div></section></div>
<div class="legend"><span><i class="dot"></i>Szary: brak przypisania</span>
<span><b class="cross">×</b> Brak pełnego wejścia lub poprawnych cech odczytu</span><span>Biały okrąg: wskazany źródłowy węzeł</span>
<span>Kolor zależy od składu komponentu, nie od numeru domeny</span></div>
<div id="changes"></div><p id="source"></p>
<div class="details"><section class="card"><h2>Wybrany punkt — pomiary i decyzje</h2><div id="detail"></div></section>
<aside class="card"><h2>Relacje wskazanego punktu</h2><div id="incident"></div></aside></div>
<div id="pair-metrics" class="card" style="margin-top:16px"></div>
</main>__INDEX__<script>'use strict';
const $=id=>document.getElementById(id),imageCache=new Map();
let data,samples,runIndex,models,sampleIndex=0,currentMeta=null,currentRun=null,currentImage=null,currentSample=null;
let selectedPoint=null,epoch=0,baseLabels=[],learnedLabels=[],baseHead=null,learnedHead=null;
const terms={fh4:'FH (k=4)',mws:'MWS',geometry:'Uczona geometria',historical:'Historyczna odległość'};
const format=(value,digits=4)=>value===null||value===undefined||typeof value==='number'&&!Number.isFinite(value)?'brak danych':typeof value==='number'?Number(value.toFixed(digits)).toString():String(value);
const percent=value=>Number.isFinite(value)?(100*value).toFixed(1)+'%':'brak danych';
const yes=value=>value===null||value===undefined?'brak danych':value?'tak':'nie';
const positive=value=>Number.isInteger(value)&&value>0?value:0;
function localPath(value){return typeof value==='string'&&!/^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i.test(value)&&!value.split('/').includes('..');}
function errorState(error){$('status').textContent='Błąd galerii: '+error.message;window.e7State={...(window.e7State||{}),ready:false,error:error.message};console.error(error.message);}
function options(id,items,preferred){const element=$(id),previous=preferred??element.value;element.replaceChildren();
  for(const [value,title] of items){const option=document.createElement('option');option.value=value;option.textContent=title;element.appendChild(option);}
  if(items.some(([value])=>String(value)===previous))element.value=previous;return element.value;
}
function unique(values){return [...new Set(values)];}
function imageFor(path){if(!localPath(path))return Promise.reject(Error('Nieprawidłowa ścieżka obrazu'));
  if(!imageCache.has(path))imageCache.set(path,new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error('Nie można odczytać obrazu: '+path));image.src=path;}));
  return imageCache.get(path);
}
function runFor(meta){if(meta.learned)return Promise.resolve(meta);if(!localPath(meta.path))return Promise.reject(Error('Nieprawidłowa ścieżka przebiegu'));
  return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=meta.path;
    script.onload=()=>{script.remove();const run=window.E7_RUN_DATA;if(!run||run.id!==meta.id)reject(Error('Niezgodny identyfikator przebiegu'));else resolve(run);};
    script.onerror=()=>{script.remove();reject(Error('Nie można odczytać przebiegu'));};document.head.appendChild(script);
  });
}
function checkVector(values,n,name){if(!Array.isArray(values)||values.length!==n)throw Error('Nieprawidłowa długość '+name);}
function validate(run,sample){const n=sample.xy.length;checkVector(sample.element_ids,n,'element_ids');
  for(const xy of sample.xy)if(!Array.isArray(xy)||xy.length!==2||!xy.every(Number.isFinite))throw Error('Nieprawidłowe współrzędne źródłowe');
  for(const key of ['available','common_valid','hard','full_gate'])checkVector(run[key],n,key);
  for(const name of ['learned','geometry','historical']){const head=run[name];if(!head)throw Error('Brak odczytu '+name);
    if(head.valid!==undefined)checkVector(head.valid,n,name+'/valid');
    for(const stage of ['before','H_M1','A_fixed_M1']){checkVector(head[stage],n,name+'/'+stage);if(!head[stage].every(Number.isInteger))throw Error('Niecałkowite ID domeny');}
  }
  if(!Array.isArray(run.edges))throw Error('Brak krawędzi');
  for(const edge of run.edges)if(!Array.isArray(edge)||edge.length!==2||!edge.every(index=>Number.isInteger(index)&&index>=0&&index<n))throw Error('Nieprawidłowa krawędź');
  checkVector(run.learned_score,run.edges.length,'learned_score');
  if(run.xy!==undefined&&JSON.stringify(run.xy)!==JSON.stringify(sample.xy))throw Error('Przebieg zmienia źródłowe współrzędne');
}
function controls(){let candidates=runIndex.filter(run=>run.sample_id===samples[sampleIndex].id);
  const ids=unique(candidates.map(run=>run.model_id));
  const defaultId=data.default_model_id||[...models.values()].find(model=>String(model.family).includes('rvae')&&model.seed===20261101)?.id||ids[0];
  const model=options('model',ids.map(id=>[id,models.get(id)?.label||id]),$('model').value||defaultId);
  candidates=candidates.filter(run=>run.model_id===model);
  const partition=options('partition',unique(candidates.map(run=>run.partition)).map(id=>[id,terms[id]||id]),$('partition').value||'fh4');
  candidates=candidates.filter(run=>run.partition===partition);if(candidates.length!==1)throw Error('Wybór nie wskazuje jednego przebiegu');return candidates[0];
}
async function chooseRun(){const token=++epoch;currentRun=null;currentImage=null;selectedPoint=null;
  $('status').textContent='Wczytywanie porównania…';$('detail').textContent='Wczytywanie…';$('incident').textContent='';
  window.e7State={ready:false,sample:samples[sampleIndex].id};
  for(const id of ['base-canvas','learned-canvas'])$(id).getContext('2d').clearRect(0,0,$(id).width,$(id).height);
  try{currentMeta=controls();const meta=currentMeta,sample=samples[sampleIndex];const [run,image]=await Promise.all([runFor(meta),imageFor(sample.image)]);
    if(token!==epoch)return;validate(run,sample);
    if(sample.width!==image.naturalWidth||sample.height!==image.naturalHeight)throw Error('Niezgodne wymiary obrazu źródłowego');
    if(sample.xy.some(xy=>xy[0]<0||xy[1]<0||xy[0]>=image.naturalWidth||xy[1]>=image.naturalHeight))throw Error('Węzeł poza źródłowym obrazem');
    currentRun=run;currentImage=image;currentSample=sample;
    const first=run.common_valid.findIndex(Boolean);selectedPoint=first>=0?first:sample.xy.length?0:null;render();
  }catch(error){if(token===epoch)errorState(error);}
}
function palette(labels){const members=new Map(),result=new Map([[0,'#acb5c2']]);
  labels.forEach((label,index)=>{if(label>0){if(!members.has(label))members.set(label,[]);members.get(label).push(currentSample.element_ids[index]);}});
  for(const [label,ids] of members){let hash=2166136261;for(const character of ids.sort().join('|'))hash=Math.imul(hash^character.charCodeAt(0),16777619)>>>0;
    hash=Math.imul(hash^(hash>>>16),0x85ebca6b);hash=Math.imul(hash^(hash>>>13),0xc2b2ae35);hash=(hash^(hash>>>16))>>>0;result.set(label,`hsl(${hash%360} 79% 69%)`);}
  return result;
}
function validFor(head){return head.valid??currentRun.common_valid;}
function draw(id,labels,head){const canvas=$(id),image=currentImage,scale=Math.min(3,1600/Math.max(image.naturalWidth,image.naturalHeight));
  canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);
  const ctx=canvas.getContext('2d');ctx.scale(canvas.width/image.naturalWidth,canvas.height/image.naturalHeight);ctx.drawImage(image,0,0);
  const colors=palette(labels);if(!$('points').checked)return;
  currentSample.xy.forEach(([x,y],index)=>{const missing=!currentRun.available[index]||!validFor(head)[index];
    ctx.beginPath();ctx.lineWidth=.9;ctx.strokeStyle=missing?'#e9b4ff':colors.get(labels[index]);
    if(missing){ctx.moveTo(x-2,y-2);ctx.lineTo(x+2,y+2);ctx.moveTo(x-2,y+2);ctx.lineTo(x+2,y-2);}else ctx.arc(x,y,1.9,0,Math.PI*2);ctx.stroke();
    if(index===selectedPoint){ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.strokeStyle='#fff';ctx.stroke();}
  });
}
function tableRow(table,values,heading=false){const row=document.createElement('tr');for(const value of values){const cell=document.createElement(heading?'th':'td');cell.textContent=value;row.appendChild(cell);}table.appendChild(row);}
function pointDetails(){const panel=$('detail'),incident=$('incident');panel.replaceChildren();incident.replaceChildren();
  if(selectedPoint===null){panel.textContent=currentSample.xy.length?'Kliknij źródłowy punkt w dowolnym panelu.':'Brak centrów w tym obrazie.';incident.textContent='Brak wybranego węzła.';return;}
  const index=selectedPoint,table=document.createElement('table'),domain=labels=>labels[index]?'D'+labels[index]:'brak';
  tableRow(table,['Właściwość','Wartość'],true);
  tableRow(table,['ID źródłowego węzła',currentSample.element_ids[index]]);
  tableRow(table,['Pozycja raw [x,y]',currentSample.xy[index].map(value=>format(value,3)).join(', ')]);
  tableRow(table,['Domena lewego / prawego panelu',domain(baseLabels)+' / '+domain(learnedLabels)]);
  tableRow(table,['Pełne wejście 48',yes(currentRun.available[index])]);
  tableRow(table,['Wspólne poprawne cechy',yes(currentRun.common_valid[index])]);
  tableRow(table,['Poprawny opis: lewy / prawy panel',yes(validFor(baseHead)[index])+' / '+yes(validFor(learnedHead)[index])]);
  tableRow(table,['Twarda bramka H',currentRun.available[index]?yes(currentRun.hard[index]):'brak pełnego wejścia']);
  tableRow(table,['Pełna stała bramka A/S/H',currentRun.available[index]?yes(currentRun.full_gate[index]):'brak pełnego wejścia']);
  tableRow(table,['Bramka w aktualnym widoku',$('before').checked?'jeszcze nie zastosowana':$('gate').value==='H_M1'?'H i minimum; ACF/widmo wyłączone':'stałe H/ACF/widmo i minimum']);
  panel.appendChild(table);
  const note=document.createElement('p');note.className='muted';note.textContent='Punkty pozostają na źródłowych pozycjach. Numery domen są lokalne; kolor zależy od składu komponentu. Brak wejścia lub cechy nie jest etykietą braku domeny.';panel.appendChild(note);
  const edges=currentRun.edges.flatMap((edge,i)=>edge.includes(index)?[{neighbor:edge[0]===index?edge[1]:edge[0],score:currentRun.learned_score[i]}]:[]);
  if(!edges.length){incident.textContent='Brak incydentnych krawędzi w zapisanym grafie.';return;}
  const edgeTable=document.createElement('table');
  tableRow(edgeTable,['Sąsiad: ID','Wynik '+(data.score_kind==='p_same'?'tej samej domeny':'różnych domen')],true);
  for(const edge of edges.slice(0,12))tableRow(edgeTable,[currentSample.element_ids[edge.neighbor],format(edge.score,6)]);
  incident.appendChild(edgeTable);const description=document.createElement('p');description.className='muted';
  description.textContent=`Pokazano ${Math.min(12,edges.length)}/${edges.length} krawędzi. Wynik pochodzi z wybranego uczonego odczytu po prawej; nie jest etykietą prawdy ani deklaracją kalibracji. Brak wartości oznacza brak ocenionej relacji.`;incident.appendChild(description);
}
function metrics(id,head){const panel=$(id);panel.replaceChildren();if($('before').checked){panel.textContent='Propozycje przed odmowami; miary końcowe ukryte.';return;}
  const stats=head.stats?.[$('gate').value]||{};
  for(const [label,value] of [['Pokrycie dodatniej referencji',stats.coverage],['Scalenia par',stats.merge_rate],['Podziały par',stats.split_rate]]){const span=document.createElement('span');span.textContent=label+': '+percent(value);panel.appendChild(span);}
}
function pairMetrics(){const panel=$('pair-metrics');panel.replaceChildren();const value=currentRun.pair_stats;if(!value)return;
  const keys=[['n_same','Pary tej samej domeny'],['n_different','Pary różnych domen'],['boundary_prevalence','Częstość granic'],['roc_auc','ROC-AUC'],['average_precision','Average precision']];
  const known=keys.filter(([key])=>Object.hasOwn(value,key));if(!known.length)return;
  const title=document.createElement('h2');title.textContent='Zapisane miary relacji wybranego odczytu';panel.appendChild(title);
  const table=document.createElement('table');for(const [key,label] of known)tableRow(table,[label,format(value[key],5)]);panel.appendChild(table);
  const note=document.createElement('p');note.className='muted';note.textContent='Miary pochodzą z zapisanej oceny. Dodatnią klasą oceny granic są różne domeny; brak jednej klasy daje brak miary. Nieoznaczone obszary STM nie są negatywami.';panel.appendChild(note);
}
function render(){if(!currentRun||!currentImage)return;
  const gate=$('gate').value,comparison=$('comparison').value,stage=$('before').checked?'before':gate;
  baseHead=currentRun[comparison];learnedHead=currentRun.learned;baseLabels=baseHead[stage].map(positive);learnedLabels=learnedHead[stage].map(positive);
  draw('base-canvas',baseLabels,baseHead);draw('learned-canvas',learnedLabels,learnedHead);
  const assigned=labels=>labels.filter(value=>value>0).length,domains=labels=>new Set(labels.filter(value=>value>0)).size;
  const available=currentRun.available.filter(Boolean).length,common=currentRun.common_valid.filter(Boolean).length;
  const countText=(labels,head)=>`${assigned(labels)} przypisanych / ${validFor(head).filter(Boolean).length} z poprawnym opisem · ${domains(labels)} domen`;
  $('base-counts').textContent=countText(baseLabels,baseHead);$('learned-counts').textContent=countText(learnedLabels,learnedHead);
  const model=models.get(currentMeta.model_id);$('base-title').textContent=terms[comparison];$('learned-title').textContent=model?.label||currentMeta.model_id;
  $('status').textContent=($('before').checked?'Przed odmowami':'Po odmowach')+' · '+gate+' · '+currentImage.naturalWidth+'×'+currentImage.naturalHeight+' px raw';
  const notices=[];if(data.fixture)notices.push('ZESTAW TECHNICZNY INTERFEJSU — wymyślone dane, nie wyniki E7.');
  if(currentSample.kind==='measurement')notices.push('STM: znana jedna akwizycja rozwojowa, częściowa referencja wnętrz. Brak niezależnego testu STM; tych etykiet nie użyto do uczenia klasyfikatorów.');
  else notices.push('Walidacja syntetyczna: oddzielone grupy realizacji tego samego generatora, nie niezależne akwizycje STM.');
  notices.push('Oba panele: ten sam pełny obraz, źródłowe centra i graf. Skala wejścia 48 px odniesienia, bez zmiany centrowania.');
  notices.push(gate==='H_M1'?'H_M1: zachowano H i minimum; progi ACF/widma wyłączone diagnostycznie.':'Pełna bramka jest stała i może usunąć wszystkie przypisania.');
  if(comparison==='historical')notices.push('Historyczna odległość jest osobną bazą całej reguły, z innym przygotowaniem cech; nie izoluje efektu samego klasyfikatora.');
  notices.push('Wyniki porównują relacje i instancje domen, nie uczą nazw klas materiału ani fizycznych kątów.');$('notice').textContent=notices.join('\n');
  $('changes').textContent=`${currentSample.xy.length} źródłowych centrów · ${available} z pełnym wejściem · ${common} ze wspólnymi poprawnymi cechami. Odmowy i niedostępność pozostają widoczne.`;
  $('source').textContent='Źródło obu paneli: '+currentSample.image+' · '+(currentMeta.path||'dane osadzone');
  metrics('base-metrics',baseHead);metrics('learned-metrics',learnedHead);
  window.e7State={ready:true,error:null,sample:currentSample.id,index:sampleIndex,run_id:currentMeta.id,
    model_id:currentMeta.model_id,family:currentMeta.family??model?.family,seed:currentMeta.seed??model?.seed??null,
    partition:currentMeta.partition,gate,comparison,before:$('before').checked,points:$('points').checked,
    point_count:currentSample.xy.length,base_assigned:assigned(baseLabels),learned_assigned:assigned(learnedLabels),
    available,common_valid:common,base_valid:validFor(baseHead).filter(Boolean).length,learned_valid:validFor(learnedHead).filter(Boolean).length,selected_point:selectedPoint,width:currentImage.naturalWidth,height:currentImage.naturalHeight,
    sample_count:samples.length,run_count:runIndex.length};
  pointDetails();pairMetrics();
}
function move(index){sampleIndex=Math.max(0,Math.min(samples.length-1,index));$('sample').value=samples[sampleIndex].id;$('frame').value=sampleIndex;
  $('counter').textContent=` ${sampleIndex+1}/${samples.length}`;$('prev').disabled=sampleIndex===0;$('next').disabled=sampleIndex===samples.length-1;chooseRun();}
try{data=window.E7_DATA;if(!data?.samples?.length||!data?.runs?.length||!data?.models?.length)throw Error('Brak poprawnego indeksu E7');
  if(!['p_same','p_different'].includes(data.score_kind))throw Error('Brak jawnego znaczenia learned_score');
  samples=data.samples;runIndex=data.runs;models=new Map(data.models.map(model=>[model.id,model]));
  if(new Set(samples.map(sample=>sample.id)).size!==samples.length||new Set(runIndex.map(run=>run.id)).size!==runIndex.length)throw Error('Powtórzone identyfikatory');
  options('sample',samples.map(sample=>[sample.id,sample.title||sample.id]));$('frame').max=samples.length-1;
  $('sample').onchange=()=>move(samples.findIndex(sample=>sample.id===$('sample').value));$('frame').oninput=()=>move(Number($('frame').value));
  $('prev').onclick=()=>move(sampleIndex-1);$('next').onclick=()=>move(sampleIndex+1);
  for(const id of ['model','partition'])$(id).onchange=chooseRun;
  for(const id of ['gate','comparison','before','points'])$(id).onchange=render;
  for(const id of ['base-canvas','learned-canvas'])$(id).onclick=event=>{if(!currentRun||!currentImage||!$('points').checked)return;
    const rect=$(id).getBoundingClientRect(),x=(event.clientX-rect.left)*currentImage.naturalWidth/rect.width,y=(event.clientY-rect.top)*currentImage.naturalHeight/rect.height;
    let nearest=Infinity,selected=null;currentSample.xy.forEach((xy,index)=>{const distance=Math.hypot(xy[0]-x,xy[1]-y);if(distance<nearest){nearest=distance;selected=index;}});
    selectedPoint=nearest<=10*currentImage.naturalWidth/rect.width?selected:null;render();};
  move(Math.max(0,samples.findIndex(sample=>sample.id==='ttmapp-259')));
}catch(error){errorState(error);}

</script></body></html>'''
