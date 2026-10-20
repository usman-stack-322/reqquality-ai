"""Real browser regression: built frontend with synthetic auth outage, no real DB.

Run after npm run build using backend/.venv/Scripts/python.exe.
"""
import json
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from websockets.sync.client import connect

root = Path(__file__).resolve().parents[2]
lookups = []


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(root / 'frontend' / 'dist'), **kwargs)

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path.startswith('/api/'):
            lookups.append(self.path)
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"code":"database_unavailable","error":"Synthetic database outage"}')
        else:
            super().do_GET()


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
origin = f'http://127.0.0.1:{server.server_port}'
try:
    with tempfile.TemporaryDirectory() as profile:
        chrome = subprocess.Popen([
            r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless=new',
            '--disable-gpu', '--no-first-run', '--no-default-browser-check',
            '--remote-debugging-port=0', '--no-proxy-server', f'--user-data-dir={profile}',
            origin + '/#home'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            portfile = Path(profile) / 'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():
                    break
                time.sleep(.1)
            port = portfile.read_text().splitlines()[0]
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=5))
            tab = next(tab for tab in tabs if tab.get('type') == 'page' and tab.get('url', '').startswith(origin))
            with connect(tab['webSocketDebuggerUrl'], ping_interval=None) as ws:
                seq = 0

                def js(code):
                    global seq
                    seq += 1
                    ws.send(json.dumps({'id': seq, 'method': 'Runtime.evaluate', 'params': {
                        'expression': code, 'returnByValue': True, 'awaitPromise': True}}))
                    while True:
                        result = json.loads(ws.recv(timeout=10))
                        if result.get('id') == seq:
                            assert 'exceptionDetails' not in result.get('result', {}), result
                            return result.get('result', {}).get('result', {}).get('value')

                def wait(condition):
                    for _ in range(100):
                        if js(condition):
                            return
                        time.sleep(.05)
                    raise AssertionError(condition + ': ' + str(js('({url:location.href,text:document.body?.innerText})')))

                wait("document.body?.innerText.includes('Bring clarity to requirements')")
                wait("performance.getEntriesByType('resource').some(r => r.name.includes('/api/auth/me'))")
                assert lookups == ['/api/auth/me'], lookups
                assert not js("document.body.innerText.includes('Session unavailable')")
                js("location.hash='login'")
                wait("!!document.querySelector('#login-email')")
                js("location.hash='dashboard'")
                wait("document.body.innerText.includes('Session unavailable')")
                assert not js("document.body.innerText.includes('Export CSV')")
                js("location.hash='home'")
                wait("document.body.innerText.includes('Bring clarity to requirements')")
                assert lookups == ['/api/auth/me'], lookups
                print(json.dumps({'public_outage_rendering': 'passed', 'protected_gate': 'passed',
                                  'session_requests': len(lookups), 'automatic_retry_requests': 0}))
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
finally:
    server.shutdown()
    server.server_close()
