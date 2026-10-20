"""Real Flask/SQLite integrated evidence checks; observations are synthetic, no AI calls."""
import csv
import json
from io import BytesIO,StringIO
from pathlib import Path
import unittest
from pypdf import PdfReader
import app
import test_admin_dashboard as fixtures


class IntegratedReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.f=fixtures.ManagerTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.analyst=self.f.client(2);self.engineer=self.f.client(3);self.admin=self.f.admin
        self.r=self.write('post','/api/requirements',dict(title='Customer ticket',description='Customers can view tickets they own.',requirement_type='Functional',priority='High'),self.analyst).json['requirement']
        self.edit_source('Customers can view tickets they own.')
        self.sid=self.create_case()

    def write(self,method,path,data,client=None):
        return getattr(client or self.engineer,method)(path,json=data,headers=fixtures.HEADERS)

    def reload(self):
        self.r=self.engineer.get(f'/api/requirements/{self.r["id"]}').json['requirement']
        return self.r

    def edit_source(self,description):
        response=self.write('patch',f'/api/requirements/{self.r["id"]}',dict(revision=self.r['revision'],title=self.r['title'],description=description,requirement_type='Functional',priority='High',acceptance_criteria=['An owner sees the requested owned ticket.']),self.analyst)
        self.assertEqual(response.status_code,200,response.json);self.r=response.json['requirement']

    def create_case(self,linked=True):
        response=self.write('post',f'/api/requirements/{self.r["id"]}/test-cases',dict(revision=self.r['revision'],title='Open an owned ticket',category='Positive',preconditions=['Customer owns ticket A.'],test_steps=['Request owned ticket A.'],test_data='Synthetic ticket A',expected_result='Owned ticket A is shown.',test_type='Functional',priority='High',criterion_codes=[self.r['acceptance_criteria'][0]['criterion_code']] if linked else []))
        self.assertEqual(response.status_code,201,response.json);self.r=response.json['requirement']
        return response.json['test_case_id']

    def run_case(self,status,sid=None):
        sid=sid or self.sid
        case=next(v for v in self.engineer.get(f'/api/requirements/{self.r["id"]}/test-cases').json['test_cases'] if v['id']==sid)
        response=self.write('post',f'/api/requirements/{self.r["id"]}/test-cases/{sid}/executions',dict(case_revision=case['case_revision'],status=status,actual_result='Synthetic observed '+status if status in ('Pass','Fail') else '',blocked_reason='QA environment unavailable.' if status=='Blocked' else '',environment='QA synthetic',build='fixture-21',notes='Manual fixture observation',evidence_reference='private-reference-21'))
        self.assertEqual(response.status_code,201,response.json)
        return response.json['execution']

    def approve(self):
        submitted=self.write('post',f'/api/requirements/{self.r["id"]}/submit',dict(revision=self.r['revision']),self.analyst)
        self.assertEqual(submitted.status_code,200,submitted.json);self.r=submitted.json['requirement']
        for status in ('In Review','Approved'):
            response=self.write('patch',f'/api/requirements/{self.r["id"]}/review',dict(revision=self.r['revision'],review_status=status,reviewer_notes='Reviewed exact source version and recorded evidence.'))
            self.assertEqual(response.status_code,200,response.json);self.r=response.json['requirement']

    def create_bug(self,execution):
        path=f'/api/executions/{execution["id"]}/bugs'
        draft=self.engineer.get(path).json['prefill']
        response=self.write('post',path,{**draft,'title':'Ticket not shown','severity':'Critical','priority':'Low'})
        self.assertEqual(response.status_code,201,response.json)
        return response.json['bug']

    def graph(self):return self.engineer.get(f'/api/requirements/{self.r["id"]}/traceability').json

    def test_metrics_match_current_cases_latest_execution_and_all_open_bug_states(self):
        failed=self.run_case('Fail');bug=self.create_bug(failed)
        self.run_case('Pass')  # failure remains historical; latest case is Pass
        sid2=self.create_case();self.run_case('Fail',sid2)
        sid3=self.create_case();self.run_case('Blocked',sid3)
        self.create_case()  # Not Run
        self.approve()
        other=self.f.requirement(title='Unlinked legacy source',review_status='Approved')
        self.f.criteria(other);self.f.scenario(other)
        for target in ('In Progress','Ready for Retest'):
            response=self.write('patch',f'/api/bugs/{bug["id"]}/status',dict(revision=bug['revision'],status=target));self.assertEqual(response.status_code,200);bug=response.json['bug']
        d=self.engineer.get('/api/dashboard').json
        self.assertEqual(d['review_status_counts'],{'Pending':1,'In Review':0,'Approved':1,'Needs Revision':0})
        self.assertEqual(d['requirements_with_linked_cases'],1);self.assertEqual(d['requirements_without_linked_cases'],1)
        self.assertEqual(d['latest_execution_counts'],{'Pass':1,'Fail':1,'Blocked':1,'Not Run':1})
        self.assertEqual(d['open_bugs_by_severity'],{'Critical':1,'High':0,'Medium':0,'Low':0})
        self.assertEqual(d['items_needing_review_count'],2)  # approved source still has draft cases/missing analysis
        manager=self.admin.get('/api/admin/dashboard').json
        self.assertEqual(manager['integrated']['latest_execution_counts'],d['latest_execution_counts'])
        filtered=self.admin.get('/api/admin/dashboard',query_string={'q':'Unlinked legacy'}).json['integrated']
        self.assertEqual(filtered['requirements_without_linked_cases'],1)
        self.assertEqual(sum(filtered['latest_execution_counts'].values()),0)

    def test_material_edit_preserves_old_chain_and_invalidates_current_approval_analysis_criteria_cases(self):
        failed=self.run_case('Fail');self.create_bug(failed);self.run_case('Pass');self.approve()
        before=self.graph();old=self.r['content_revision']
        self.edit_source('Customers can view the subject and description of tickets they own.')
        after=self.graph()
        self.assertEqual(self.r['content_revision'],old+1)
        self.assertEqual(self.r['sqa_review_status'],'Pending');self.assertFalse(self.r['review_valid'])
        self.assertIsNone(self.r['reviewed_content_revision']);self.assertIsNone(self.r['reviewed_at'])
        self.assertTrue(self.r['analysis_summary']['stale']);self.assertTrue(self.r['analysis_outdated'])
        self.assertTrue(self.r['criteria_review_required']);self.assertTrue(self.r['acceptance_criteria'][0]['needs_review'])
        self.assertEqual(after['executions'],before['executions']);self.assertEqual(after['bugs'],before['bugs']);self.assertEqual(after['reviews'],before['reviews'])
        self.assertEqual([v for v in after['versions'] if v['content_revision']==old][0]['snapshot']['description'],'Customers can view tickets they own.')
        self.assertEqual(after['reviews'][-1]['content_revision'],old)
        self.assertIn(failed['id'],after['reviews'][-1]['snapshot']['execution_ids'])
        d=self.engineer.get('/api/dashboard').json
        self.assertEqual(d['requirements_with_linked_cases'],0);self.assertEqual(sum(d['latest_execution_counts'].values()),0)
        self.assertEqual(d['open_bugs_by_severity']['Critical'],1)
        stale=self.write('patch',f'/api/requirements/{self.r["id"]}/review',dict(revision=self.r['revision']-1,review_status='Approved'))
        self.assertEqual(stale.status_code,409)

    def test_reports_include_the_chain_versions_reviews_and_safe_csv_content(self):
        failed=self.run_case('Fail');bug=self.create_bug(failed);self.run_case('Blocked');self.approve()
        old=self.r['content_revision'];self.edit_source('Customers can view the subject of tickets they own.')
        self.f.sql('UPDATE requirements SET title=? WHERE id=?',('=unsafe_formula()',self.r['id']))
        for path in (f'/api/requirements/{self.r["id"]}/report.pdf','/api/reports/project.pdf'):
            response=self.engineer.get(path);self.assertEqual(response.status_code,200)
            reader=PdfReader(BytesIO(response.data),strict=True)
            text='\n'.join(p.extract_text() for p in reader.pages)
            for value in (f'BUG-{bug["id"]}',f'Manual execution #{failed["id"]}',f'Requirement version {old}','Version-bound SQA review history','fixture-21','private-reference-21','Critical','Low','Blocked','Reviewed exact source version'):
                self.assertIn(value,text)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        csv_response=self.engineer.get('/api/exports/requirements.csv')
        row=next(csv.DictReader(StringIO(csv_response.data.decode('utf-8-sig'))))
        self.assertEqual(row['title'],"'=unsafe_formula()")
        self.assertEqual(row['sqa_review_status'],'Pending')
        self.assertEqual(len(json.loads(row['executions'])),2);self.assertEqual(json.loads(row['reviews'])[-1]['content_revision'],old)
        self.assertEqual(json.loads(row['bugs'])[0]['failed_execution_id'],failed['id'])

    def test_project_role_permissions_and_unknown_version_legacy_approval(self):
        path=f'/api/requirements/{self.r["id"]}/traceability'
        for client in (self.admin,self.analyst,self.engineer):self.assertEqual(client.get(path).status_code,200)
        self.assertEqual(self.f.client().get(path).status_code,401)
        self.assertEqual(self.admin.get(path+'?project_id=other').status_code,403)
        self.f.sql('UPDATE users SET project_access=0 WHERE id=3')
        for uri in (path,'/api/dashboard','/api/exports/requirements.csv','/api/reports/project.pdf',f'/api/requirements/{self.r["id"]}/report.pdf'):
            self.assertEqual(self.engineer.get(uri).status_code,403)
        self.f.sql('UPDATE users SET project_access=1 WHERE id=3')
        self.f.sql("UPDATE role_permissions SET enabled=0 WHERE role='SQA Engineer' AND permission='review_requirements'")
        self.assertEqual(self.write('patch',f'/api/requirements/{self.r["id"]}/review',dict(revision=self.r['revision'],review_status='In Review')).status_code,403)
        for client in (self.admin,self.analyst):self.assertEqual(self.write('patch',f'/api/requirements/{self.r["id"]}/review',dict(revision=self.r['revision'],review_status='In Review'),client).status_code,403)
        self.f.sql("UPDATE requirements SET review_status='Approved',reviewed_content_revision=NULL WHERE id=?",(self.r['id'],))
        self.assertEqual(self.reload()['sqa_review_status'],'Pending')
        self.f.sql("UPDATE role_permissions SET enabled=1 WHERE role='SQA Engineer' AND permission='review_requirements'")
        reopened=self.write('patch',f'/api/requirements/{self.r["id"]}/review',dict(revision=self.r['revision'],review_status='In Review',reviewer_notes='Explicitly re-review unknown legacy version.'))
        self.assertEqual(reopened.status_code,200,reopened.json)
        self.assertEqual(reopened.json['requirement']['reviewed_content_revision'],self.r['content_revision'])
        self.assertEqual(len(self.engineer.get('/api/requirements?status=Pending').json['requirements']),0)


if __name__=='__main__':unittest.main()
