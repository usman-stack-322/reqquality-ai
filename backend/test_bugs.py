"""Failed execution → bug → retest workflows with real API and disposable SQLite.

No external application or model is tested by these synthetic observations.
"""
import unittest
from unittest.mock import patch
import app
import test_admin_dashboard as fixtures


class BugWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.f=fixtures.ManagerTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.engineer=self.f.client(3);self.analyst=self.f.client(2);self.admin=self.f.admin
        self.r=self.write('post','/api/requirements',dict(title='Own tickets',description='Customers can view their own tickets.',requirement_type='Functional',priority='High'),self.analyst).json['requirement']
        result=self.write('post',f'/api/requirements/{self.r["id"]}/test-cases',dict(revision=self.r['revision'],title='View an owned ticket',category='Positive',preconditions=['Customer owns a ticket.'],test_steps=['Request the owned ticket.'],expected_result='Owned ticket is shown.',test_data='Synthetic ticket A',test_type='Functional',priority='High',criterion_codes=[]))
        self.r=result.json['requirement'];self.sid=result.json['test_case_id']
        self.case=self.engineer.get(f'/api/requirements/{self.r["id"]}/test-cases').json['test_cases'][0]
        self.failed=self.run_case('Fail')
        self.eid=self.failed['id']

    def write(self,method,path,data,client=None,key=None):
        headers=dict(fixtures.HEADERS)
        if key:headers['Idempotency-Key']=key
        return getattr(client or self.engineer,method)(path,json=data,headers=headers)

    def run_case(self,status,**changes):
        body=dict(status=status,case_revision=self.case['case_revision'],actual_result='Synthetic observed failure.' if status=='Fail' else 'Synthetic observed success.',environment='QA fixture',build='fixture-build',blocked_reason='Fixture unavailable.' if status=='Blocked' else '')
        response=self.write('post',f'/api/requirements/{self.r["id"]}/test-cases/{self.sid}/executions',{**body,**changes})
        self.assertEqual(response.status_code,201,response.json)
        return response.json['execution']

    def draft(self):return self.engineer.get(f'/api/executions/{self.eid}/bugs').json['prefill']

    def create(self,client=None,**changes):
        response=self.write('post',f'/api/executions/{self.eid}/bugs',{**self.draft(),**changes},client)
        self.assertIn(response.status_code,(200,201),response.json)
        return response.json['bug']

    def move(self,bug,target,**details):
        response=self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status=target,**details))
        self.assertEqual(response.status_code,200,response.json)
        return response.json['bug']

    def ready(self,bug):return self.move(self.move(bug,'In Progress'),'Ready for Retest')

    def test_prefill_is_reviewable_links_are_immutable_and_severity_is_separate(self):
        before=self.f.sql('SELECT * FROM test_executions WHERE id=?',(self.eid,))[0]
        draft=self.draft()
        self.assertEqual(draft['preconditions'],['Customer owns a ticket.'])
        self.assertEqual(draft['steps_to_reproduce'],['Request the owned ticket.'])
        self.assertEqual(draft['expected_result'],'Owned ticket is shown.')
        self.assertEqual(draft['actual_result'],self.failed['actual_result'])
        self.assertFalse(self.f.sql('SELECT * FROM bugs'))
        bug=self.create(title='Wrong customer ticket shown',severity='Critical',priority='Low',actual_result='Reviewed, precise observation.',evidence_reference='evidence://reference')
        self.assertEqual(bug['severity'],'Critical');self.assertEqual(bug['priority'],'Low')
        self.assertEqual(bug['project_id'],'current');self.assertEqual(bug['requirement_id'],self.r['id'])
        self.assertEqual(bug['scenario_id'],self.sid);self.assertEqual(bug['failed_execution_id'],self.eid)
        self.assertEqual(bug['reporter_id'],3);self.assertTrue(bug['created_at'].endswith('Z'));self.assertEqual(bug['status'],'Open')
        self.assertEqual(self.f.sql('SELECT * FROM test_executions WHERE id=?',(self.eid,))[0],before)
        self.assertEqual(self.engineer.get(f'/api/executions/{self.eid}/bugs').json['bugs'][0],bug)

    def test_duplicate_retries_do_not_create_another_bug_or_history_event(self):
        body=self.draft();path=f'/api/executions/{self.eid}/bugs'
        first=self.write('post',path,body,key='same-click-submission')
        retry=self.write('post',path,body,key='same-click-submission')
        self.assertEqual(first.status_code,201);self.assertEqual(retry.status_code,200)
        self.assertEqual(first.json['bug']['id'],retry.json['bug']['id'])
        other_key=self.write('post',path,body,self.admin,key='another-click-submission')
        self.assertEqual(other_key.status_code,200)
        self.assertEqual(other_key.json['bug']['reporter_id'],3)
        self.assertEqual(self.write('post',path,{**body,'title':'Different issue'},key='same-click-submission').status_code,409)
        self.assertEqual(len(self.f.sql('SELECT * FROM bugs')),1)
        self.assertEqual(len(self.f.sql('SELECT * FROM bug_history')),1)

    def test_complete_lifecycle_passing_retest_closure_failed_retest_reopening(self):
        bug=self.ready(self.create())
        passed=self.run_case('Pass')
        bug=self.move(bug,'Closed',retest_execution_id=passed['id'])
        self.assertEqual(bug['last_retest_execution_id'],passed['id'])
        closed_snapshot=self.engineer.get(f'/api/bugs/{bug["id"]}/history').json['history'][0]
        failed_retest=self.run_case('Fail',actual_result='A subsequent fixture retest failed.')
        bug=self.move(bug,'Open',retest_execution_id=failed_retest['id'],note='Reproduced again.')
        bug=self.ready(bug)
        next_pass=self.run_case('Pass')
        bug=self.move(bug,'Closed',retest_execution_id=next_pass['id'])
        reload=self.engineer.get(f'/api/bugs/{bug["id"]}').json['bug']
        self.assertEqual(reload,bug)
        events=self.engineer.get(f'/api/bugs/{bug["id"]}/history').json['history']
        self.assertIn(closed_snapshot,events)
        self.assertEqual([v['to_status'] for v in reversed(events)],['Open','In Progress','Ready for Retest','Closed','Open','In Progress','Ready for Retest','Closed'])
        self.assertEqual(self.f.sql('SELECT status FROM test_executions ORDER BY id'),[{'status':'Fail'},{'status':'Pass'},{'status':'Fail'},{'status':'Pass'}])

    def test_closure_requires_passing_evidence_or_documented_resolution(self):
        bug=self.ready(self.create())
        path=f'/api/bugs/{bug["id"]}/status'
        self.assertEqual(self.write('patch',path,dict(revision=bug['revision'],status='Closed')).status_code,400)
        blocked=self.run_case('Blocked')
        self.assertEqual(self.write('patch',path,dict(revision=bug['revision'],status='Closed',retest_execution_id=blocked['id'])).status_code,409)
        bug=self.move(bug,'Closed',resolution_reason='Stakeholder accepted the documented limitation for this release.')
        self.assertIsNone(bug['last_retest_execution_id'])
        self.assertIn('documented limitation',bug['resolution_reason'])
        self.assertEqual(self.write('patch',path,dict(revision=bug['revision'],status='Open')).status_code,409)

    def test_stale_or_unrelated_pass_cannot_close_and_passing_retest_cannot_reopen(self):
        bug=self.ready(self.create())
        passed=self.run_case('Pass');self.run_case('Fail')
        self.assertEqual(self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status='Closed',retest_execution_id=passed['id'])).status_code,409)
        later_pass=self.run_case('Pass')
        bug=self.move(bug,'Closed',retest_execution_id=later_pass['id'])
        self.assertEqual(self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status='Open',retest_execution_id=later_pass['id'])).status_code,409)
        other=self.f.requirement()
        self.assertEqual(self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status='Open',retest_execution_id=999999)).status_code,404)

    def test_roles_permissions_project_access_and_csrf(self):
        bug=self.create(self.admin,title='Admin reported bug')
        self.assertEqual(bug['reporter_id'],1)
        self.assertEqual(self.analyst.get(f'/api/bugs/{bug["id"]}').status_code,200)
        self.assertEqual(self.analyst.get(f'/api/bugs/{bug["id"]}/history').status_code,200)
        self.assertEqual(self.write('post',f'/api/executions/{self.eid}/bugs',self.draft(),self.analyst).status_code,403)
        self.assertEqual(self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status='In Progress'),self.analyst).status_code,403)
        self.assertEqual(self.engineer.post(f'/api/executions/{self.eid}/bugs',json=self.draft()).status_code,403)
        self.f.sql("UPDATE role_permissions SET enabled=0 WHERE role='SQA Engineer' AND permission='manage_bugs'")
        self.assertEqual(self.write('post',f'/api/executions/{self.eid}/bugs',self.draft()).status_code,403)
        self.f.sql('UPDATE users SET project_access=0 WHERE id=3')
        for path in (f'/api/bugs/{bug["id"]}',f'/api/bugs/{bug["id"]}/history',f'/api/executions/{self.eid}/bugs'):
            self.assertEqual(self.engineer.get(path).status_code,403)
        self.assertEqual(self.admin.get(f'/api/bugs/{bug["id"]}?project_id=other').status_code,403)
        self.assertEqual(self.f.client().get(f'/api/bugs/{bug["id"]}').status_code,401)

    def test_non_failure_cannot_create_bug_and_input_validation_is_safe(self):
        for status in ('Pass','Blocked','Not Run'):
            run=self.run_case(status)
            self.assertIsNone(self.engineer.get(f'/api/executions/{run["id"]}/bugs').json['prefill'])
            self.assertEqual(self.write('post',f'/api/executions/{run["id"]}/bugs',self.draft()).status_code,409)
        for changes in ({'title':''},{'steps_to_reproduce':[]},{'severity':[]},{'priority':'Critical'},{'reporter_id':1},{'failed_execution_id':999},{'status':'Closed'}):
            self.assertEqual(self.write('post',f'/api/executions/{self.eid}/bugs',{**self.draft(),**changes}).status_code,400)
        self.assertFalse(self.f.sql('SELECT * FROM bugs'))

    def test_safe_content_roundtrip_edit_history_and_stale_revision_rejection(self):
        content='<img src=x onerror=alert(1)> & <script>not executed</script>'
        bug=self.create(title=content,evidence_reference='javascript:never-followed-as-a-link')
        data={**self.draft(),'title':'Edited issue','severity':'High','priority':'Low','revision':bug['revision']}
        response=self.write('patch',f'/api/bugs/{bug["id"]}',data)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['bug']['severity'],'High');self.assertEqual(response.json['bug']['priority'],'Low')
        self.assertEqual(self.write('patch',f'/api/bugs/{bug["id"]}',data).status_code,409)
        history=self.engineer.get(f'/api/bugs/{bug["id"]}/history').json['history']
        self.assertEqual(history[-1]['snapshot']['title'],content)
        self.assertEqual(self.engineer.delete(f'/api/bugs/{bug["id"]}').status_code,405)
        self.assertEqual(self.engineer.patch(f'/api/bugs/{bug["id"]}/history').status_code,405)

    def test_unrelated_case_retest_rejected_and_history_survives_case_archive(self):
        bug=self.ready(self.create())
        result=self.write('post',f'/api/requirements/{self.r["id"]}/test-cases',dict(revision=self.r['revision'],title='Other case',category='Negative',preconditions=[],test_steps=['Observe other case'],expected_result='Other expected outcome',test_data='',test_type='Functional',priority='Low',criterion_codes=[]))
        self.assertEqual(result.status_code,201,result.json)
        other_id=result.json['test_case_id']
        response=self.write('post',f'/api/requirements/{self.r["id"]}/test-cases/{other_id}/executions',dict(case_revision=1,status='Pass',actual_result='Other case passed',environment='QA',build='fixture'))
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status='Closed',retest_execution_id=response.json['execution']['id'])).status_code,400)
        self.f.sql('UPDATE test_scenarios SET archived=1 WHERE id=?',(self.sid,))
        self.assertEqual(self.engineer.get(f'/api/executions/{self.eid}/bugs').json['bugs'][0],bug)
        self.assertEqual(self.draft()['steps_to_reproduce'],['Request the owned ticket.'])
        bug=self.move(bug,'Closed',resolution_reason='Superseded case; retained as historical evidence.')
        self.assertEqual(self.engineer.get(f'/api/bugs/{bug["id"]}/history').json['total'],4)


if __name__=='__main__':unittest.main()
