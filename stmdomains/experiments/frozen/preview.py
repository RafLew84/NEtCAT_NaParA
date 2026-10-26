"""Self-contained inspection of feature sampling geometry, not domain predictions."""
import argparse,base64,io,json
from pathlib import Path
import numpy as np
from PIL import Image
from stmdomains.experiments.bundle import load_sample


def preview(root):
    m=json.loads((root/'manifest.json').read_text());samples={};entries=[]
    for sid in m['samples']:
        rec,a=load_sample(root/'input/analysis',sid);values=a['image'][a['measured']];lo,hi=np.percentile(values,[2,98]);gray=np.uint8(np.clip((a['image']-lo)/max(hi-lo,1e-12),0,1)*255)
        stream=io.BytesIO();Image.fromarray(gray).save(stream,format='PNG');image='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()
        order=np.argsort(a['object_ids']);samples[sid]=dict(image=image,shape=list(gray.shape),spacing=rec['pixel_spacing_xy'],centers=a['centers_xy'][order].tolist(),ids=a['object_ids'][order].tolist())
    for e in m['entries']:
        a=np.load(root/e['path']);meta=json.loads((root/e['metadata_path']).read_text())
        entries.append(dict(sample=e['sample_id'],config=e['config'],mode=e['sampling'],xy=a['xy'].tolist(),boxes=a['window_xyxy'].tolist(),support=a['measured_support_fraction'].round(6).tolist(),
                            norms=np.linalg.norm(a['features'],axis=1).round(6).tolist(),dimension=meta['dimension'],maps=meta['native_feature_maps'],normalization=meta['normalization']))
    data=json.dumps(dict(samples=samples,entries=entries),ensure_ascii=False,separators=(',',':'))
    html=r'''<!doctype html><meta charset="utf-8"><title>Issue18 · miejsca pomiaru cech</title>
<style>*{box-sizing:border-box}body{font:16px/1.5 system-ui;margin:24px auto;max-width:1240px;padding:0 18px;color:#203345;background:#f6f8fa}.panel{background:white;border:1px solid #d9e1e8;padding:18px;margin:16px 0}.controls{display:flex;gap:12px;flex-wrap:wrap}select,button{font:inherit;padding:6px;max-width:100%}.view{display:grid;grid-template-columns:minmax(300px,1.5fr) minmax(250px,1fr);gap:20px}canvas{width:100%;max-width:760px;background:#141c24}#details{white-space:pre-line}.notice{background:#fff1d9;padding:14px}h1{font-size:27px}@media(max-width:800px){.view{grid-template-columns:1fr}}</style>
<h1>Issue 18 · skąd pochodzą cechy obrazu?</h1><p class="notice"><b>To przygotowanie cech, bez wykrywania domen.</b> Krzyżyki pokazują regularną siatkę próbkowania. Okręgi pokazują dostarczone centra molekuł. Prostokąt wskazuje fragment obrazu podany do sieci; nie jest granicą domeny.</p>
<div class="panel controls"><label>Klatka <select id="sample"></select></label><label>Model <select id="model"><option>fcn_resnet101</option><option>dinov2_vits14</option></select></label><label>Miejsca <select id="mode"><option value="grid">Siatka — krzyżyki</option><option value="centers">Molekuły — okręgi</option></select></label><label>Promień okna <select id="radius"><option>24</option><option>36</option></select></label><label>Wejście sieci <select id="size"><option>112</option><option>224</option></select></label><label>Normalizacja klatki <select id="norm"><option value="frame_percentile">Percentyle 2–98</option><option value="frame_minmax">Minimum–maksimum</option></select></label><button id="edge">Próbka przy brzegu</button><button id="middle">Próbka wewnątrz</button></div>
<div class="panel view"><div><canvas id="canvas"></canvas><p>Kliknij krzyżyk lub środek molekuły, aby obejrzeć jego okno. Jasność zdjęcia służy tylko podglądowi.</p></div><div id="details"></div></div>
<p>Podparcie pomiarem oddziela zmierzone piksele od odbicia poza polem i uzupełnienia braków. Okna mają szerokość 48/72 piksele odniesienia; 112/224 oznacza rozmiar po technicznym przeskalowaniu. Rozstaw molekuł nie steruje skalowaniem.</p><p>Statystyki normalizacji pochodzą z całej zmierzonej klatki. W DINO każdy token może korzystać z całego okna przez attention. FCN używa warstw layer1/layer2; zapisany wektor uśrednia ich mapy w oknie. Norma wektora nie mierzy porządku ani pewności domeny.</p>
<script>const DATA=__DATA__;let selected=0,current=null,epoch=0;const pictures={};
for(const id of Object.keys(DATA.samples)){const o=document.createElement('option');o.value=id;o.textContent=id;document.getElementById('sample').appendChild(o)}
document.getElementById('sample').value='ttmapp-250';
function render(){let sid=document.getElementById('sample').value,s=DATA.samples[sid];current=DATA.entries.find(e=>e.sample===sid&&e.config.model===document.getElementById('model').value&&e.mode===document.getElementById('mode').value&&e.config.radius===+document.getElementById('radius').value&&e.config.input_size===+document.getElementById('size').value&&e.config.normalization===document.getElementById('norm').value);let e=current;selected=Math.min(selected,Math.max(0,e.xy.length-1));let c=document.getElementById('canvas'),ctx=c.getContext('2d'),token=++epoch;c.width=s.shape[1]*3;c.height=s.shape[0]*3;
let details='Model: '+e.config.model+'\nPróbek: '+e.xy.length+'\nCech w wektorze: '+e.dimension+'\nMapy wewnętrzne: '+e.maps.map(x=>x.join('×')).join(' + ');if(e.xy.length){let p=e.xy[selected];details+='\n\nWybrana próbka: '+(selected+1)+(e.mode==='centers'?' · '+s.ids[selected]:'')+'\nPozycja w oryginale: '+p.map(x=>x.toFixed(2)).join(', ')+' px\nRzeczywiste podparcie: '+(e.support[selected]*100).toFixed(2)+'%\nNorma wektora: '+e.norms[selected].toFixed(4)+'\nOkno w oryginale: '+e.boxes[selected].map(x=>x.toFixed(2)).join(', ')}else details+='\n\nBrak oznaczeń molekuł. Wariant siatkowy nadal jest dostępny.';document.getElementById('details').textContent=details;
if(!pictures[sid])pictures[sid]=new Promise(resolve=>{const im=new Image();im.onload=()=>resolve(im);im.src=s.image});pictures[sid].then(im=>{if(token!==epoch)return;ctx.drawImage(im,0,0,c.width,c.height);ctx.lineWidth=1.3;ctx.strokeStyle=e.mode==='grid'?'#48e3db':'#ffdb65';for(const p of e.xy){const x=p[0]*3,y=p[1]*3;ctx.beginPath();if(e.mode==='grid'){ctx.moveTo(x-4,y);ctx.lineTo(x+4,y);ctx.moveTo(x,y-4);ctx.lineTo(x,y+4)}else ctx.arc(x,y,5,0,2*Math.PI);ctx.stroke()}if(e.xy.length){let b=e.boxes[selected];ctx.strokeStyle='#ff617d';ctx.lineWidth=3;ctx.strokeRect(b[0]*3,b[1]*3,(b[2]-b[0])*3,(b[3]-b[1])*3)}})}
for(const id of ['sample','model','mode','radius','size','norm'])document.getElementById(id).onchange=()=>{selected=0;render()};document.getElementById('edge').onclick=()=>{selected=0;render()};document.getElementById('middle').onclick=()=>{selected=Math.floor(current.xy.length/2);render()};document.getElementById('canvas').onclick=ev=>{let rect=ev.target.getBoundingClientRect(),s=DATA.samples[document.getElementById('sample').value],x=(ev.clientX-rect.left)/rect.width*s.shape[1],y=(ev.clientY-rect.top)/rect.height*s.shape[0],best=Infinity;current.xy.forEach((p,i)=>{let d=Math.hypot(p[0]-x,p[1]-y);if(d<best){best=d;selected=i}});render()};render();</script>'''
    (root/'index.html').write_text(html.replace('__DATA__',data))
    print('geometry preview',len(samples),'frames',len(entries),'variants')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();preview(a.root)
