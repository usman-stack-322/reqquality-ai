"""Real browser/auth/Flask/SQLite AI review journey; provider mocked, no cloud DB."""
import base64
import copy
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch
from websockets.sync.client import connect

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
import app
from flask import send_from_directory
from werkzeug.serving import make_server
from test_review_assistant import ReviewAssistantTests
from test_admin_dashboard import PASSWORD

logging.disable(logging.CRITICAL)
ReviewAssistantTests.setUpClass()
fixture=ReviewAssistantTests()
for url,directory,name in [('/',root/'frontend/dist','index.html'),('/appearance.js',root/'frontend/public','appearance.js')]:
    app.app.add_url_rule(url,'review_'+name,lambda d=directory,n=name:send_from_directory(d,n))
app.app.add_url_rule('/assets/<path:name>','review_assets',lambda name:send_from_directory(root/'frontend/dist/assets',name))
for name in ('favicon.ico','favicon-192.png','favicon-512.png','reqquality-logo.png'):
    app.app.add_url_rule('/'+name,'review_'+name,lambda n=name:send_from_directory(root/'frontend/public',n))
fixture.setUp()
app.app.config.update(LOCAL_HTTP_DEVELOPMENT=True,SESSION_COOKIE_SECURE=False)
server=make_server('127.0.0.1',0,app.app,threaded=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
output=root/'audit/ai-review-browser';output.mkdir(exist_ok=True)
calls=[]
def provider(context):
    calls.append(copy.deepcopy(context))
    if len(calls)==1:raise RuntimeError('synthetic provider failure')
    proposal=fixture.proposal()
    if len(calls)>2:proposal['changes'][0]['content']['title']='Clarified owned ticket check'
    return proposal

try:
    with patch('analyzers.review_assistant.generate_review',side_effect=provider), tempfile.TemporaryDirectory() as profile:
        chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--no-proxy-server',f'--user-data-dir={profile}',origin+'/#login'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            portfile=Path(profile)/'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():break
                time.sleep(.1)
            port=portfile.read_text().splitlines()[0]
            tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=5))
            tab=next(t for t in tabs if t.get('type')=='page')
            with connect(tab['webSocketDebuggerUrl'],ping_interval=None) as ws:
                seq=0;errors=[]
                def cdp(method,params):
                    global seq
                    seq+=1;ws.send(json.dumps({'id':seq,'method':method,'params':params}))
                    while True:
                        value=json.loads(ws.recv(timeout=20))
                        if value.get('method')=='Runtime.exceptionThrown':errors.append(value)
                        if value.get('id')==seq:return value.get('result',{})
                def js(code):
                    value=cdp('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                    assert 'exceptionDetails' not in value,str(value)
                    return value.get('result',{}).get('value')
                def wait(code):
                    for _ in range(200):
                        if js('!!document.body&&('+code+')'):return
                        time.sleep(.05)
                    (output/'failure.txt').write_text(js('document.body.innerText'),encoding='utf-8')
                    raise AssertionError(code)
                def fill(selector,value):
                    js("(()=>{const e=document.querySelector("+json.dumps(selector)+");Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,"+json.dumps(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));})()")
                def click(text):
                    assert js("(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(text)+");if(!b||b.disabled)return false;b.click();return true;})()"),text
                cdp('Runtime.enable',{})
                wait("!!document.querySelector('#login-email')")
                fill('#login-email','engineer@example.com');fill('#login-password',PASSWORD)
                js("document.querySelector('form').requestSubmit()")
                wait("location.hash==='#dashboard'")
                js("location.hash='requirement/"+str(fixture.r['id'])+"'")
                wait("document.body.innerText.includes('Request AI Revision')")
                click('Request AI Revision')
                wait("!!document.querySelector('.ai-review-panel textarea')")
                feedback='Clarify the expected result and add a negative ownership scenario.'
                fill('.ai-review-panel textarea',feedback)
                js("document.querySelector('.ai-review-panel form').requestSubmit();document.querySelector('.ai-review-panel form').requestSubmit()")
                wait("document.querySelector('.ai-review-panel').innerText.includes('could not be generated')")
                assert len(calls)==1
                assert js("document.querySelector('.ai-review-panel textarea').value")==feedback
                click('Retry / Send feedback')
                wait("document.querySelector('.ai-review-panel').innerText.includes('NEW proposed test case')")
                assert len(calls)==2
                assert fixture.f.sql('SELECT case_revision FROM test_scenarios WHERE id=?',(fixture.c['id'],))[0]['case_revision']==1
                click('Request Another Revision');fill('.ai-review-panel textarea','Also clarify the title.')
                click('Send feedback')
                wait("document.querySelector('.ai-review-panel').innerText.includes('Clarified owned ticket check')")
                assert calls[-1]['latest_proposal'] and len(calls[-1]['history'])==1
                for theme,width in [('light',1366),('dark',1366),('dark',360)]:
                    js('window.reqQualityAppearance.set('+json.dumps(theme)+')')
                    cdp('Emulation.setDeviceMetricsOverride',dict(width=width,height=900,deviceScaleFactor=1,mobile=width<500))
                    assert js('document.documentElement.scrollWidth<=innerWidth')
                    image=cdp('Page.captureScreenshot',{'format':'png'})
                    (output/f'proposal-{theme}-{width}.png').write_bytes(base64.b64decode(image['data']))
                click('Accept Changes')
                wait("document.querySelector('.ai-review-panel').innerText.includes('Changes saved as Pending Review')")
                cases=fixture.f.sql('SELECT review_status FROM test_scenarios WHERE requirement_id=?',(fixture.r['id'],))
                assert len(cases)==2 and all(c['review_status']=='Pending Review' for c in cases)
                click('Close')
                wait("!document.querySelector('.ai-review-panel')")
                click('Discuss requirement coverage')
                wait("document.querySelector('.ai-review-panel')?.innerText.includes('no cases selected')")
                assert not js("document.querySelector('.ai-review-panel').innerText.includes('Clarified owned ticket check')")
                assert not errors
                (output/'result.json').write_text(json.dumps(dict(status='passed',provider='mocked',database='isolated SQLite',provider_calls=len(calls),uncaught_exceptions=len(errors),checks=['failed feedback preserved','double submit guarded','retry','followup context','saved unchanged before acceptance','side-by-side preview','light dark mobile','accept Pending Review','context switch isolation']),indent=2),encoding='utf-8')
                print('AI review browser journey passed (mock provider, isolated SQLite).')
        finally:
            chrome.terminate();chrome.wait(timeout=10)
finally:
    server.shutdown();fixture.doCleanups()
