"""Local browser fixture. Synthetic users and temporary SQLite, never configured DB."""
import os
os.environ['DATABASE_URL']=''
os.environ['GEMINI_API_KEY']=''
import app
from test_admin_dashboard import ManagerTests
from test_ai_workflow import valid_analysis
from unittest.mock import patch
ManagerTests.setUpClass()
f=ManagerTests();f.setUp()
app.app.config.update(LOCAL_HTTP_DEVELOPMENT=True,SESSION_COOKIE_SECURE=False,TESTING=False)
app.frontend_origins.append('http://127.0.0.1:5173')
# Deterministic provider fixture only; browser still uses real auth, API and DB.
seen=set()
def provider(requirement):
    if '[retry]' in requirement['title'] and requirement['title'] not in seen:
        seen.add(requirement['title'])
        return {'status':'network_error','analysis':None}
    return {'status':'success','analysis':valid_analysis()}
patcher=patch('analyzers.ai_analyzer.analyze_with_llm',side_effect=provider)
patcher.start()
try: app.app.run(host='127.0.0.1',port=5000,debug=False,use_reloader=False)
finally: patcher.stop();f.tearDown()
