"""Local inspection gallery. Rendering never changes the analysis arrays."""

from __future__ import annotations

import html
import json

import numpy as np
from PIL import Image


def make_preview(root, manifest):
    evaluation = json.loads((root/"evaluation/manifest.json").read_text())
    truth_by_id = {r['sample_id']: r for r in evaluation['controls']+evaluation['references']}
    folder = root/'preview'; folder.mkdir()
    rows = []
    colors = np.array([[0, 0, 0, 0], [25, 195, 170, 110], [245, 80, 80, 110], [250, 205, 30, 110]], dtype=np.uint8)
    for record in manifest['samples']:
        ident = record['sample_id']
        with np.load(root/'analysis'/record['file'], allow_pickle=False) as arrays:
            image = arrays['image']; valid = arrays['measured']; centers = arrays['centers_xy'].tolist()
        lo, hi = np.percentile(image[valid], [1, 99])
        gray = np.zeros(image.shape, np.uint8)
        gray[valid] = (255*np.clip((image[valid]-lo)/max(hi-lo, 1e-12), 0, 1)).astype(np.uint8)
        Image.fromarray(gray).save(folder/f'{ident}.png')
        overlay = np.zeros((*image.shape, 4), np.uint8)
        truth_record = truth_by_id.get(ident)
        caption = 'Brak ręcznej referencji. Całe oryginalne pole pomiarowe.'
        if truth_record:
            with np.load(root/'evaluation'/truth_record['file'], allow_pickle=False) as truth:
                if record['kind'] == 'synthetic':
                    labels = truth['domain_labels']; uncertain = truth['boundary_uncertain']
                    caption = f"Kontrola {truth_record['case']} · {truth_record['split']} · seed {truth_record['seed']} · zadanych domen w generatorze: {truth_record['expected_domain_count']}. To prawda kontrolna, nie wynik detektora."
                else:
                    labels = truth['orientation_groups']; uncertain = truth['boundary_unscored']
                    caption = 'Częściowe wnętrza referencji: kolory opisują głównie orientacje. Reszta jest nieoznaczona. Kolor bursztynowy = wyłączony pas przybliżonej granicy; nie jest skalibrowaną niepewnością.'
                overlay = colors[labels % len(colors)]
                overlay[uncertain] = [255, 150, 25, 150]
            Image.fromarray(overlay).save(folder/f'{ident}-evaluation.png')
        title = f"Klatka {record['frame_number']}" if record['kind']=='measurement' else f"{ident}: {truth_record['case']} / {truth_record['seed']}"
        rows.append(dict(id=ident, title=title, kind=record['kind'], shape=record['shape_hw'],
                         image=f'preview/{ident}.png', overlay=f'preview/{ident}-evaluation.png' if truth_record else None,
                         centers=centers, caption=caption, unit=record['position_unit'], spacing=record['pixel_spacing_xy']))
    case_rows = ''.join(f'<tr><td>{html.escape(case)}</td><td>3 rozwojowe + 3 do oceny</td></tr>' for case in sorted({r['case'] for r in evaluation['controls']}))
    page = '''<!doctype html><html lang="pl"><meta charset="utf-8"><title>STM Domains — wspólne wejście</title>
<style>body{font:16px/1.5 system-ui;margin:24px auto;max-width:1100px;padding:0 20px;background:#f4f6f7;color:#162c36}h1{font-size:27px}main{display:grid;grid-template-columns:minmax(300px,600px) 1fr;gap:24px}canvas{width:100%;background:#111;image-rendering:auto}button,select,label{margin:6px;padding:6px}table{border-collapse:collapse}td,th{padding:5px 12px;border-bottom:1px solid #ccc}aside{background:white;padding:16px}small{display:block} @media(max-width:750px){main{display:block}}</style>
<h1>Wspólne wejście do prób domen</h1><p>Przygotowanie issue 14. Nie uruchomiono detektora domen. Dane analizy są w <code>analysis/</code>; referencje i prawda syntetyczna osobno w <code>evaluation/</code>.</p>
<p>Podgląd: percentyle 1–99 osobno dla obrazu. Jasność podglądu nie zmienia danych pomiarowych. Padding rejestracji jest poza wejściem.</p>
<select id="group"><option value="all">Wszystkie</option><option value="measurement">TTMAPP</option><option value="synthetic">Kontrole</option></select><button id="prev">←</button><select id="sample"></select><button id="next">→</button>
<main><div><canvas id="canvas"></canvas><label><input id="points" type="checkbox" checked>Centra oznaczeń</label><label><input id="truth" type="checkbox">Referencja / prawda kontrolna</label></div><aside><h2 id="title"></h2><p id="caption"></p><p id="meta"></p><small>Nieoznaczone otoczenie rzeczywistych ramek nie jest podłożem ani błędem detekcji. Ramki nie wyznaczają wejścia analizy.</small></aside></main>
<details><summary>Zestaw kontroli</summary><table><tr><th>Przypadek</th><th>Powtórzenia</th></tr>CASES</table></details>
<script>const rows=ROWS;const sel=document.querySelector('#sample'),group=document.querySelector('#group'),canvas=document.querySelector('#canvas'),ctx=canvas.getContext('2d');let current=null,base=null,over=null,token=0;
function image(src){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=reject;im.src=src;});}
function draw(){if(!base||!current)return;ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(base,0,0);if(over&&document.querySelector('#truth').checked)ctx.drawImage(over,0,0);if(document.querySelector('#points').checked){ctx.strokeStyle='#68baff';ctx.lineWidth=.7;for(const [x,y] of current.centers){ctx.beginPath();ctx.arc(x,y,2,0,2*Math.PI);ctx.stroke();}}}
function show(){const t=++token,row=rows[Number(sel.value)];Promise.all([image(row.image),row.overlay?image(row.overlay):Promise.resolve(null)]).then(imgs=>{if(t!==token)return;current=row;[base,over]=imgs;canvas.width=base.width;canvas.height=base.height;document.querySelector('#title').textContent=row.title;document.querySelector('#caption').textContent=row.caption;document.querySelector('#meta').textContent=`${row.shape[1]} × ${row.shape[0]} px · ${row.centers.length} oznaczeń · krok ${row.spacing.join(' / ')} ${row.unit}`;draw();}).catch(()=>{document.querySelector('#caption').textContent='Nie udało się odczytać lokalnego podglądu.';});}
function populate(){sel.replaceChildren();rows.forEach((r,i)=>{if(group.value==='all'||group.value===r.kind){const o=document.createElement('option');o.value=i;o.textContent=r.title;sel.append(o);}});show();}
group.onchange=populate;sel.onchange=show;document.querySelector('#prev').onclick=()=>{sel.selectedIndex=Math.max(0,sel.selectedIndex-1);show();};document.querySelector('#next').onclick=()=>{sel.selectedIndex=Math.min(sel.options.length-1,sel.selectedIndex+1);show();};document.querySelector('#points').onchange=draw;document.querySelector('#truth').onchange=draw;populate();</script></html>'''
    page = page.replace('CASES', case_rows).replace('ROWS', json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c'))
    (root/'index.html').write_text(page)
