"""Current real localhost backend, synthetic credentials; no successful login claim."""
import base64
import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from websockets.sync.client import connect

root = Path(__file__).resolve().parent
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
profile = root/'chrome-profile'/str(time.time_ns())
browser = subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', f'--remote-debugging-port={port}', f'--user-data-dir={profile}', 'http://127.0.0.1:5173/#login'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
ws = None
try:
    for _ in range(100):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1))
            tab = next(t for t in tabs if '127.0.0.1:5173' in t.get('url', ''))
            break
        except Exception:
            time.sleep(.1)
    ws = connect(tab['webSocketDebuggerUrl'], open_timeout=10, ping_interval=None)
    sequence = 0
    events = []

    def call(method, params=None):
        global sequence
        sequence += 1
        ident = sequence
        ws.send(json.dumps(dict(id=ident, method=method, params=params or {})))
        while True:
            message = json.loads(ws.recv(timeout=30))
            if message.get('id') == ident:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message.get('result', {})
            events.append(message)

    def js(code):
        result = call('Runtime.evaluate', dict(expression=code, awaitPromise=True, returnByValue=True))
        if 'exceptionDetails' in result:
            raise RuntimeError(str(result['exceptionDetails']))
        return result.get('result', {}).get('value')

    def wait(code):
        for _ in range(250):
            if js(code):
                return
            time.sleep(.1)
        raise AssertionError(code)

    call('Page.enable')
    call('Runtime.enable')
    call('Network.enable')
    wait("Boolean(document.querySelector('#login-email'))")
    js("(() => {for(const [s,v] of [['#login-email','diagnostic-no-account@example.invalid'],['#login-password','synthetic-not-a-user-password']]) {const e=document.querySelector(s);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));}})()")
    started = time.perf_counter()
    js("document.querySelector('form').requestSubmit()")
    wait("document.body.innerText.includes('The database is temporarily unavailable')")
    elapsed = round((time.perf_counter()-started)*1000, 2)
    rows = js("performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')).map(r=>({path:new URL(r.name).pathname,ms:r.duration,bytes:r.decodedBodySize}))")
    logins = [r for r in rows if r['path'] == '/api/auth/login']
    assert len(logins) == 1, rows
    assert not any('analyze' in r['path'] for r in rows)
    assert js("document.querySelector('#login-email').value") == 'diagnostic-no-account@example.invalid'
    assert js("location.hash") == '#login'
    evidence = dict(environment='real configured PostgreSQL backend, Vite dev proxy, Chrome', outcome='database outage reproduced; not authenticated', elapsed_ms=elapsed, login_requests=len(logins), resources=rows, ai_requests=0, email_preserved=True, console_exceptions=sum(e.get('method') == 'Runtime.exceptionThrown' for e in events))
    screenshot = call('Page.captureScreenshot', dict(format='png', captureBeyondViewport=True))
    (root/'browser-failure.png').write_bytes(base64.b64decode(screenshot['data']))
    (root/'browser-failure.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))
finally:
    if ws is not None:
        try:
            ws.send(json.dumps(dict(id=999999, method='Browser.close')))
        except Exception:
            pass
        ws.close()
    if browser.poll() is None:
        browser.terminate()
        browser.wait(timeout=10)
