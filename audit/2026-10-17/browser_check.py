"""Chrome CDP smoke test against local Flask + Vite and synthetic provider fixture."""
import base64,json,socket,subprocess,time,urllib.request
from pathlib import Path
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parent
TITLE='Browser sign in [retry] '+str(time.time_ns())
profile=ROOT/'chrome-profile'/str(time.time_ns())
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',f'--remote-debugging-port={port}','--no-proxy-server',f'--user-data-dir={profile}','http://127.0.0.1:5173/#login'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
try:
    for _ in range(100):
        try:
            tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1));break
        except Exception: time.sleep(.1)
    print(json.dumps({'step':'browser_target','url':'http://127.0.0.1:5173/#login','bundle':'production'}),flush=True)
    tab=next((t for t in tabs if '127.0.0.1:5173' in t.get('url','')),tabs[0])
    ws=connect(tab['webSocketDebuggerUrl'],open_timeout=10,ping_interval=None)
    seq=0;events=[]
    def call(method,params={}):
        global seq
        seq+=1;ident=seq
        ws.send(json.dumps({'id':ident,'method':method,'params':params}))
        while True:
            msg=json.loads(ws.recv(timeout=30))
            if msg.get('id')==ident:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
            events.append(msg)
    def js(code):
        r=call('Runtime.evaluate',{'expression':code,'awaitPromise':True,'returnByValue':True})
        if 'exceptionDetails' in r: raise RuntimeError(str(r['exceptionDetails']))
        return r.get('result',{}).get('value')
    def wait(code):
        for _ in range(120):
            if js(code): return
            time.sleep(.1)
        raise AssertionError('UI wait failed: '+code+'\n'+str(js('({url:location.href,state:document.readyState,text:document.body.innerText})'))+'\n'+str(call('Page.getFrameTree')))
    def click(text):
        assert js("(() => {const e=[...document.querySelectorAll('button,a')].find(e=>e.textContent.trim()==="+json.dumps(text)+");if(e){e.click();return true;}return false;})()"),text
    def fill(selector,value):
        js("(() => {const e=document.querySelector("+json.dumps(selector)+"); const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,"+json.dumps(value)+");e.dispatchEvent(new Event('input',{bubbles:true}));})()")
    def login(email):
        js("location.hash='login'")
        wait("Boolean(document.querySelector('#login-email'))")
        fill('#login-email',email);fill('#login-password','test-only-password-123')
        js("document.querySelector('form').requestSubmit()")
        wait("location.hash==='#dashboard' && document.body.innerText.includes('All Requirements')")
    call('Page.enable');call('Runtime.enable');call('Network.enable');call('Network.clearBrowserCookies')
    wait("location.host==='127.0.0.1:5173' && document.readyState==='complete'")
    login('analyst@example.com')
    print(json.dumps({'step':'analyst_login','result':'passed'}),flush=True)
    dashboard_count=js("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname==='/api/dashboard').length")
    list_count=js("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname==='/api/requirements').length")
    js("(() => {const e=[...document.querySelectorAll('.dashboard-filters label')].find(l=>l.textContent.startsWith('Filter risk')).querySelector('select');e.value='High';e.dispatchEvent(new Event('change',{bubbles:true}));})()")
    wait("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname==='/api/requirements').length>"+str(list_count))
    assert js("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname==='/api/dashboard').length")==dashboard_count
    print(json.dumps({'step':'queue_filter_does_not_repeat_dashboard_request','result':'passed'}),flush=True)

    js("location.hash='requirements'")
    wait("Boolean(document.querySelector('#requirement-title'))")
    fill('#requirement-title',TITLE);fill('#requirement-description','Registered users can sign in with valid credentials.')
    js("[...document.querySelectorAll('button')].find(e=>e.textContent.includes('Analyze')).click()")
    wait("document.body.innerText.includes('Your input is preserved')")
    assert js("document.querySelector('#requirement-title').value")== TITLE
    js("[...document.querySelectorAll('button')].find(e=>e.textContent.includes('Analyze')).click()")
    wait("Boolean(document.querySelector('.analysis-results'))")
    print(json.dumps({'step':'failed_analysis_preserves_input_and_retry','result':'passed','provider':'mock'}),flush=True)
    js("document.querySelector('.analysis-results input[type=checkbox]').click()")
    js("document.querySelector('form.requirement-form').requestSubmit()")
    wait("document.body.innerText.includes('Requirement saved successfully.')")
    click(TITLE)
    wait("document.body.innerText.includes('Prepare requirement for review')")
    click('Submit saved requirement for SQE review')
    wait("document.body.innerText.includes('Ready for Review')")
    print(json.dumps({'step':'analyze_save_submit','result':'passed','provider':'mock'}),flush=True)
    rid=js("location.hash.split('/')[1]")
    click('Log out');login('engineer@example.com')
    js("location.hash='requirement/"+rid+"'")
    wait("Boolean(document.querySelector('#review-status'))")
    js("document.querySelector('.review-form').requestSubmit()")
    wait("document.body.innerText.includes('SQA review saved.')")
    fill('#reviewer-notes','Specify locked-account behavior.')
    js("(() => {const e=document.querySelector('#review-status');e.value='Needs Revision';e.dispatchEvent(new Event('change',{bubbles:true}));})()")
    js("document.querySelector('.review-form').requestSubmit()")
    wait("!document.querySelector('#review-status') && document.body.innerText.includes('Needs Revision')")
    click('Log out');login('analyst@example.com')
    js("location.hash='requirement/"+rid+"'")
    wait("Boolean(document.querySelector('.workflow-editor textarea'))")
    fill('.workflow-editor textarea','Registered users can sign in with valid credentials. Locked accounts are rejected.')
    click('Save edits as Draft')
    wait("document.querySelector('.requirement-detail-heading .review-status').textContent.trim()==='Draft'")
    click('Submit saved requirement for SQE review')
    wait("document.querySelector('.requirement-detail-heading .review-status').textContent.trim()==='Ready for Review'")
    print(json.dumps({'step':'revision_feedback_edit_resubmit','result':'passed'}),flush=True)
    click('Log out');login('engineer@example.com')
    js("location.hash='requirement/"+rid+"'")
    wait("Boolean(document.querySelector('#review-status'))")
    js("document.querySelector('.review-form').requestSubmit()")
    wait("document.body.innerText.includes('SQA review saved.')")
    js("document.querySelector('.workflow-editor details').open=true")
    js("document.querySelector('.workflow-editor input[type=checkbox]').click()")
    click('Save scenario revision')
    wait("document.body.innerText.includes('Criteria without linked scenarios: None')")

    js("(() => {const e=document.querySelector('#review-status');e.value='Approved';e.dispatchEvent(new Event('change',{bubbles:true}));})()")
    js("document.querySelector('.review-form').requestSubmit()")
    wait("!document.querySelector('#review-status') && document.body.innerText.includes('Approved')")
    assert js("Boolean(document.querySelector('.badge-needs-confirmation'))"), 'Approval must preserve unconfirmed AI content'
    screenshot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})
    (ROOT/'browser-approved.png').write_bytes(base64.b64decode(screenshot['data']))
    print(json.dumps({'step':'sqe_review_approval','result':'passed'}),flush=True)
    click('Log out');login('analyst@example.com')
    js("location.hash='requirement/"+rid+"'")
    wait("Boolean(document.querySelector('.workflow-editor textarea'))")
    fill('.workflow-editor textarea','Registered users can sign in with valid credentials. Locked accounts require stakeholder clarification before implementation.')
    click('Save edits as Draft')
    wait("document.querySelector('.requirement-detail-heading .review-status').textContent.trim()==='Draft'")
    assert js("document.body.innerText.includes('review approved')")
    print(json.dumps({'step':'approved_material_edit_requires_rereview_and_keeps_history','result':'passed'}),flush=True)
    resources=js("performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')).map(r=>({path:new URL(r.name).pathname,ms:Math.round(r.duration)}))")
    errors=[e for e in events if e.get('method')=='Runtime.exceptionThrown']
    print(json.dumps({'step':'browser_evidence','resources':resources,'console_exceptions':len(errors)}),flush=True)
    assert not errors,errors
    ws.close()
finally:
    if 'events' in globals(): (ROOT/'browser-events.json').write_text(json.dumps([e for e in events if e.get('method') in ('Runtime.exceptionThrown','Network.loadingFailed')]),encoding='utf-8')
    if 'ws' in globals():
        try: ws.send(json.dumps({'id':999999,'method':'Browser.close'}))
        except Exception: pass
    if chrome.poll() is None:
        chrome.terminate();chrome.wait(timeout=10)
