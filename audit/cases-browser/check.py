"""Detailed case and Manual execution browser journey, real auth/API and disposable SQLite.

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
                payload = dict(title='Sign in',description='Registered users can sign in with valid credentials.',requirement_type='Functional',priority='High')
                rid = js("(async()=>{const session=await(await fetch('/api/auth/me')).json();const r=await fetch('/api/requirements',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},body:JSON.stringify("+json.dumps(payload)+")});const item=(await r.json()).requirement;await fetch('/api/requirements/'+item.id,{method:'PATCH',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},body:JSON.stringify({..."+json.dumps(payload)+",revision:item.revision,acceptance_criteria:['Valid credentials open the account.']})});return item.id;})()")
                click('Log out')
                wait("!!document.querySelector('#login-email')")
                fill('#login-email','engineer@example.com');fill('#login-password',PASSWORD)
                js("document.querySelector('form').requestSubmit()")
                wait("location.hash==='#dashboard'")
                js("location.hash='requirement/"+str(rid)+"'")
                wait("!!document.querySelector('.detailed-test-cases') && document.body.innerText.includes('Create test case')")

                def field(label,value,tag='textarea',scope='.detailed-test-cases'):
                    js("(() => {const l=[...document.querySelectorAll("+json.dumps(scope+' label')+")].find(l=>l.textContent.startsWith("+json.dumps(label)+"));const e=l.querySelector("+json.dumps(tag)+");const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(e,"+json.dumps(value)+");e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}));})()")

                click('Create test case')
                field('Case title','Sign-in detailed test case','input')
                field('Test type','Functional','select')
                field('Case priority','High','select')
                field('Preconditions','Registered account exists.')
                field('Test data','Initial fixture credentials, no real accounts.')
                field('Execution steps','Enter valid fixture credentials.\nRequest sign in.')
                field('Expected results','The fixture account opens.')
                js("document.querySelector('.case-edit-form input[type=checkbox]').click()")
                js("document.querySelector('.case-edit-form').requestSubmit()")
                wait("!document.querySelector('.case-edit-form') && document.body.innerText.includes('Sign-in detailed test case')")
                case = js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"/test-cases')).json()).test_cases[0])()")
                assert case['test_steps']==['Enter valid fixture credentials.','Request sign in.']
                assert case['criterion_codes']==['AC-001']
                click('Edit '+case['stable_id'])
                field('Case title','Edited sign-in test case','input')
                field('Test data','Edited fixture test data.')
                js("document.querySelector('.case-edit-form').requestSubmit()")
                wait("!document.querySelector('.case-edit-form') && document.body.innerText.includes('Edited sign-in test case')")
                click('Open Manual execution and history for '+case['stable_id'])
                wait("!!document.querySelector('.manual-execution-form')")
                field('Execution status','Fail','select')
                field('Actual result','Observed fixture failure on first attempt.')
                field('Environment','QA fixture environment','input')
                field('Build / version','fixture-build-1','input')
                field('Execution notes','First-attempt observation.')
                field('Evidence reference','evidence://first-attempt','input')
                js("document.querySelector('.manual-execution-form').requestSubmit()")
                wait("document.body.innerText.includes('1 executions recorded')")
                field('Execution status','Pass','select')
                field('Actual result','Observed fixture success on retest.')
                field('Evidence reference','evidence://retest','input')
                js("document.querySelector('.manual-execution-form').requestSubmit()")
                wait("document.body.innerText.includes('2 executions recorded')")
                before = js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"/test-cases/"+str(case['id'])+"/executions')).json()).executions)()")
                assert [v['status'] for v in before]==['Pass','Fail']
                assert before[-1]['evidence_reference']=='evidence://first-attempt'
                assert before[0]['id']!=before[1]['id']
                js('location.reload()')
                wait("document.body?.innerText.includes('Edited sign-in test case')")
                click('Open Manual execution and history for '+case['stable_id'])
                wait("document.body.innerText.includes('2 executions recorded')")
                after = js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"/test-cases/"+str(case['id'])+"/executions')).json()).executions)()")
                assert before==after
                versions = js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"/test-cases/"+str(case['id'])+"/versions')).json()).versions)()")
                assert len(versions)==2
                assert versions[-1]['snapshot']['test_data']=='Initial fixture credentials, no real accounts.'
                click('Log out');wait("!!document.querySelector('#login-email')")
                fill('#login-email','analyst@example.com');fill('#login-password',PASSWORD)
                js("document.querySelector('form').requestSubmit()")
                wait("location.hash==='#dashboard'")
                js("location.hash='requirement/"+str(rid)+"'")
                wait("document.body.innerText.includes('Edited sign-in test case')")
                assert not js("[...document.querySelectorAll('button')].some(b=>b.textContent==='Create test case')")
                denied=js("(async()=>{const s=await(await fetch('/api/auth/me')).json();return (await fetch('/api/requirements/"+str(rid)+"/test-cases/"+str(case['id'])+"/executions',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':s.csrf_token},body:'{}'})).status})()")
                assert denied==403
                assert not calls
                print(json.dumps(dict(real_auth_api_sqlite=True,external_application_tested=False,provider_calls=0,case_create_edit_links_numbered_steps='passed',manual_failure_and_retest='passed',reload_preserves_evidence='passed',old_case_version_preserved='passed',analyst_execution_rejected=denied)))
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
finally:
    server.shutdown()
    server.server_close()
    fixture.tearDown()
