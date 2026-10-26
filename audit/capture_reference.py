"""Read-only screenshot of the running reference's hero; exclude sign-in fields."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
from websockets.sync.client import connect

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'audit/tmp') as profile:
    chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--no-proxy-server',f'--user-data-dir={profile}','http://127.0.0.1:5173/login'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        portfile=Path(profile)/'DevToolsActivePort'
        for _ in range(150):
            if portfile.exists(): break
            time.sleep(.1)
        port=portfile.read_text().splitlines()[0]
        tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=5))
        tab=next(t for t in tabs if t.get('type')=='page')
        with connect(tab['webSocketDebuggerUrl'],ping_interval=None) as ws:
            seq=0
            def call(method,params):
                global seq
                seq+=1; ws.send(json.dumps(dict(id=seq,method=method,params=params)))
                while True:
                    r=json.loads(ws.recv(timeout=15))
                    if r.get('id')==seq: return r.get('result',{})
            call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
            for _ in range(150):
                r=call('Runtime.evaluate',dict(expression="!!document.body && document.body.innerText.includes('Sign in')",returnByValue=True))
                if r.get('result',{}).get('value'): break
                time.sleep(.1)
            for theme in ('light','dark'):
                call('Emulation.setEmulatedMedia',dict(features=[dict(name='prefers-color-scheme',value=theme)]))
                time.sleep(.3)
                image=call('Page.captureScreenshot',dict(format='png',clip=dict(x=0,y=0,width=690,height=900,scale=1)))
                (root/f'audit/reference-live-{theme}-hero.png').write_bytes(base64.b64decode(image['data']))
            print(json.dumps(dict(reference='AI Shorts localhost:5173/login',source_modified=False,account_interaction=False,screenshot='left hero only; sign-in fields and demo credentials excluded')))
    finally:
        chrome.terminate(); chrome.wait(timeout=10)
