"""Write a self-contained E0 reference gallery; never compute predictions."""

from __future__ import annotations

import json
import math
from pathlib import Path


def write_gallery(path: Path, samples: list[dict]) -> None:
    """Embed prepared PNGs, original centres and explicitly described references."""
    if not samples or len({s["id"] for s in samples}) != len(samples):
        raise ValueError("Expected a nonempty collection with unique sample IDs")
    for sample in samples:
        if sample["kind"] not in {"measurement", "synthetic"}:
            raise ValueError("Unknown sample kind")
        for field in ("image", "overlay"):
            value = sample.get(field)
            if field == "overlay" and value is None:
                continue
            if not isinstance(value, str) or not value.startswith("data:image/png;base64,"):
                raise ValueError(f"{field} must be an embedded PNG")
        width, height = sample["width"], sample["height"]
        if not all(isinstance(n, int) and n > 0 for n in (width, height)):
            raise ValueError("Invalid image dimensions")
        if len(sample["xy"]) != len(sample["point_labels"]):
            raise ValueError("Point labels must align with the original centres")
        for x, y in sample["xy"]:
            if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < width and 0 <= y < height):
                raise ValueError("Centre outside the original image")
        for label in sample["point_labels"]:
            if label is not None and label not in sample["colors"]:
                raise ValueError("Missing colour for a point label")
        for roi in sample["rois"]:
            x0, y0, x1, y1 = roi["bbox_raw_xyxy"]
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise ValueError("ROI outside the original image")
    payload = json.dumps(samples, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML.replace("__E0_DATA__", payload), encoding="utf-8")


_HTML = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E0 — referencje i kandydaci</title>
<style>
:root{color-scheme:dark;--bg:#101721;--card:#192431;--line:#3c4b5d;--text:#eff4fa;--muted:#b7c5d6;--accent:#92dfca}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}
main{max-width:1250px;margin:auto;padding:24px}h1{font-size:27px;line-height:1.25;margin:0 0 10px}
p{margin:8px 0}.intro,small{color:var(--muted)}.controls,.layers{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.controls{padding:15px 0}.choice{flex:1;min-width:260px}.choice select{display:block;width:100%;margin-top:4px}
button,select{font:inherit;color:var(--text);background:#233346;border:1px solid #6d819a;border-radius:5px;padding:8px 12px}
button{cursor:pointer}button:disabled{opacity:.4;cursor:default}button:hover:enabled{border-color:var(--accent)}
input{accent-color:var(--accent)}#frame{width:180px;vertical-align:middle}.layers{margin:0 0 12px}
.stage{background:#080d13;border:1px solid var(--line);padding:14px;display:flex;justify-content:center;align-items:center;min-height:180px}
canvas{display:block;max-width:100%;max-height:570px;width:auto;height:auto;image-rendering:auto}
#legend{display:flex;flex-wrap:wrap;gap:10px 22px;margin:12px 0}.key{display:inline-flex;gap:7px;align-items:center}
.swatch{width:12px;height:12px;border:1px solid #b6c3d1;border-radius:50%}
#notice{border-left:3px solid #efc47e;background:#302b23;padding:12px 15px;white-space:pre-line}
h2{font-size:17px;margin:20px 0 9px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:8px}th{color:var(--muted)}
#source{overflow-wrap:anywhere;color:var(--muted);font-size:12px;margin-top:17px}.counter{color:var(--muted);white-space:nowrap}
@media(max-width:700px){main{padding:15px}h1{font-size:22px}.choice{min-width:100%}#frame{width:140px}}
</style></head><body><main>
<h1>E0 — referencje i kandydaci, bez predykcji</h1>
<p class="intro">Dane pomiarowe: nakładki to konserwatywne wnętrza referencji, nie pełne granice domen.
Syntetyki: pokazujemy prawdę generatora lub osobno opisane przykłady wymagające rozstrzygnięcia.
Okręgi wskazują dostarczone centra molekuł; nie są siatką próbkowania.</p>
<div class="controls">
<label class="choice" for="sample">Źródło / klatka<select id="sample"></select></label>
<button id="prev" type="button" aria-label="Poprzedni przykład">← Poprzedni</button>
<button id="next" type="button" aria-label="Następny przykład">Następny →</button>
<label for="frame">Przykład <input id="frame" type="range" min="0" step="1"><span id="counter" class="counter"></span></label>
</div>
<div class="layers">
<label><input id="points" type="checkbox" checked> Centra molekuł</label>
<label><input id="overlay" type="checkbox" checked> Wnętrza / etykiety źródłowe</label>
<label><input id="rois" type="checkbox" checked> Proponowane ROI</label>
<small id="dimensions"></small>
</div>
<div class="stage"><canvas id="canvas" aria-label="Obraz źródłowy z wybranymi warstwami"></canvas></div>
<div id="legend" aria-label="Legenda etykiet"></div>
<div id="notice" role="status"></div>
<h2>ROI i ich status</h2>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Zakres raw [x₀, y₀, x₁, y₁]</th><th>Cel</th><th>Rola</th><th>Status</th></tr></thead><tbody id="roi-list"></tbody></table></div>
<p id="source"></p>
</main><script>
'use strict';
window.DATA=__E0_DATA__;
const $=id=>document.getElementById(id), cache=new Map();
const terms={development_fit_candidate:'Kandydat do uczenia odczytu',development_validation_candidate:'Kandydat do walidacji',development_diagnostic:'Diagnostyka',pending_user_review:'Do przeglądu'};
let index=Math.max(0,DATA.findIndex(s=>s.id==='ttmapp-259')), epoch=0;
for(const kind of ['measurement','synthetic']){
  const group=document.createElement('optgroup');
  group.label=kind==='measurement'?'Pomiary STM':'Kontrole syntetyczne';
  DATA.forEach((s,i)=>{if(s.kind===kind){const option=document.createElement('option');option.value=i;option.textContent=s.title;group.appendChild(option)}});
  if(group.children.length)$('sample').appendChild(group);
}
$('frame').max=DATA.length-1;
function loadImage(url){
  if(!url)return Promise.resolve(null);
  if(!cache.has(url))cache.set(url,new Promise((resolve,reject)=>{
    const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Nie udało się odczytać obrazu PNG'));im.src=url;
  }));
  return cache.get(url);
}
function cell(row,text){const td=document.createElement('td');td.textContent=text;row.appendChild(td)}
function describe(s){
  $('dimensions').textContent=`${s.width} × ${s.height} px · ${s.xy.length} centrów`;
  $('counter').textContent=` ${index+1} / ${DATA.length}`;
  $('notice').textContent=s.note;
  $('source').textContent='Źródło: '+s.source;
  $('legend').replaceChildren();
  const labels=new Map(Object.entries(s.colors));
  if(s.point_labels.some(x=>x===null))labels.set('Bez etykiety referencyjnej','#b7c2d0');
  for(const [label,color] of labels){
    const item=document.createElement('span'),swatch=document.createElement('span');
    item.className='key';swatch.className='swatch';swatch.style.backgroundColor=color;
    item.append(swatch,document.createTextNode(label));$('legend').appendChild(item);
  }
  $('roi-list').replaceChildren();
  for(const roi of s.rois){const row=document.createElement('tr');
    for(const value of [roi.id,roi.bbox_raw_xyxy.map(x=>Number(x).toFixed(1)).join(', '),roi.purpose,terms[roi.role]||roi.role,terms[roi.status]||roi.status])cell(row,value);
    $('roi-list').appendChild(row);
  }
  if(!s.rois.length){const row=document.createElement('tr');cell(row,'Brak proponowanych ROI w tym przykładzie.');row.firstChild.colSpan=5;$('roi-list').appendChild(row)}
}
async function render(){
  const token=++epoch,s=DATA[index];
  $('sample').value=index;$('frame').value=index;$('prev').disabled=index===0;$('next').disabled=index===DATA.length-1;
  window.e0State={sample:s.id,index,points:$('points').checked,overlay:$('overlay').checked,rois:$('rois').checked,ready:false};
  describe(s);
  try{
    const [im,overlay]=await Promise.all([loadImage(s.image),loadImage(s.overlay)]);
    if(token!==epoch)return;
    if(im.naturalWidth!==s.width||im.naturalHeight!==s.height)throw new Error('Niezgodne wymiary obrazu');
    if(overlay&&(overlay.naturalWidth!==s.width||overlay.naturalHeight!==s.height))throw new Error('Niezgodne wymiary nakładki');
    const canvas=$('canvas'),scale=Math.min(3,1600/Math.max(s.width,s.height));
    canvas.width=Math.round(s.width*scale);canvas.height=Math.round(s.height*scale);
    const ctx=canvas.getContext('2d');ctx.scale(canvas.width/s.width,canvas.height/s.height);ctx.drawImage(im,0,0);
    if($('overlay').checked&&overlay)ctx.drawImage(overlay,0,0);
    if($('points').checked){
      for(let i=0;i<s.xy.length;i++){const [x,y]=s.xy[i],label=s.point_labels[i];
        ctx.beginPath();ctx.arc(x,y,1.7,0,2*Math.PI);ctx.lineWidth=.7;
        ctx.strokeStyle=label===null?'#bdc8d7':s.colors[label];ctx.stroke();
      }
    }
    if($('rois').checked){
      ctx.strokeStyle='#ffb36b';ctx.fillStyle='#ffb36b';ctx.lineWidth=.7;ctx.font='5px sans-serif';ctx.setLineDash([2,1.4]);
      for(const roi of s.rois){const [x0,y0,x1,y1]=roi.bbox_raw_xyxy;ctx.strokeRect(x0,y0,x1-x0,y1-y0);ctx.fillText(roi.id,x0+1,Math.min(s.height-1,y0+5))}
      ctx.setLineDash([]);
    }
    window.e0State.ready=true;
  }catch(error){if(token===epoch){$('notice').textContent='Błąd galerii: '+error.message;console.error(error.message)}}
}
function move(i){index=Math.max(0,Math.min(DATA.length-1,i));render()}
$('sample').onchange=()=>move(Number($('sample').value));
$('frame').oninput=()=>move(Number($('frame').value));
$('prev').onclick=()=>move(index-1);$('next').onclick=()=>move(index+1);
for(const id of ['points','overlay','rois'])$(id).onchange=render;
render();
</script></body></html>'''
