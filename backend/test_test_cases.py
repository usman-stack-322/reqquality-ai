"""Real API/SQLite case and manual-execution tests. Gemini calls are MOCKED."""
import json
import unittest
from unittest.mock import patch
import app
import test_admin_dashboard as fixtures
from test_ai_workflow import valid_analysis


class DetailedCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.f=fixtures.ManagerTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.analyst=self.f.client(2); self.engineer=self.f.client(3); self.admin=self.f.admin
        self.source=dict(title='Read own tickets',description='An authenticated customer can view their own tickets.',requirement_type='Functional',priority='High')
        self.r=self.write('post','/api/requirements',self.source,self.analyst).json['requirement']
        self.case=dict(title='View own ticket',category='Positive',preconditions=['A customer owns a ticket.'],test_data='Customer A; ticket owned by A.',test_steps=['Request the owned ticket.','Inspect the returned ticket.'],expected_result='The customer can view the owned ticket.',test_type='Functional',priority='High',criterion_codes=[],clarification_notes='')

    def write(self,method,path,data,client=None,headers=None):
        return getattr(client or self.engineer,method)(path,json=data,headers={**fixtures.HEADERS,**(headers or {})})

    def base(self,sid=None,suffix=''):
        return f"/api/requirements/{self.r['id']}/test-cases"+(f'/{sid}' if sid else '')+suffix

    def test_explicit_ai_clarification_markers_block_approval_and_completed_execution(self):
        analysis=valid_analysis()
        analysis['test_scenarios'][0]['expected_result']='BLOCKED pending clarification: [TO BE CONFIRMED: response target].'
        with patch('analyzers.ai_analyzer.analyze_with_llm',return_value=dict(status='success',analysis=analysis)):
            generated=self.write('post','/api/analyze-requirement',self.source,self.analyst)
        saved=self.write('post','/api/requirements',{**self.source,'analysis':generated.json},self.analyst)
        self.assertEqual(saved.status_code,201,saved.json);self.r=saved.json['requirement']
        case=self.engineer.get(self.base()).json['test_cases'][0];sid=case['id']
        self.assertTrue(case['clarification_notes'])
        run=dict(case_revision=case['case_revision'],status='Pass',actual_result='Cannot establish unresolved expected behavior.',environment='Fixture QA',build='fixture')
        self.assertEqual(self.write('post',self.base(sid,'/executions'),run).status_code,409)
        self.assertEqual(self.write('post',self.base(sid,'/executions'),{**run,'status':'Blocked','blocked_reason':'Source target requires stakeholder clarification.'}).status_code,201)
        # An old row with no persisted flag must still honor its explicit marker.
        self.f.sql("UPDATE test_scenarios SET clarification_notes='' WHERE id=?",(sid,))
        self.assertEqual(self.write('post',self.base(sid,'/executions'),run).status_code,409)
        response=self.write('patch',self.base(sid,'/review'),dict(revision=self.r['revision'],case_revision=case['case_revision'],review_status='In Review'))
        self.assertEqual(response.status_code,200,response.json);self.r=response.json['requirement']
        updated=self.engineer.get(self.base()).json['test_cases'][0]
        self.assertEqual(self.write('patch',self.base(sid,'/review'),dict(revision=self.r['revision'],case_revision=updated['case_revision'],review_status='Approved')).status_code,409)
        edited=self.write('patch',self.base(sid),{**updated,'revision':self.r['revision'],'clarification_notes':''})
        self.assertEqual(edited.status_code,200,edited.json)
        self.assertTrue(self.engineer.get(self.base()).json['test_cases'][0]['clarification_notes'])

    def reload(self):
        self.r=self.engineer.get(f"/api/requirements/{self.r['id']}").json['requirement']

    def create(self,**changes):
        response=self.write('post',self.base(),{**self.case,**changes,'revision':self.r['revision']})
        self.assertEqual(response.status_code,201,response.json)
        self.r=response.json['requirement']
        return next(c for c in self.engineer.get(self.base()).json['test_cases'] if c['id']==response.json['test_case_id'])

    def run_case(self,c,status='Pass',**changes):
        return self.write('post',self.base(c['id'],'/executions'),dict(status=status,case_revision=c['case_revision'],actual_result='Observed the correct ticket.',environment='Local test environment',build='fixture-build-1',**changes))

    def test_creation_editing_links_and_immutable_case_versions(self):
        criterion=self.f.criteria(self.r['id'])
        c=self.create(criterion_codes=['AC-1'])
        self.assertEqual(c['review_status'],'Draft'); self.assertEqual(c['latest_execution_status'],'Not Run')
        self.assertEqual(c['requirement_revision'],self.r['content_revision'])
        self.assertEqual(c['criterion_codes'],['AC-1'])
        original_version=self.engineer.get(self.base(c['id'],'/versions')).json['versions'][0]
        edited=self.write('patch',self.base(c['id']),{**c,'title':'Revised detailed case','test_data':'Different fixture account','revision':self.r['revision']})
        self.assertEqual(edited.status_code,200,edited.json)
        self.r=edited.json['requirement']
        current=self.engineer.get(self.base()).json['test_cases'][0]
        self.assertEqual(current['id'],c['id']); self.assertEqual(current['scenario_code'],c['scenario_code'])
        self.assertEqual(current['case_revision'],2); self.assertEqual(current['criterion_codes'],['AC-1'])
        self.assertEqual(current['review_status'],'Draft')
        versions=self.engineer.get(self.base(c['id'],'/versions')).json['versions']
        self.assertEqual(len(versions),2); self.assertEqual(versions[-1],original_version)
        self.assertEqual(versions[-1]['snapshot']['test_data'],self.case['test_data'])
        self.assertEqual(versions[-1]['snapshot']['requirement_snapshot']['acceptance_criteria'][0]['criterion_code'],'AC-1')
        self.assertEqual(self.write('patch',self.base(c['id']),{**c,'revision':self.r['revision']}).status_code,409)

    def test_each_execution_and_retest_preserves_original_evidence_and_identity(self):
        c=self.create()
        first=self.run_case(c,'Fail',evidence_reference='evidence://first-failure',notes='Observed a mismatch.')
        self.assertEqual(first.status_code,201,first.json)
        second=self.run_case(c,'Pass',evidence_reference='evidence://successful-retest')
        self.assertEqual(second.status_code,201)
        self.assertNotEqual(first.json['execution']['id'],second.json['execution']['id'])
        history=self.engineer.get(self.base(c['id'],'/executions')).json
        self.assertEqual(history['total'],2)
        self.assertEqual(history['executions'][-1]['evidence_reference'],'evidence://first-failure')
        self.assertEqual(history['executions'][-1]['status'],'Fail')
        for entry in history['executions']:
            self.assertEqual(entry['tester_id'],3); self.assertTrue(entry['tester_name']); self.assertTrue(entry['executed_at'].endswith('Z'))
            self.assertEqual(entry['environment'],'Local test environment'); self.assertEqual(entry['build'],'fixture-build-1')
            self.assertEqual(entry['snapshot']['test_steps'],self.case['test_steps'])
        self.reload()
        self.assertEqual(self.r['review_status'],'Draft')
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['latest_execution_status'],'Pass')
        self.assertEqual(self.engineer.patch(self.base(c['id'],'/executions')).status_code,405)
        self.assertEqual(self.engineer.delete(self.base(c['id'],'/executions')).status_code,405)
        self.assertEqual(self.engineer.get(self.base(c['id'],'/executions')).json,history)

    def test_validation_completion_blocking_and_no_forged_identity(self):
        c=self.create()
        for status in ('Pass','Fail'):
            response=self.write('post',self.base(c['id'],'/executions'),dict(status=status,case_revision=c['case_revision'],actual_result=' ',environment='QA',build='b1'))
            self.assertEqual(response.status_code,400)
        blocked=self.run_case(c,'Blocked')
        self.assertEqual(blocked.status_code,400)
        self.assertEqual(self.run_case(c,'Blocked',blocked_reason='Test service is unavailable.').status_code,201)
        self.assertEqual(self.run_case(c,'Not Run').status_code,201)
        for changes in ({'tester_id':1},{'executed_at':'forged'},{'status':['Pass']},{'environment':''},{'build':''}):
            data=dict(status='Pass',case_revision=c['case_revision'],actual_result='Observed result.',environment='QA',build='b1')
            self.assertEqual(self.write('post',self.base(c['id'],'/executions'),{**data,**changes}).status_code,400)
        self.assertEqual(self.engineer.get(self.base(c['id'],'/executions')).json['total'],2)

    def test_permission_matrix_project_revocation_and_nested_id_checks(self):
        c=self.create()
        for client in (self.analyst,self.admin,self.f.client()):
            self.assertIn(self.write('post',self.base(),{**self.case,'revision':self.r['revision']},client).status_code,(401,403))
            self.assertIn(self.write('post',self.base(c['id'],'/executions'),{},client).status_code,(401,403))
        self.f.sql("UPDATE role_permissions SET enabled=0 WHERE role='SQA Engineer' AND permission='execute_test_cases'")
        self.assertEqual(self.run_case(c).status_code,403)
        self.f.sql("UPDATE role_permissions SET enabled=1 WHERE role='SQA Engineer' AND permission='execute_test_cases'")
        self.f.sql("UPDATE role_permissions SET enabled=0 WHERE role='SQA Engineer' AND permission='review_requirements'")
        self.assertEqual(self.run_case(c).status_code,201)  # execution is separately granted
        self.assertEqual(self.write('patch',self.base(c['id']),{**c,'revision':self.r['revision']}).status_code,403)
        other=self.f.requirement()
        self.assertEqual(self.engineer.get(f'/api/requirements/{other}/test-cases/{c["id"]}/executions').status_code,404)
        self.assertEqual(self.engineer.get(self.base()+'?project_id=other').status_code,403)
        self.f.sql('UPDATE users SET project_access=0 WHERE id=3')
        for path in (self.base(),self.base(c['id'],'/versions'),self.base(c['id'],'/executions')):
            self.assertEqual(self.engineer.get(path).status_code,403)
        self.assertEqual(self.run_case(c).status_code,403)

    def test_csrf_missing_or_stale_case_is_rejected(self):
        c=self.create()
        response=self.engineer.post(self.base(c['id'],'/executions'),json={})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.run_case({**c,'case_revision':99}).status_code,409)
        self.assertFalse(self.f.sql('SELECT * FROM test_executions'))

    def test_case_edits_and_source_edits_cannot_rewrite_execution_snapshots(self):
        self.f.criteria(self.r['id'])
        c=self.create(criterion_codes=['AC-1'])
        self.assertEqual(self.run_case(c).status_code,201)
        evidence=self.engineer.get(self.base(c['id'],'/executions')).json['executions'][0]
        edit=self.write('patch',self.base(c['id']),{**c,'test_steps':['Different steps.'],'revision':self.r['revision']})
        self.assertEqual(edit.status_code,200,edit.json);self.r=edit.json['requirement']
        c=self.engineer.get(self.base()).json['test_cases'][0]
        self.assertEqual(c['latest_execution_status'],'Not Run')
        self.assertEqual(self.engineer.get(self.base(c['id'],'/executions')).json['executions'][0],evidence)
        changed=self.write('patch',f'/api/requirements/{self.r["id"]}',{**self.source,'description':'Changed source behavior.','revision':self.r['revision'],'acceptance_criteria':['A new criterion.']},self.analyst)
        self.assertEqual(changed.status_code,200,changed.json);self.r=changed.json['requirement']
        preserved=self.engineer.get(self.base()).json['test_cases'][0]
        self.assertEqual(preserved['criterion_codes'],['AC-1']);self.assertTrue(preserved['stale'])
        self.assertEqual(self.run_case(preserved).status_code,409)
        self.assertEqual(self.engineer.get(self.base(c['id'],'/executions')).json['executions'][0],evidence)
        rebased=self.write('patch',self.base(c['id']),{**preserved,'criterion_codes':['AC-001'],'revision':self.r['revision']})
        self.assertEqual(rebased.status_code,200,rebased.json)

    def test_unresolved_expectation_is_flagged_and_can_be_recorded_blocked(self):
        c=self.create(expected_result='BLOCKED pending clarification of the required response time.',clarification_notes='Response time and workload are undecided.',category='Boundary',test_type='Performance')
        self.assertEqual(self.run_case(c).status_code,409)
        self.assertEqual(self.run_case(c,'Blocked',blocked_reason='Awaiting stakeholder response-time target.').status_code,201)

    def test_ai_reanalysis_archives_cases_without_deleting_links_or_runs(self):
        self.f.criteria(self.r['id'])
        c=self.create(criterion_codes=['AC-1'])
        self.assertEqual(self.run_case(c).status_code,201)
        evidence=self.engineer.get(self.base(c['id'],'/executions')).json['executions'][0]
        with patch('analyzers.ai_analyzer.analyze_with_llm',return_value={'status':'success','analysis':valid_analysis()}):
            analysis=self.write('post','/api/analyze-requirement',{**self.source,'requirement_id':self.r['id'],'requirement_revision':self.r['revision']},self.analyst)
        self.assertEqual(analysis.status_code,200,analysis.json)
        accepted=self.write('patch',f'/api/requirements/{self.r["id"]}/analysis',dict(analysis=analysis.json,title=self.r['title'],description=self.r['description'],revision=self.r['revision']),self.analyst)
        self.assertEqual(accepted.status_code,200,accepted.json)
        cases=self.engineer.get(self.base()).json['test_cases']
        old=next(v for v in cases if v['id']==c['id'])
        self.assertTrue(old['archived']); self.assertEqual(old['criterion_codes'],['AC-1'])
        self.assertEqual(self.engineer.get(self.base(c['id'],'/executions')).json['executions'][0],evidence)
        new=next(v for v in cases if v['id']!=c['id'])
        self.assertEqual(new['review_status'],'Draft');self.assertEqual(new['latest_execution_status'],'Not Run')
        self.assertEqual(self.run_case(old).status_code,409)

    def test_execution_idempotency_is_distinct_from_a_new_retest(self):
        c=self.create()
        payload=dict(status='Pass',case_revision=c['case_revision'],actual_result='Observed result.',environment='QA',build='b1')
        headers={'Idempotency-Key':'manual-execution-request-1'}
        first=self.write('post',self.base(c['id'],'/executions'),payload,headers=headers)
        retry=self.write('post',self.base(c['id'],'/executions'),payload,headers=headers)
        self.assertEqual(first.status_code,201);self.assertEqual(first.json,retry.json)
        self.assertEqual(self.write('post',self.base(c['id'],'/executions'),{**payload,'notes':'changed'},headers=headers).status_code,409)
        retest=self.write('post',self.base(c['id'],'/executions'),payload,headers={'Idempotency-Key':'manual-execution-request-2'})
        self.assertNotEqual(first.json['execution']['id'],retest.json['execution']['id'])
        self.assertEqual(self.engineer.get(self.base(c['id'],'/executions')).json['total'],2)

    def test_case_review_and_material_edit_reopens_draft(self):
        c=self.create()
        self.assertEqual(self.write('patch',self.base(c['id'],'/review'),dict(revision=self.r['revision'],case_revision=c['case_revision'],review_status='Approved')).status_code,409)
        for status in ('In Review','Approved'):
            result=self.write('patch',self.base(c['id'],'/review'),dict(revision=self.r['revision'],case_revision=c['case_revision'],review_status=status))
            self.assertEqual(result.status_code,200,result.json);self.r=result.json['requirement']
            c=self.engineer.get(self.base()).json['test_cases'][0]
        self.assertEqual(c['review_status'],'Approved')
        edited=self.write('patch',self.base(c['id']),{**c,'title':'Edited after review','revision':self.r['revision']})
        self.assertEqual(edited.status_code,200)
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['review_status'],'Draft')

    def test_history_pagination_and_distinct_concurrent_retests(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        c=self.create()
        clients=[self.f.client(3),self.f.client(3)]
        barrier=Barrier(2)
        def run(index):
            barrier.wait(timeout=5)
            return self.write('post',self.base(c['id'],'/executions'),dict(status='Pass',case_revision=c['case_revision'],actual_result=f'Observation {index}',environment='QA',build='b1'),clients[index],{'Idempotency-Key':f'concurrent-retest-{index}'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,range(2)))
        self.assertEqual([r.status_code for r in results],[201,201])
        first=self.engineer.get(self.base(c['id'],'/executions')+'?page_size=1').json
        second=self.engineer.get(self.base(c['id'],'/executions')+'?page_size=1&page=2').json
        self.assertEqual(first['total'],2)
        self.assertNotEqual(first['executions'][0]['id'],second['executions'][0]['id'])

    def test_preserved_old_requirement_snapshot_when_stale_case_is_archived(self):
        self.f.criteria(self.r['id'])
        c=self.create(criterion_codes=['AC-1'])
        old_source=self.source['description']
        changed=self.write('patch',f'/api/requirements/{self.r["id"]}',{**self.source,'description':'A completely different requirement.','revision':self.r['revision'],'acceptance_criteria':['Different criterion.']},self.analyst)
        self.assertEqual(changed.status_code,200);self.r=changed.json['requirement']
        payload={**self.source,'description':self.r['description'],'requirement_id':self.r['id'],'requirement_revision':self.r['revision']}
        with patch('analyzers.ai_analyzer.analyze_with_llm',return_value={'status':'success','analysis':valid_analysis()}):
            analysis=self.write('post','/api/analyze-requirement',payload,self.analyst)
        accepted=self.write('patch',f'/api/requirements/{self.r["id"]}/analysis',dict(analysis=analysis.json,title=self.r['title'],description=self.r['description'],revision=self.r['revision']),self.analyst)
        self.assertEqual(accepted.status_code,200,accepted.json)
        archived_version=self.engineer.get(self.base(c['id'],'/versions')).json['versions'][0]['snapshot']
        self.assertTrue(archived_version['archived'])
        self.assertEqual(archived_version['requirement_snapshot']['description'],old_source)
        self.assertEqual(archived_version['requirement_snapshot']['acceptance_criteria'][0]['criterion_code'],'AC-1')

    def test_structural_validation_rejects_wrong_links_and_empty_steps(self):
        for changes in ({'test_steps':[]},{'title':''},{'criterion_codes':['unknown']},{'priority':[]},{'category':{}},{'preconditions':['']},{'test_type':'Invented type'}):
            result=self.write('post',self.base(),{**self.case,**changes,'revision':self.r['revision']})
            self.assertEqual(result.status_code,400,result.json)
        self.assertFalse(self.f.sql('SELECT * FROM test_scenarios'))

    def test_case_authorization_keeps_requirement_author_review_restriction(self):
        self.f.sql('UPDATE requirements SET created_by_user_id=3 WHERE id=?',(self.r['id'],))
        self.assertEqual(self.write('post',self.base(),{**self.case,'revision':self.r['revision']}).status_code,403)


if __name__=='__main__': unittest.main()
