import json,sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QTimer,QUrl
root=Path(sys.argv[1]);app=QApplication(['feature-geometry-check']);errors=[];checks=[]
class Page(QWebEnginePage):
 def javaScriptConsoleMessage(self,level,message,line,source):
  if level==QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:errors.append([message,line])
v=QWebEngineView();page=Page(v);v.setPage(page);v.resize(1280,1050);v.show()
actions=[]
for sample in ['ttmapp-250','control-0070','control-0086','control-0087']:
 for model in ['fcn_resnet101','dinov2_vits14']:
  for mode in ['grid','centers']:
   actions.append(f"document.getElementById('sample').value='{sample}';document.getElementById('model').value='{model}';document.getElementById('mode').value='{mode}';render()")
actions += ["document.getElementById('sample').value='ttmapp-250';document.getElementById('radius').value='36';document.getElementById('size').value='224';document.getElementById('norm').value='frame_minmax';render()","document.getElementById('middle').click()","document.getElementById('mode').value='grid';render();document.getElementById('edge').click()"]
def observe(result):
 checks.append(result)
 if actions:advance()
 else:
  v.grab().save(str(root/'geometry-preview.png'));report=dict(errors=errors,checks=checks,browser='QtWebEngine offscreen',local_html=True)
  (root/'browser-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps({'errors':errors,'checks':len(checks)}));app.exit(0 if not errors and all(x and x['samples']==12 and x['painted'] and x['width']<=x['viewport'] for x in checks) else 1)
def advance():
 page.runJavaScript(actions.pop(0));QTimer.singleShot(250,lambda:page.runJavaScript("({samples:Object.keys(DATA.samples).length,count:current.xy.length,sampling:current.mode,selected:selected,painted:document.getElementById('canvas').getContext('2d').getImageData(100,100,1,1).data[3]===255,width:document.body.scrollWidth,viewport:innerWidth})",observe))
def loaded(ok):
 if ok:QTimer.singleShot(500,advance)
 else:app.exit(2)
page.loadFinished.connect(loaded);page.load(QUrl.fromLocalFile(str(root/'index.html')));QTimer.singleShot(30000,lambda:app.exit(3));sys.exit(app.exec())
