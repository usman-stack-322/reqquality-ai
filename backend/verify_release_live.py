"""Opt-in real-provider API checks with synthetic inputs and disposable accounts/SQLite."""
import argparse
import json
import logging
from pathlib import Path
from time import perf_counter
import app
from test_admin_dashboard import ManagerTests,HEADERS

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    logging.disable(logging.CRITICAL)
    ManagerTests.setUpClass();f=ManagerTests();f.setUp()
    try:
        analyst=f.client(2);engineer=f.client(3)
        cases=json.loads((Path(__file__).parent/'evaluation/requirement_cases.json').read_text())
        records=[]
        for case in (v for v in cases if v['id'] in ('clear','security','performance_missing')):
            project=f.admin.get('/api/project').json['project']
            assert f.admin.patch('/api/project',json=dict(revision=project['revision'],context=case['project_context']),headers=HEADERS).status_code==200
            body={key:case[key] for key in ('title','description','requirement_type')};body['priority']='Medium'
            r=analyst.post('/api/requirements',json=body,headers=HEADERS).json['requirement']
            start=perf_counter()
            response=analyst.post('/api/analyze-requirement',json={**body,'requirement_id':r['id'],'requirement_revision':r['revision']},headers=HEADERS)
            item=dict(case=case['id'],request_ms=round((perf_counter()-start)*1000,2),status=response.status_code,provider='REAL',application_database='disposable SQLite')
            item['original_unchanged']=analyst.get(f'/api/requirements/{r["id"]}').json['requirement']['description']==body['description']
            assert item['original_unchanged']
            if response.status_code==200:
                analysis=response.json
                saved=analyst.patch(f'/api/requirements/{r["id"]}/analysis',json=dict(revision=r['revision'],analysis=analysis,title=r['title'],description=r['description'],analysis_edits=dict(improved_requirement=analysis['improved_requirement'])),headers=HEADERS)
                assert saved.status_code==200,saved.status_code
                stored=saved.json['requirement'];assert stored['description']==body['description'] and stored['review_status']=='Draft'
                item.update(persisted_draft=True,case_count=len(stored['test_scenarios']))
                # GET reuse cannot call provider, and must keep saved artifacts unchanged.
                assert analyst.get(f'/api/requirements/{r["id"]}').json['requirement']['test_scenarios']==stored['test_scenarios']
                blocked=[s for s in stored['test_scenarios'] if s['clarification_notes']]
                item['clarification_flagged_cases']=len(blocked)
                if blocked:
                    s=blocked[0]
                    run=engineer.post(f'/api/requirements/{r["id"]}/test-cases/{s["id"]}/executions',json=dict(case_revision=s['case_revision'],status='Pass',actual_result='Synthetic assertion must be rejected while unresolved.',environment='Synthetic QA',build='synthetic'),headers=HEADERS)
                    assert run.status_code==409,run.status_code
                    item['unresolved_pass_rejected']=run.status_code
            else:
                item['error_code']=response.json.get('code')
                item['saved_success_rows']=f.sql('SELECT COUNT(*) AS n FROM requirement_analysis_drafts WHERE requirement_id=?',(r['id'],))[0]['n']
                assert item['saved_success_rows']==0
            records.append(item)
            print(json.dumps(item),flush=True)
        Path(args.output).write_text(json.dumps(records,indent=2),encoding='utf-8')
    finally:f.tearDown()

if __name__=='__main__':main()
