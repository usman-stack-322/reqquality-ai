import json, urllib.request, http.cookiejar
from pathlib import Path
values=dict(line.split(': ',1) for line in Path('backend/instance/local-login.txt').read_text().splitlines() if ': ' in line)
client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(path,data=None,csrf=None):
    headers={'Content-Type':'application/json'}
    if csrf: headers['X-CSRF-Token']=csrf
    req=urllib.request.Request('http://127.0.0.1:5173'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
    with client.open(req,timeout=15) as r: return r.status,json.load(r)
for run in range(1,6):
    status,login=call('/api/auth/login',{'email':values['Email'],'password':values['Password']})
    assert status==200
    assert call('/api/auth/me')[1]['authenticated']
    assert call('/api/admin/dashboard')[0]==200
    assert call('/api/auth/me')[1]['authenticated']
    assert call('/api/auth/logout',{},login['csrf_token'])[0]==200
    assert not call('/api/auth/me')[1]['authenticated']
    print(json.dumps({'run':run,'login_dashboard_session_logout':'passed'}))
