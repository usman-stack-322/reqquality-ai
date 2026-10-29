"""One live Gemini request against synthetic context in disposable SQLite only."""
import json
import logging
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from test_review_assistant import ReviewAssistantTests
logging.disable(logging.CRITICAL)
ReviewAssistantTests.setUpClass()
fixture=ReviewAssistantTests();fixture.setUp()
try:
    session=fixture.open()
    response=fixture.write('post',fixture.path(session['id'],'/messages'),{
        'feedback':'Make the expected result more specific using only the source requirement. Preserve the existing checks. If the source is insufficient, ask for clarification.',
        'request_key':'live-synthetic-review'})
    data=response.json
    result={'database':'isolated SQLite','provider':'live Gemini','http_status':response.status_code,
            'saved_case_unchanged':fixture.engineer.get(fixture.base()).json['test_cases'][0]['case_revision']==1}
    if response.status_code==200:
        result.update(status='passed',response_kind=data['turn']['proposal']['kind'],validated_changes=len(data['turn']['proposal']['changes']))
    else:
        result.update(status='blocked',error=data.get('error','Request failed'))
    (root/'audit/ai-review-live.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    if result['status']!='passed':sys.exit(1)
finally:fixture.doCleanups()
