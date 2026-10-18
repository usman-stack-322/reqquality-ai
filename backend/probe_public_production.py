"""Six non-destructive anonymous requests; no credentials, login or load testing."""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

results = []
for path in ('/api/auth/me', '/api/dashboard'):
    for sample in range(3):
        start = time.perf_counter()
        request = urllib.request.Request('https://reqquality-api.vercel.app'+path, headers={'User-Agent':'ReqQuality-readonly-verification', 'Cache-Control':'no-cache'})
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        except Exception as error:
            results.append(dict(path=path, sample=sample+1, error=type(error).__name__, ms=round((time.perf_counter()-start)*1000,2)))
            continue
        with response:
            body = response.read()
            results.append(dict(path=path, sample=sample+1, status=response.status, ms=round((time.perf_counter()-start)*1000,2), bytes=len(body), server_timing=response.headers.get('Server-Timing'), cache=response.headers.get('Cache-Control'), vercel_cache=response.headers.get('X-Vercel-Cache')))
Path('audit/reliability-followup/public-production.json').write_text(json.dumps(results,indent=2), encoding='utf-8')
print(json.dumps(results,indent=2))
