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
                def request(method,path,body=None):
                    value=js("(async()=>{const s=await(await fetch('/api/auth/me')).json();const r=await fetch("+json.dumps(path)+",{method:"+json.dumps(method)+",headers:{'Content-Type':'application/json','X-CSRF-Token':s.csrf_token},"+("body:JSON.stringify("+json.dumps(body)+")," if body is not None else '')+"});return {status:r.status,data:await r.json()};})()")
                    assert value['status']<300, (path,value['status'])
                    return value['data']

                failed=request('GET',f'/api/requirements/{rid}/test-cases/{case["id"]}/executions')['executions'][0]
                js("document.getElementById('execution-"+str(failed['id'])+"').open=true")
                click('Bugs for execution #'+str(failed['id']))
                wait("document.body.innerText.includes('Create bug from failed execution')")
                click('Create bug from failed execution')
                field('Bug title','Browser observed sign-in failure','input','.execution-bugs')
                field('Severity','Critical','select','.execution-bugs')
                field('Bug priority','Low','select','.execution-bugs')
                js("document.querySelector('.execution-bugs form').requestSubmit();document.querySelector('.execution-bugs form').requestSubmit()")
                wait("!!document.querySelector('.bug-detail') && document.body.innerText.includes('Bug saved.')")
                linked=request('GET',f'/api/executions/{failed["id"]}/bugs')['bugs']
                assert len(linked)==1 and linked[0]['severity']=='Critical' and linked[0]['priority']=='Low'
                bid=linked[0]['id']

                def open_bug():
                    js("document.getElementById('execution-"+str(failed['id'])+"').open=true")
                    if not js("!!document.querySelector('.execution-bugs')"):
                        click('Bugs for execution #'+str(failed['id']))
                    wait("document.body.innerText.includes('BUG-"+str(bid)+"')")
                    if not js("!!document.querySelector('.bug-detail')"):click('Open BUG-'+str(bid))
                    wait("!!document.querySelector('.bug-detail form')")

                def move_bug(target,retest=None):
                    field('Next bug status',target,'select','.bug-detail')
                    if retest:field('Retest execution ID',str(retest),'input','.bug-detail')
                    js("document.querySelector('.bug-detail form').requestSubmit()")
                    wait("document.querySelector('.execution-bugs article.card > p')?.textContent.startsWith("+json.dumps(target)+")")

                move_bug('In Progress');move_bug('Ready for Retest')
                field('Execution status','Pass','select')
                field('Actual result','Synthetic success observed on browser retest.')
                js("document.querySelector('.manual-execution-form').requestSubmit()")
                wait("document.body.innerText.includes('2 executions recorded')")
                passed=request('GET',f'/api/requirements/{rid}/test-cases/{case["id"]}/executions')['executions'][0]
                open_bug();move_bug('Closed',passed['id'])
                field('Execution status','Fail','select');field('Actual result','Synthetic later failure observed.')
                js("document.querySelector('.manual-execution-form').requestSubmit()")
                wait("document.body.innerText.includes('3 executions recorded')")
                retest=request('GET',f'/api/requirements/{rid}/test-cases/{case["id"]}/executions')['executions'][0]
                open_bug();move_bug('Open',retest['id'])
                before=request('GET',f'/api/bugs/{bid}/history')
                assert any(e['to_status']=='Closed' and e['retest_execution_id']==passed['id'] for e in before['history'])
                js('location.reload()')
                wait("document.body?.innerText.includes('Edited sign-in test case')")
                click('Open Manual execution and history for '+case['stable_id'])
                wait("document.body.innerText.includes('3 executions recorded')")
                open_bug()
                assert request('GET',f'/api/bugs/{bid}/history')==before

                def login(email):
                    click('Log out');wait("!!document.querySelector('#login-email')")
                    fill('#login-email',email);fill('#login-password',PASSWORD)
                    js("document.querySelector('form').requestSubmit()")
                    wait("location.hash==='#dashboard' || location.hash==='#admin'")
                    js("location.hash='requirement/"+str(rid)+"'")
                    wait("document.body.innerText.includes('Edited sign-in test case')")

                login('analyst@example.com')
                click('Submit saved requirement for SQE review')
                wait("document.body.innerText.includes('Ready for Review')")
                assert not js("[...document.querySelectorAll('button')].some(b=>b.textContent==='Create test case')")
                login('engineer@example.com')
                current=request('GET',f'/api/requirements/{rid}')['requirement']
                for status in ('In Review','Approved'):
                    wait("!!document.querySelector('#review-status')")
                    js("(()=>{const e=document.querySelector('#review-status');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,"+json.dumps(status)+");e.dispatchEvent(new Event('change',{bubbles:true}));})()")
                    fill('#reviewer-notes','Browser-session review of recorded source version.')
                    click('Save Review')
                    wait("document.querySelector('.sqa-review .detail-section-heading span')?.textContent==="+json.dumps(status))
                    current=request('GET',f'/api/requirements/{rid}')['requirement']
                old=current['content_revision']
                login('analyst@example.com')
                field('Description','Registered users can sign in using their fixture account credentials.','textarea','.workflow-editor')
                click('Save edits as Draft')
                wait("document.body.innerText.includes('Current requirement content version: "+str(old+1)+"')")
                graph=request('GET',f'/api/requirements/{rid}/traceability')
                assert graph['sqa_review_status']=='Pending' and graph['current_content_revision']==old+1
                assert len(graph['executions'])==3 and graph['reviews'][-1]['content_revision']==old
                assert graph['bugs'][0]['id']==bid
                assert any(v['content_revision']==old for v in graph['versions'])
                js("location.hash='dashboard'")
                wait("document.body.innerText.includes('Current-version review and test evidence')")
                dashboard=request('GET','/api/dashboard')
                assert dashboard['approved_count']==0 and dashboard['requirements_with_linked_cases']==0
                assert dashboard['open_bugs_by_severity']['Critical']==1
                assert sum(dashboard['latest_execution_counts'].values())==0
                sizes=js("(async()=>{const values=[];for(const p of ['/api/reports/project.pdf','/api/exports/requirements.csv']){const r=await fetch(p);values.push({status:r.status,size:(await r.arrayBuffer()).byteLength});}return values;})()")
                assert all(v['status']==200 and v['size']>500 for v in sizes)
                assert not calls
                assert js("document.body.innerText.includes('Requirements needing review')")
                # Paint offscreen lazy rows for a full-page screenshot only.
                js("document.querySelectorAll('.dashboard-requirement-row').forEach(e=>e.style.contentVisibility='visible')")
                seq+=1
                ws.send(json.dumps({'id':seq,'method':'Page.captureScreenshot','params':{'format':'png','captureBeyondViewport':True}}))
                while True:
                    capture=json.loads(ws.recv(timeout=15))
                    if capture.get('id')==seq:
                        import base64
                        (Path(__file__).parent/'dashboard.png').write_bytes(base64.b64decode(capture['result']['data']))
                        break
                print(json.dumps(dict(real_browser_auth_api_sqlite=True,provider_calls=0,external_application_tested=False,case_edit_fail_bug_duplicate_guard='passed',passing_retest_close_failed_retest_reopen='passed',reload_history='passed',version_change_preserves_evidence_invalidates_approval='passed',dashboard_matches_records='passed',report_downloads=sizes,review_actions='UI form; source/case/execution/bug actions also use UI')))
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
finally:
    server.shutdown()
    server.server_close()
    fixture.tearDown()
