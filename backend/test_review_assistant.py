"""Isolated SQLite APIs; Gemini responses are mocked. No production data is touched."""
import copy
import unittest
from unittest.mock import patch
import test_test_cases as case_tests


class ReviewAssistantTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: case_tests.DetailedCaseTests.setUpClass())
    write = case_tests.DetailedCaseTests.write
    base = case_tests.DetailedCaseTests.base
    create = case_tests.DetailedCaseTests.create
    # Reuse fixture helpers without inheriting the existing suite's tests.
    def path(self,cid='',tail=''):
        return f"/api/requirements/{self.r['id']}/ai-review"+(f'/{cid}' if cid else '')+tail

    def open(self,ids=None,client=None):
        response=self.write('post',self.path(),{'case_ids':ids if ids is not None else [self.c['id']]},client)
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def setUp(self):
        case_tests.DetailedCaseTests.setUp(self);self.c=self.create()

    def proposal(self,new=True):
        from analyzers.review_assistant import FIELDS
        content={k:copy.deepcopy(self.c[k]) for k in FIELDS}
        content['expected_result']='Only the owned ticket is returned with its identifier.'
        changes=[{'operation':'revise','case_id':self.c['id'],'summary':'Clarify observable expected result.','content':content}]
        if new:
            changes.append({'operation':'new','case_id':0,'summary':'Separate negative ownership scenario.','content':{**content,'category':'Negative','title':'Request another customer ticket','test_steps':['Request a ticket owned by another customer.'],'expected_result':'The other customer ticket is not visible.'}})
        return {'kind':'proposal','message':'Clarified the expected result and preserved the owned-ticket check.','changes':changes}

    def generate(self,session,proposal=None,key='request-123',feedback='Clarify the expected result.',client=None):
        with patch('analyzers.review_assistant.generate_review',return_value=proposal or self.proposal()) as mock:
            response=self.write('post',self.path(session['id'],'/messages'),{'feedback':feedback,'request_key':key},client)
        return response,mock

    def decision(self,s,t,action='accept',client=None):
        return self.write('post',self.path(s['id'],f"/proposals/{t['id']}"),{'action':action},client)

    def test_proposal_is_not_saved_until_atomic_accept_and_pending_review_requires_approval(self):
        s=self.open(); response,_=self.generate(s); self.assertEqual(response.status_code,200,response.json);t=response.json['turn']
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['expected_result'],self.c['expected_result'])
        accepted=self.decision(s,t);self.assertEqual(accepted.status_code,200,accepted.json);self.r=accepted.json['requirement']
        cases=self.engineer.get(self.base()).json['test_cases'];self.assertEqual(len(cases),2)
        revised=next(c for c in cases if c['id']==self.c['id'])
        self.assertEqual(revised['scenario_code'],self.c['scenario_code']);self.assertEqual(revised['review_status'],'Pending Review');self.assertEqual(revised['case_revision'],2)
        self.assertEqual(self.decision(s,t).status_code,200);self.assertEqual(len(self.engineer.get(self.base()).json['test_cases']),2)
        versions=self.engineer.get(self.base(self.c['id'],'/versions')).json['versions'];self.assertEqual(len(versions),2)
        self.assertEqual(versions[-1]['snapshot']['expected_result'],self.c['expected_result'])
        self.assertEqual(self.write('patch',self.base(self.c['id'],'/review'),dict(revision=self.r['revision'],case_revision=2,review_status='Approved')).status_code,409)
        for status in ('In Review','Approved'):
            current=self.engineer.get(self.base()).json['test_cases'][0]
            reviewed=self.write('patch',self.base(current['id'],'/review'),dict(revision=self.r['revision'],case_revision=current['case_revision'],review_status=status))
            self.assertEqual(reviewed.status_code,200,reviewed.json);self.r=reviewed.json['requirement']
        s=self.open();response,_=self.generate(s,key='second-revision');self.assertEqual(response.status_code,200)
        accepted=self.decision(s,response.json['turn']);self.assertEqual(accepted.status_code,200,accepted.json)
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['review_status'],'Pending Review')

    def test_reject_followup_and_server_owned_history(self):
        s=self.open();first,_=self.generate(s);t=first.json['turn']
        changed=self.proposal(False);changed['changes'][0]['content']['title']='More precise title'
        second,mock=self.generate(s,changed,key='followup-key',feedback='Also clarify the title.')
        self.assertEqual(second.status_code,200,second.json)
        context=mock.call_args.args[0];self.assertEqual(context['latest_proposal'],t['proposal']);self.assertEqual(context['requirement']['description'],self.source['description']);self.assertEqual(context['history'][0]['feedback'],t['feedback'])
        self.assertEqual(self.decision(s,t).status_code,409)
        self.assertEqual(self.decision(s,second.json['turn'],'reject').status_code,200)
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['case_revision'],1)
        self.assertEqual(self.open()['turns'][-1]['status'],'rejected')

    def test_stale_source_or_case_cannot_be_accepted(self):
        s=self.open();response,_=self.generate(s);t=response.json['turn']
        edited=self.write('patch',self.base(self.c['id']),{**self.c,'revision':self.r['revision'],'title':'Concurrent edit'})
        self.assertEqual(edited.status_code,200)
        self.assertEqual(self.decision(s,t).status_code,409)
        response,_=self.generate(s,key='fresh-request');self.assertEqual(response.status_code,200)
        self.f.sql('UPDATE requirements SET content_revision=content_revision+1 WHERE id=?',(self.r['id'],))
        self.assertEqual(self.decision(s,response.json['turn']).status_code,409)

    def test_permissions_context_csrf_and_analyst_discussion(self):
        s=self.open(client=self.analyst);response,_=self.generate(s,client=self.analyst);self.assertEqual(response.status_code,200)
        self.assertEqual(self.decision(s,response.json['turn'],client=self.analyst).status_code,403)
        self.assertEqual(self.decision(s,response.json['turn']).status_code,404)
        self.assertEqual(self.write('post',self.path(),{'case_ids':[999999]}).status_code,409)
        self.assertEqual(self.write('post',self.path(),{'case_ids':[],'project_id':'other'}).status_code,403)
        self.assertEqual(self.engineer.post(self.path(),json={'case_ids':[]}).status_code,403)
        self.f.sql("UPDATE role_permissions SET enabled=0 WHERE role='SQA Engineer' AND permission='review_requirements'")
        self.assertEqual(self.write('post',self.path(),{'case_ids':[]}).status_code,403)
        self.f.sql('UPDATE users SET project_access=0 WHERE id=2')
        self.assertEqual(self.write('post',self.path(),{'case_ids':[]},self.analyst).status_code,403)

    def test_failure_saved_feedback_invalid_outputs_and_idempotent_retry(self):
        s=self.open()
        with patch('analyzers.review_assistant.generate_review',side_effect=RuntimeError('SECRET must never escape')):
            response=self.write('post',self.path(s['id'],'/messages'),{'feedback':'Clarify result','request_key':'retry-key'})
        self.assertEqual(response.status_code,502);self.assertNotIn('SECRET',str(response.json))
        self.assertEqual(self.open()['turns'][0]['feedback'],'Clarify result')
        response,_=self.generate(s,key='retry-key',feedback='Clarify result');self.assertEqual(response.status_code,200,response.json)
        again,mock=self.generate(s,key='retry-key',feedback='Clarify result');self.assertEqual(again.json,response.json);mock.assert_not_called()
        invalid=self.proposal();invalid['changes'][0]['case_id']=999
        response,_=self.generate(s,invalid,key='invalid-target');self.assertEqual(response.status_code,502)
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['case_revision'],1)

    def test_clarification_and_coverage_discussion_do_not_mutate_cases(self):
        for kind,ids in [('clarification',[self.c['id']]),('discussion',[])]:
            s=self.open(ids);response,_=self.generate(s,{'kind':kind,'message':'What should happen for an empty password?','changes':[]},key=kind+'-key')
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(self.decision(s,response.json['turn']).status_code,409)
        self.assertEqual(self.engineer.get(self.base()).json['test_cases'][0]['case_revision'],1)

    def test_multi_case_scope_and_archiving_preserve_versions(self):
        second=self.create(title='Duplicate owned ticket check')
        s=self.open([self.c['id'],second['id']]);proposal=self.proposal(False)
        from analyzers.review_assistant import FIELDS
        proposal['changes'].append({'operation':'archive','case_id':second['id'],'summary':f"Duplicate; checks retained by TC-{self.c['id']}.",'content':{k:second[k] for k in FIELDS}})
        response,mock=self.generate(s,proposal)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(len(mock.call_args.args[0]['test_cases']),2)
        result=self.decision(s,response.json['turn']);self.assertEqual(result.status_code,200,result.json)
        cases=self.engineer.get(self.base()).json['test_cases'];self.assertEqual(len(cases),2)
        archived=next(c for c in cases if c['id']==second['id']);self.assertTrue(archived['archived'])
        self.assertEqual(self.engineer.get(self.base(second['id'],'/versions')).json['total'],2)
        coverage=self.open([]);self.assertEqual(len(coverage['context']['coverage_cases']),1)

    def test_active_generation_blocks_duplicates_and_acceptance_and_expires_for_retry(self):
        s=self.open();response,_=self.generate(s);t=response.json['turn']
        self.f.sql("INSERT INTO ai_review_turns(id,conversation_id,request_key,feedback,actor_id,created_at,started_at,status,base_snapshot) VALUES('busy',?,'busy-request','Feedback',3,'2099',?,'generating','{}')",(s['id'],int(__import__('time').time())))
        response,mock=self.generate(s,key='other-request');self.assertEqual(response.status_code,409);mock.assert_not_called()
        self.assertEqual(self.decision(s,t).status_code,409)
        self.f.sql("UPDATE ai_review_turns SET started_at=0 WHERE id='busy'")
        response,_=self.generate(s,key='busy-request',feedback='Feedback');self.assertEqual(response.status_code,200,response.json)

    def test_invalid_criteria_and_foreign_case_reject_entire_proposal_and_project_change_is_stale(self):
        s=self.open();invalid=self.proposal();invalid['changes'][1]['content']['criterion_codes']=['FOREIGN-AC']
        response,_=self.generate(s,invalid);self.assertEqual(response.status_code,502)
        self.assertEqual(len(self.engineer.get(self.base()).json['test_cases']),1)
        response,_=self.generate(s,key='valid-request')
        self.f.sql("UPDATE projects SET revision=revision+1,context='Changed context' WHERE id='current'")
        self.assertEqual(self.decision(s,response.json['turn']).status_code,409)


if __name__=='__main__': unittest.main()
