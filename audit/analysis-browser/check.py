"""MOCKED provider browser journey, real auth/API and disposable SQLite.

Run with backend/.venv/Scripts/python.exe after building frontend. Uses no live DB.
"""
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

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
import app
from flask import send_from_directory
from werkzeug.serving import make_server
from test_admin_dashboard import ManagerTests, PASSWORD
from test_ai_workflow import valid_analysis

logging.disable(logging.CRITICAL)
ManagerTests.setUpClass()
fixture = ManagerTests()
fixture.setUp()
app.app.config.update(LOCAL_HTTP_DEVELOPMENT=True, SESSION_COOKIE_SECURE=False)
app.app.add_url_rule('/', 'browser_index', lambda: send_from_directory(root / 'frontend/dist', 'index.html'))
app.app.add_url_rule('/assets/<path:name>', 'browser_assets', lambda name: send_from_directory(root / 'frontend/dist/assets', name))
calls = []


def provider(data):
    calls.append(data)
    return dict(status='network_error', analysis=None) if len(calls) == 1 else dict(status='success', analysis=valid_analysis())


server = make_server('127.0.0.1', 0, app.app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
origin = f'http://127.0.0.1:{server.server_port}'
try:
    with patch('analyzers.ai_analyzer.analyze_with_llm', side_effect=provider), tempfile.TemporaryDirectory() as profile:
        chrome = subprocess.Popen([
            r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless=new',
            '--disable-gpu', '--no-first-run', '--no-default-browser-check',
            '--remote-debugging-port=0', '--no-proxy-server', f'--user-data-dir={profile}',
            origin + '/#login'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            portfile = Path(profile) / 'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists(): break
                time.sleep(.1)
            port = portfile.read_text().splitlines()[0]
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=5))
            tab = next(tab for tab in tabs if tab.get('type') == 'page' and tab.get('url','').startswith(origin))
            with connect(tab['webSocketDebuggerUrl'], ping_interval=None) as ws:
                seq = 0

                def js(code):
                    global seq
                    seq += 1
                    ws.send(json.dumps({'id':seq,'method':'Runtime.evaluate','params':{'expression':code,'returnByValue':True,'awaitPromise':True}}))
                    while True:
                        result = json.loads(ws.recv(timeout=15))
                        if result.get('id') == seq:
                            assert 'exceptionDetails' not in result.get('result',{}), 'Browser JavaScript failed'
                            return result.get('result',{}).get('result',{}).get('value')

                def wait(condition):
                    for _ in range(200):
                        if js(condition): return
                        time.sleep(.05)
                    raise AssertionError(condition)

                def fill(selector, value):
                    js("(() => {const e=document.querySelector("+json.dumps(selector)+");Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,"+json.dumps(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));})()")

                def click(text):
                    assert js("(() => {const e=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==="+json.dumps(text)+");if(e){e.click();return true;}return false;})()")

                wait("!!document.querySelector('#login-email')")
                fill('#login-email','analyst@example.com')
                fill('#login-password',PASSWORD)
                js("document.querySelector('form').requestSubmit()")
                wait("location.hash==='#dashboard' && document.body.innerText.includes('All Requirements')")
                payload = dict(title='Sign in',description='Registered users can sign in with valid credentials.',requirement_type='Functional',priority='Medium')
                rid = js("(async()=>{const session=await(await fetch('/api/auth/me')).json();const r=await fetch('/api/requirements',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},body:JSON.stringify("+json.dumps(payload)+")});return (await r.json()).requirement.id;})()")
                js("location.hash='requirement/"+str(rid)+"'")
                wait("document.body.innerText.includes('Analyze saved version / Retry AI')")
                click('Analyze saved version / Retry AI')
                wait("document.body.innerText.includes('Your input is preserved')")
                assert js("document.querySelector('textarea').value") == payload['description']
                click('Analyze saved version / Retry AI')
                wait("document.body.innerText.includes('Editable proposal')")
                assert len(calls) == 2
                js('location.reload()')
                wait("document.body?.innerText.includes('Editable proposal')")
                assert len(calls) == 2, 'Reload triggered provider generation'
                js("(()=>{const e=[...document.querySelectorAll('label')].find(e=>e.textContent.startsWith('Proposed refined requirement')).querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,'Human proposal awaiting review.');e.dispatchEvent(new Event('input',{bubbles:true}));})()")
                click('Accept and save analysis with linked scenarios')
                wait("!document.body.innerText.includes('Accept and save analysis with linked scenarios')")
                saved = js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"')).json()).requirement)()")
                assert saved['description'] == payload['description']
                assert saved['analysis_summary']['improved_requirement'] == 'Human proposal awaiting review.'
                assert saved['review_status'] == 'Draft'
                assert saved['risk_score'] is None
                assert len(calls) == 2
                print(json.dumps(dict(provider='MOCKED',real_auth_api_sqlite=True,retry_preserves_input='passed',saved_proposal_reopens_without_generation='passed',editable_proposal='passed',original_unchanged='passed',no_automatic_approval='passed',provider_calls=len(calls))))
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
finally:
    server.shutdown()
    server.server_close()
    fixture.tearDown()
