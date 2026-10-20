"""AI contract, retry safety, project access and review state machine regressions."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import app
import test_admin_dashboard as fixtures
from analyzers.llm_analyzer import _validate_analysis, analyze_with_llm


def valid_analysis():
    return dict(ambiguity_issues=[], conflict_issues=[], missing_information=['What should happen if the account is locked?'],
                testability_issues=[], assumptions=[], edge_cases=[], clarification_questions=['What should happen if the account is locked?'],
                improved_requirement='Registered users can sign in with valid credentials.',
                acceptance_criteria=['Valid credentials open the account.'],
                risk_reasons=['Locked-account behavior is unspecified.'],
                priority_reasons=['Confirm stakeholder priority; authentication affects access.'],
                suggested_requirement_type='Functional',type_explanation='Describes system behavior.',
                risk_level='Medium',suggested_priority='Medium',test_scenarios=[dict(
                    category='Positive',title='Valid sign in',preconditions=['Registered account exists.'],
                    test_steps=['Enter valid credentials.'],expected_result='Account opens.',criterion_codes=['AC-001'])])


class AIContractTests(unittest.TestCase):
    def test_real_sdk_schema_normalization_preserves_generation_identity(self):
        from analyzers.llm_analyzer import generation_configuration
        from google.genai import _transformers
        import google.genai
        with patch.dict('os.environ',GEMINI_API_KEY='mock-key',GEMINI_MODEL='account-model'):
            before=generation_configuration()
            def sdk_normalization(**kwargs):
                _transformers.t_schema(SimpleNamespace(vertexai=False),kwargs['config'].response_schema)
                return SimpleNamespace(text=json.dumps(valid_analysis()))
            with patch.object(google.genai,'Client') as client:
                client.return_value.models.generate_content.side_effect=sdk_normalization
                self.assertEqual(analyze_with_llm({})['status'],'success')
                self.assertEqual(analyze_with_llm({})['status'],'success')
            self.assertEqual(generation_configuration(),before)

    def test_transport_read_failure_is_classified_without_fallback(self):
        from analyzers.llm_analyzer import _error_status
        ReadError = type('ReadError', (Exception,), {})
        self.assertEqual(_error_status(ReadError()),'network_error')

    def test_complete_schema_and_malformed_output(self):
        self.assertIsNotNone(_validate_analysis(valid_analysis()))
        for change in ({'risk_level':[]},{'suggested_priority':{}},{'test_scenarios':[]},
                       {'missing_information':'question'},{'risk_reasons':[]},{'type_explanation':''},{'clarification_questions':[]}):
            self.assertIsNone(_validate_analysis({**valid_analysis(),**change}))
        value=valid_analysis();value['test_scenarios'][0]['criterion_codes']=['AC-999']
        self.assertIsNone(_validate_analysis(value))

    def test_sdk_timeout_quota_and_invalid_json(self):
        import google.genai
        with patch.dict('os.environ', GEMINI_API_KEY='mock-key',GEMINI_MODEL='account-model'):
            for error, status in [(TimeoutError(), 'network_error'),(SimpleAPIError(429),'quota_exceeded'),(SimpleAPIError(503),'service_unavailable')]:
                with patch.object(google.genai,'Client') as client:
                    client.return_value.models.generate_content.side_effect=error
                    self.assertEqual(analyze_with_llm({})['status'],status)
            with patch.object(google.genai,'Client') as client:
                client.return_value.models.generate_content.return_value.text='{"incomplete":true}'
                self.assertEqual(analyze_with_llm({})['status'],'malformed_json')
                client.return_value.models.generate_content.return_value.text='not json'
                self.assertEqual(analyze_with_llm({})['status'],'malformed_json')
                client.return_value.models.generate_content.return_value.text=json.dumps(valid_analysis())
                self.assertEqual(analyze_with_llm({})['status'],'success')


class SimpleAPIError(Exception):
    def __init__(self,code): self.code=code


class AIWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ManagerTests.setUpClass()
    def setUp(self):
        self.f=fixtures.ManagerTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.analyst=self.f.client(2);self.engineer=self.f.client(3);self.admin=self.f.admin
        self.payload=dict(title='Sign in',description='Registered users can sign in with valid credentials.',requirement_type='Functional',priority='Medium')
    def request(self, client, method, path, data):
        response=getattr(client,method)(path,json=data,headers=fixtures.HEADERS)
        return response
    def create(self):
        with patch('analyzers.ai_analyzer.analyze_with_llm',return_value={'status':'success','analysis':valid_analysis()}):
            analysis=self.request(self.analyst,'post','/api/analyze-requirement',self.payload)
        self.assertEqual(analysis.status_code,200,analysis.json)
        saved=self.request(self.analyst,'post','/api/requirements',{**self.payload,'analysis':analysis.json})
        self.assertEqual(saved.status_code,201,saved.json)
        return saved.json['requirement']
    def transition(self,r,client,path,data):
        response=self.request(client,'post' if path=='submit' else 'patch',f"/api/requirements/{r['id']}/{path}",{'revision':r['revision'],**data})
        self.assertEqual(response.status_code,200,response.json)
        return response.json['requirement']
    def test_failure_is_retryable_and_never_creates_requirement(self):
        for status in ('network_error','quota_exceeded','malformed_json'):
            with patch('analyzers.ai_analyzer.analyze_with_llm',return_value={'status':status,'analysis':None}):
                response=self.request(self.analyst,'post','/api/analyze-requirement',self.payload)
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json['code'],status)
            self.assertTrue(response.json['retryable'])
            self.assertNotIn('improved_requirement',response.json)
        self.assertFalse(self.f.sql('SELECT * FROM requirements'))
        r=self.create();self.assertEqual(r['title'],self.payload['title'])
    def test_incomplete_analysis_cannot_be_saved_as_success(self):
        response=self.request(self.analyst,'post','/api/requirements',{**self.payload,'analysis':{'status':'completed','analysis_mode':'ai_only'}})
        self.assertEqual(response.status_code,400)
        response=self.request(self.analyst,'post','/api/requirements',self.payload)
        self.assertEqual(response.status_code,201)
        self.assertIsNone(response.json['requirement']['risk_level'])
    def test_save_retry_is_idempotent_and_payload_bound(self):
        headers={**fixtures.HEADERS,'Idempotency-Key':'same-save-request'}
        first=self.analyst.post('/api/requirements',json=self.payload,headers=headers)
        second=self.analyst.post('/api/requirements',json=self.payload,headers=headers)
        self.assertEqual(first.status_code,201,first.json)
        self.assertEqual(second.status_code,201,second.json)
        self.assertEqual(first.json['requirement']['id'],second.json['requirement']['id'])
        self.assertEqual(len(self.f.sql('SELECT id FROM requirements')),1)
        self.assertEqual(self.analyst.post('/api/requirements',json={**self.payload,'title':'Different'},headers=headers).status_code,409)
        self.assertEqual(self.analyst.post('/api/requirements',json=self.payload,headers={**fixtures.HEADERS,'Idempotency-Key':'!'}).status_code,400)
    def test_workflow_validation_rejects_unhashable_enums_and_empty_updates(self):
        r=self.create()
        for changes in ({'requirement_type':[]},{'priority':{}}):
            response=self.request(self.analyst,'patch',f"/api/requirements/{r['id']}",{**self.payload,'revision':r['revision'],'acceptance_criteria':['Valid credentials open account.'],**changes})
            self.assertEqual(response.status_code,400,response.json)
        r=self.transition(r,self.analyst,'submit',{})
        for changes in ({'review_status':[]},{'review_status':{}},{}):
            response=self.request(self.engineer,'patch',f"/api/requirements/{r['id']}/review",{'revision':r['revision'],**changes})
            self.assertEqual(response.status_code,400,response.json)
    def test_submission_key_never_returns_another_users_record(self):
        self.f.sql("INSERT INTO users(name,email,password_hash,role) VALUES('Other','other@example.com',?,'Analyst')",(self.f.password_hash,))
        headers={**fixtures.HEADERS,'Idempotency-Key':'same-key-two-users'}
        first=self.analyst.post('/api/requirements',json=self.payload,headers=headers)
        second=self.f.client(5).post('/api/requirements',json=self.payload,headers=headers)
        self.assertEqual(first.status_code,201,first.json);self.assertEqual(second.status_code,201,second.json)
        self.assertNotEqual(first.json['requirement']['id'],second.json['requirement']['id'])
        self.assertEqual(second.json['requirement']['created_by_user_id'],5)
    def test_duplicate_calls_share_only_same_user_receipt(self):
        with patch('analyzers.ai_analyzer.analyze_with_llm',side_effect=lambda _: {'status':'success','analysis':valid_analysis()}) as generate:
            for _ in range(2):
                self.assertEqual(self.request(self.analyst,'post','/api/analyze-requirement',self.payload).status_code,200)
            self.assertEqual(generate.call_count,1)
            self.f.sql("INSERT INTO users(name,email,password_hash,role) VALUES('Other','other@example.com',?,'Analyst')",(self.f.password_hash,))
            other=self.f.client(5)
            self.assertEqual(self.request(other,'post','/api/analyze-requirement',self.payload).status_code,200)
            self.assertEqual(generate.call_count,2)
    def test_complete_revision_review_and_rereview(self):
        r=self.create();self.assertEqual(r['review_status'],'Draft')
        self.assertEqual(r['coverage_gaps'],[])
        self.assertEqual(self.request(self.engineer,'patch',f"/api/requirements/{r['id']}/review",{'revision':1,'review_status':'Approved'}).status_code,409)
        r=self.transition(r,self.analyst,'submit',{})
        r=self.transition(r,self.engineer,'review',{'review_status':'In Review'})
        r=self.transition(r,self.engineer,'review',{'review_status':'Needs Revision','reviewer_notes':'Clarify locked accounts.'})
        edited=self.request(self.analyst,'patch',f"/api/requirements/{r['id']}",dict(self.payload,revision=r['revision'],description='Registered users sign in. Locked accounts cannot sign in.',acceptance_criteria=['Valid credentials open unlocked accounts.'],clarifications='Locked accounts are rejected, stakeholder decision.'))
        self.assertEqual(edited.status_code,200,edited.json);r=edited.json['requirement']
        # A replacement criterion gets a new code; old scenario links are invalidated.
        self.assertEqual(r['coverage_gaps'],['AC-002'])
        r=self.transition(r,self.analyst,'submit',{})
        r=self.transition(r,self.engineer,'review',{'review_status':'In Review'})
        scenario=r['test_scenarios'][0]
        revised=self.request(self.engineer,'patch',f"/api/requirements/{r['id']}/scenarios/{scenario['id']}",{**scenario,'revision':r['revision'],'criterion_codes':['AC-002']})
        self.assertEqual(revised.status_code,200,revised.json);r=revised.json['requirement']
        self.assertEqual(r['coverage_gaps'],[])
        r=self.transition(r,self.engineer,'review',{'review_status':'Approved'})
        old_revision=r['revision']
        edited=self.request(self.analyst,'patch',f"/api/requirements/{r['id']}",{**self.payload,'revision':old_revision,'acceptance_criteria':['Valid sign in opens account.']})
        self.assertEqual(edited.status_code,200,edited.json);r=edited.json['requirement']
        self.assertEqual(r['review_status'],'Draft');self.assertTrue(r['analysis_summary']['stale'])
        self.assertTrue(any(e['action']=='review_approved' for e in r['history']))
        self.assertEqual(self.request(self.analyst,'patch',f"/api/requirements/{r['id']}",{**self.payload,'revision':old_revision,'acceptance_criteria':[]}).status_code,409)
        self.assertTrue(self.f.sql('SELECT snapshot FROM requirement_history WHERE action=?',('before_material_edit',)))
    def test_project_scope_all_reads_writes_and_exports(self):
        r=self.create();rid=r['id']
        self.assertEqual(self.request(self.analyst,'post','/api/requirements',{**self.payload,'project_id':'another-project'}).status_code,403)
        response=self.request(self.admin,'patch','/api/admin/users/2/project-access',{'enabled':False});self.assertEqual(response.status_code,200)
        for path in ('/api/requirements',f'/api/requirements/{rid}',f'/api/requirements/{rid}/report.pdf','/api/dashboard','/api/reports/project.pdf','/api/exports/requirements.csv'):
            self.assertEqual(self.analyst.get(path).status_code,403,path)
        self.assertEqual(self.request(self.analyst,'post','/api/analyze-requirement',self.payload).status_code,403)
        self.assertEqual(self.request(self.analyst,'patch',f'/api/requirements/{rid}',{**self.payload,'revision':1,'acceptance_criteria':[]}).status_code,403)
        self.assertEqual(self.analyst.get('/api/auth/me').status_code,200)
        self.assertEqual(self.request(self.engineer,'patch','/api/admin/users/2/project-access',{'enabled':True}).status_code,403)
        self.assertEqual(self.request(self.admin,'patch','/api/admin/users/2/project-access',{'enabled':True}).status_code,200)
        self.assertEqual(self.analyst.get(f'/api/requirements/{rid}').status_code,200)
    def test_analysis_acceptance_is_explicit_versioned_and_text_bound(self):
        r=self.create()
        with patch('analyzers.ai_analyzer.analyze_with_llm',return_value={'status':'success','analysis':valid_analysis()}):
            result=self.request(self.analyst,'post','/api/analyze-requirement',{**self.payload,'requirement_id':r['id'],'requirement_revision':r['revision']}).json
        path=f"/api/requirements/{r['id']}/analysis"
        data={'revision':r['revision'],'analysis':result,'title':r['title'],'description':r['description']}
        self.assertEqual(self.request(self.analyst,'patch',path,{**data,'description':'Other text'}).status_code,409)
        accepted=self.request(self.analyst,'patch',path,data)
        self.assertEqual(accepted.status_code,200,accepted.json)
        self.assertEqual(accepted.json['requirement']['risk_level'],'Medium')
        self.assertEqual(accepted.json['requirement']['coverage_gaps'],[])
        self.assertTrue(accepted.json['requirement']['test_scenarios'][0]['needs_confirmation'])
        self.assertEqual(self.request(self.engineer,'patch',path,data).status_code,403)
        history=accepted.json['requirement']['history'][0]
        historical=self.analyst.get(f"/api/requirements/{r['id']}/history/{history['id']}")
        self.assertEqual(historical.status_code,200)
        self.assertEqual(historical.json['snapshot']['id'],r['id'])
    def test_author_cannot_review_even_after_role_change(self):
        r=self.create();r=self.transition(r,self.analyst,'submit',{})
        self.f.sql("UPDATE users SET role='SQA Engineer' WHERE id=2")
        self.assertEqual(self.request(self.analyst,'patch',f"/api/requirements/{r['id']}/review",{'revision':r['revision'],'review_status':'In Review'}).status_code,403)
    def test_pagination_and_filters_and_historical_data(self):
        for i in range(55): self.f.requirement(title=f'Historical {i}',risk_level='High',review_status='Pending')
        data=self.analyst.get('/api/requirements?view=summary&risk=High&page=2').json
        self.assertEqual(data['total'],55);self.assertEqual(len(data['requirements']),5)
        self.assertEqual(self.analyst.get('/api/requirements?status=unknown').status_code,400)
        rid=data['requirements'][0]['id']
        self.assertEqual(self.analyst.get(f'/api/requirements/{rid}').json['requirement']['review_status'],'Pending')
        self.assertEqual(self.analyst.get(f'/api/requirements/{rid}/report.pdf').status_code,200)

if __name__=='__main__': unittest.main()
