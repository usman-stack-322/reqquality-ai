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
                    (Path(__file__).parent/'failure-body.txt').write_text(js('document.body.innerText'),encoding='utf-8')
                    raise AssertionError(condition)

                def fill(selector, value):
                    js("(() => {const e=document.querySelector("+json.dumps(selector)+");Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,"+json.dumps(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));})()")

                def click(text):
                    assert js("(() => {const e=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==="+json.dumps(text)+");if(e){e.click();return true;}return false;})()")

                def cdp(method, params):
                    global seq
                    seq += 1
                    ws.send(json.dumps(dict(id=seq,method=method,params=params)))
                    while True:
                        result=json.loads(ws.recv(timeout=15))
                        if result.get('id')==seq:
                            assert 'error' not in result,result.get('error')
                            return result.get('result',{})

                wait("!!document.querySelector('#login-email')")
                js("window.requestLog=[];window.realFetch=window.fetch;window.fetch=async(...a)=>{window.requestLog.push(String(a[0]));if(window.failLogin&&String(a[0]).includes('/api/auth/login')){window.failLogin=false;return new Response(JSON.stringify({error:'The database is temporarily unavailable. Please try again later.',code:'database_unavailable'}),{status:503,headers:{'Content-Type':'application/json'}});}return window.realFetch(...a);}")
                time.sleep(.3)
                assert js("window.requestLog.filter(p=>p.includes('/api/auth/')).length===0")
                fill('#login-email','analyst@example.com');fill('#login-password','invalid-synthetic-password')
                y=js("document.querySelector('button[type=submit]').getBoundingClientRect().top")
                js("document.querySelector('form').requestSubmit()")
                wait("document.body.innerText.includes('Email or password is incorrect.')")
                assert abs(js("document.querySelector('button[type=submit]').getBoundingClientRect().top")-y)<2
                js("window.failLogin=true;window.requestLog=[]")
                fill('#login-password',PASSWORD)
                js("document.querySelector('form').requestSubmit()")
                wait("document.body.innerText.includes('database is temporarily unavailable')")
                assert js("window.requestLog.filter(p=>p.includes('/api/auth/login')).length===1")
                import base64
                for width in (360,768,1366):
                    cdp('Emulation.setDeviceMetricsOverride',dict(width=width,height=900,deviceScaleFactor=1,mobile=width<500))
                    assert js("document.documentElement.scrollWidth<=innerWidth"),width
                    capture=cdp('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
                    (Path(__file__).parent/f'login-{width}.png').write_bytes(base64.b64decode(capture['data']))
                js("window.requestLog=[];document.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));document.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
                wait("location.hash==='#dashboard' && document.body.innerText.includes('All Requirements')")
                assert js("window.requestLog.filter(p=>p.includes('/api/auth/login')).length===1")
                payload = dict(title='Sign in',description='Registered users can sign in with valid credentials.',requirement_type='Functional',priority='High')
                js("location.hash='requirements'")
                wait("!!document.querySelector('#requirement-title')")
                assert js("!window.requestLog.some(p=>p.includes('view=summary')&&p.includes('requirements')&&p.endsWith('view=summary'))")
                fill('#requirement-title',payload['title']);fill('#requirement-description',payload['description'])
                click('Save Requirement')
                wait("location.hash.startsWith('#requirement/') && document.body.innerText.includes('Analyze saved version / Retry AI')")
                rid=js("Number(location.hash.split('/')[1])")
                js("location.hash='requirement/"+str(rid)+"'")
                wait("document.body.innerText.includes('Analyze saved version / Retry AI')")
                click('Analyze saved version / Retry AI')
                wait("document.body.innerText.includes('Your input is preserved')")
                click('Analyze saved version / Retry AI')
                wait("document.body.innerText.includes('Editable proposal')")
                js('location.reload()')
                wait("document.body?.innerText.includes('Editable proposal')")
                assert len(calls)==2
                js("(()=>{const labels=[...document.querySelectorAll('label')];for(const [prefix,value] of [['Proposed refined requirement','Registered users can sign in using valid credentials.'],['Acceptance criteria, one per line','Valid credentials open the registered account.']]){const e=labels.find(l=>l.textContent.startsWith(prefix)&&l.closest('fieldset')?.querySelector('legend')?.textContent.startsWith('Editable proposal')).querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));}})()")
                js("(()=>{const e=[...document.querySelectorAll('label')].find(l=>l.textContent.startsWith('Acceptance criteria, one per line')&&l.closest('fieldset')?.querySelector('legend')?.textContent.startsWith('Editable proposal')).querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,e.value+String.fromCharCode(10));e.dispatchEvent(new Event('input',{bubbles:true}));})()")
                assert js("[...document.querySelectorAll('label')].find(l=>l.textContent.startsWith('Acceptance criteria, one per line')&&l.closest('fieldset')?.querySelector('legend')?.textContent.startsWith('Editable proposal')).querySelector('textarea').value.endsWith(String.fromCharCode(10))")
                click('Accept and save analysis with linked scenarios')
                wait("!document.body.innerText.includes('Accept and save analysis with linked scenarios')")
                saved=js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"')).json()).requirement)()")
                assert saved['description']==payload['description'] and saved['review_status']=='Draft'
                assert saved['analysis_summary']['improved_requirement']=='Registered users can sign in using valid credentials.'
                assert saved['acceptance_criteria'][0]['description']=='Valid credentials open the registered account.'
                assert saved['test_scenarios'] and all(v['review_status']=='Draft' for v in saved['test_scenarios'])
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
                case = js("(async()=> (await(await fetch('/api/requirements/"+str(rid)+"/test-cases')).json()).test_cases.find(c=>c.title==='Sign-in detailed test case'))()")
                assert case['test_steps']==['Enter valid fixture credentials.','Request sign in.']
                assert case['criterion_codes']==['AC-001']
                click('Edit '+case['stable_id'])
                js("globalThis.__releaseOriginalFetch=window.fetch;globalThis.__delayCaseReads=true;window.fetch=async function(...args){const response=await globalThis.__releaseOriginalFetch(...args);if(globalThis.__delayCaseReads&&String(args[0]).includes('/test-cases?'))await new Promise(resolve=>setTimeout(resolve,1200));return response;}")
                field('Case title','Edited sign-in test case','input')
                field('Test data','Edited fixture test data.')
                js("document.querySelector('.case-edit-form').requestSubmit()")
                wait("!document.querySelector('.case-edit-form') && document.body.innerText.includes('Case version saved.')")
                assert not js("!!document.getElementById('test-case-"+str(case['id'])+"')"), 'Old executable row remained interactive during delayed revision refresh'
                js("globalThis.__delayCaseReads=false")
                wait("[...document.querySelectorAll('.detailed-test-cases button')].some(b=>b.textContent.trim()==="+json.dumps('Open Manual execution and history for '+case['stable_id'])+")")
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
                    wait("!!document.querySelector('.bug-detail form fieldset:not(:disabled)')")
                    field('Next bug status',target,'select','.bug-detail')
                    if retest:field('Retest execution ID',str(retest),'input','.bug-detail')
                    js("document.querySelector('.bug-detail form').requestSubmit()")
                    wait("document.querySelector('.execution-bugs article.card > p')?.textContent.startsWith("+json.dumps(target)+") && !!document.querySelector('.bug-detail form fieldset:not(:disabled)')")

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
                wait("[...document.querySelectorAll('.detailed-test-cases button')].some(b=>b.textContent.trim()==="+json.dumps('Open Manual execution and history for '+case['stable_id'])+")")
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
                wait("document.querySelector('.requirement-detail-heading')?.innerText.includes('fixture account credentials.')")
                js("[...document.querySelectorAll('.requirement-detail-page > details')].find(d=>d.querySelector('summary')?.textContent==='Version history and traceability').open=true")
                wait("document.body.innerText.includes('Current requirement content version: "+str(old+1)+"')")
                graph=request('GET',f'/api/requirements/{rid}/traceability')
                assert graph['sqa_review_status']=='Pending' and graph['current_content_revision']==old+1
                assert len(graph['executions'])==3 and graph['reviews'][-1]['content_revision']==old
                assert graph['bugs'][0]['id']==bid
                assert any(v['content_revision']==old for v in graph['versions'])
                # Review the NEW source version explicitly, without carrying the
                # prior approval or historical passing result forward.
                click('Submit saved requirement for SQE review')
                wait("document.body.innerText.includes('Ready for Review')")
                login('engineer@example.com')
                for status in ('In Review','Needs Revision'):
                    wait("!!document.querySelector('#review-status')")
                    js("(()=>{const e=document.querySelector('#review-status');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,"+json.dumps(status)+");e.dispatchEvent(new Event('change',{bubbles:true}));})()")
                    fill('#reviewer-notes','Current source reviewed: analysis and stale cases need revision before current-version verification.')
                    click('Save Review')
                    wait("document.querySelector('.sqa-review .detail-section-heading span')?.textContent==="+json.dumps(status))
                reviewed=request('GET',f'/api/requirements/{rid}')['requirement']
                assert reviewed['reviewed_content_revision']==old+1 and reviewed['sqa_review_status']=='Needs Revision'
                assert request('GET',f'/api/requirements/{rid}/traceability')['reviews'][-1]['content_revision']==old+1
                js("location.hash='dashboard'")
                wait("document.body.innerText.includes('Current-version review and test evidence')")
                dashboard=request('GET','/api/dashboard')
                assert dashboard['approved_count']==0 and dashboard['requirements_with_linked_cases']==0
                assert dashboard['needs_revision_count']==1
                assert dashboard['open_bugs_by_severity']['Critical']==1
                assert sum(dashboard['latest_execution_counts'].values())==0
                sizes=js("(async()=>{const values=[];for(const p of ['/api/reports/project.pdf','/api/exports/requirements.csv']){const r=await fetch(p);values.push({status:r.status,size:(await r.arrayBuffer()).byteLength});}return values;})()")
                assert all(v['status']==200 and v['size']>500 for v in sizes)
                assert len(calls)==2
                assert js("document.body.innerText.includes('Requirements needing review')")
                # Paint offscreen lazy rows for a full-page screenshot only.
                js("document.querySelectorAll('.dashboard-requirement-row').forEach(e=>e.style.contentVisibility='visible')")
                # Actual export controls: delayed transport, rapid clicks, failure and explicit retry.
                js("window.downloads=[];window.anchorClick=HTMLAnchorElement.prototype.click;HTMLAnchorElement.prototype.click=function(){if(this.download){window.downloads.push(this.download);return;}return window.anchorClick.call(this);};window.exportRequests=0;window.exportFetch=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).includes('/api/reports/project.pdf')){window.exportRequests++;await new Promise(r=>setTimeout(r,700));}if(window.failCsv&&String(a[0]).includes('/api/exports/requirements.csv')){window.failCsv=false;return new Response(JSON.stringify({error:'Synthetic unavailable export; retry.'}),{status:503,headers:{'Content-Type':'application/json'}});}return window.exportFetch(...a);};const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Export Project PDF');b.click();b.click();")
                wait("document.body.innerText.includes('Downloading PDF')")
                assert js("window.exportRequests===1")
                wait("window.downloads.length===1")
                js("window.failCsv=true")
                click('Export CSV')
                wait("document.body.innerText.includes('Synthetic unavailable export; retry.')")
                click('Export CSV')
                wait("window.downloads.length===2")
                assert js("window.downloads.includes('project-quality-report.pdf') && window.downloads.includes('requirements.csv')")
                # Returning from a public page with a persisted cookie must still restore a protected route.
                js("location.hash='home';location.reload()")
                wait("document.body.innerText.includes('Bring clarity to requirements')")
                js("location.hash='dashboard'")
                wait("document.body.innerText.includes('All Requirements') && document.body.innerText.includes('SQA Engineer')")
                for width in (360,768,1366):
                    cdp('Emulation.setDeviceMetricsOverride',dict(width=width,height=900,deviceScaleFactor=1,mobile=width<500))
                    assert js("document.documentElement.scrollWidth<=innerWidth"),('dashboard',width)
                    image=cdp('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
                    (Path(__file__).parent/f'dashboard-{width}.png').write_bytes(base64.b64decode(image['data']))
                js("location.hash='requirement/"+str(rid)+"'")
                wait("document.body.innerText.includes('Edited sign-in test case')")
                cdp('Emulation.setDeviceMetricsOverride',dict(width=360,height=900,deviceScaleFactor=1,mobile=True))
                assert js("document.documentElement.scrollWidth<=innerWidth"),'detail mobile overflow'
                image=cdp('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
                (Path(__file__).parent/'detail-360.png').write_bytes(base64.b64decode(image['data']))
                cdp('Emulation.setDeviceMetricsOverride',dict(width=1366,height=900,deviceScaleFactor=1,mobile=False))
                login('manager@example.com')
                admin_session=request('GET','/api/auth/me')
                assert admin_session['user']['role']=='admin'
                assert request('GET','/api/project')['project']['id']=='current'
                click('Logout');wait("!!document.querySelector('#login-email')")
                denied=js("(async()=>{const out=[];for(const p of ['/api/project','/api/dashboard','/api/requirements/"+str(rid)+"/traceability','/api/exports/requirements.csv'])out.push((await fetch(p)).status);return out;})()")
                assert denied==[401]*4
                seq+=1
                ws.send(json.dumps({'id':seq,'method':'Page.captureScreenshot','params':{'format':'png','captureBeyondViewport':True}}))
                while True:
                    capture=json.loads(ws.recv(timeout=15))
                    if capture.get('id')==seq:
                        import base64
                        (Path(__file__).parent/'dashboard.png').write_bytes(base64.b64decode(capture['result']['data']))
                        break
                print(json.dumps(dict(real_browser_auth_api_sqlite=True,provider='MOCKED',provider_calls=len(calls),external_application_tested=False,all_three_role_logins='passed',logout_protected_resources=denied,ai_retry_edit_generated_drafts='passed',case_edit_fail_bug_duplicate_guard='passed',passing_retest_close_failed_retest_reopen='passed',reload_history='passed',version_change_preserves_evidence_invalidates_approval='passed',dashboard_matches_records='passed',report_downloads=sizes,review_actions='UI form; source/case/execution/bug actions also use UI',login_double_submit='one POST',public_auth_requests=0,login_layout_widths=[360,768,1366],export_buttons='duplicate guard and explicit retry passed',public_to_protected_session_restore='passed')))
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
finally:
    server.shutdown()
    server.server_close()
    fixture.tearDown()
