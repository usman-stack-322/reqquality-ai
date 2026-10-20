"""MOCKED Gemini integration tests. These do not establish model output quality."""
import copy
import json
import unittest
from unittest.mock import patch
import app
import test_admin_dashboard as fixtures
from test_ai_workflow import valid_analysis


class VersionedAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.f = fixtures.ManagerTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.analyst = self.f.client(2)
        self.engineer = self.f.client(3)
        self.payload = dict(title='Own tickets', description='An authenticated customer can view their own support tickets.', requirement_type='Functional', priority='Medium')
        provider_patch = patch('analyzers.ai_analyzer.analyze_with_llm', side_effect=lambda _: dict(status='success', analysis=valid_analysis()))
        self.provider = provider_patch.start()
        self.addCleanup(provider_patch.stop)

    def write(self, method, path, data, client=None):
        return getattr(client or self.analyst, method)(path, json=data, headers=fixtures.HEADERS)

    def create(self):
        result = self.write('post', '/api/requirements', self.payload)
        self.assertEqual(result.status_code, 201, result.json)
        return result.json['requirement']

    def analyze(self, r, **changes):
        return self.write('post', '/api/analyze-requirement', {**self.payload, 'requirement_id':r['id'], 'requirement_revision':r['revision'], **changes})

    def accept(self, r, analysis, edits=None):
        return self.write('patch', f"/api/requirements/{r['id']}/analysis", dict(title=r['title'],description=r['description'],revision=r['revision'],analysis=analysis,analysis_edits=edits))

    def test_context_is_server_owned_and_revision_bound(self):
        project = self.f.admin.get('/api/project').json['project']
        update = self.write('patch', '/api/project', {'context':'Customers may view their own support tickets only.', 'revision':project['revision']}, self.f.admin)
        self.assertEqual(update.status_code, 200)
        self.assertEqual(self.write('patch','/api/project',{'context':'forged','revision':2}).status_code,403)
        r = self.create()
        result = self.analyze(r, project_context='Invented business rules')
        self.assertEqual(result.status_code, 200, result.json)
        sent = self.provider.call_args.args[0]
        self.assertEqual(sent['project_context'], update.json['project']['context'])
        self.assertEqual(sent['requirement_revision'], r['revision'])
        self.assertEqual(result.json['risk_score'], None)
        self.assertEqual(self.f.admin.get('/api/project?project_id=other').status_code,403)

    def test_success_persists_proposal_without_modifying_original_or_auto_approval(self):
        r = self.create()
        response = self.analyze(r)
        self.assertEqual(response.status_code,200,response.json)
        with patch('analyzers.ai_analyzer.analyze_with_llm', side_effect=AssertionError('Viewing must not generate')):
            for _ in range(2):
                saved = self.analyst.get(f"/api/requirements/{r['id']}").json['requirement']
                self.assertEqual(saved['analysis_draft'], response.json)
                self.assertEqual(saved['description'],r['description'])
                self.assertEqual(saved['revision'],r['revision'])
                self.assertEqual(saved['analysis_summary'],{})
                self.assertEqual(saved['review_status'],'Draft')
        accepted = self.accept(r, response.json, {'improved_requirement':'Human edited proposal, pending stakeholder review.'})
        self.assertEqual(accepted.status_code,200,accepted.json)
        saved = accepted.json['requirement']
        self.assertEqual(saved['description'],r['description'])
        self.assertEqual(saved['analysis_summary']['improved_requirement'],'Human edited proposal, pending stakeholder review.')
        self.assertEqual(saved['analysis_summary']['labeled_analysis']['improved_requirement']['source'],'original')
        self.assertEqual(saved['review_status'],'Draft')
        self.assertEqual(json.loads(self.f.sql('SELECT result FROM requirement_analysis_drafts')[0]['result'])['improved_requirement'], response.json['improved_requirement'])

    def test_cache_changes_with_version_context_and_generation_configuration(self):
        r = self.create()
        first = self.analyze(r)
        self.assertEqual(self.analyze(r).json, first.json)
        self.assertEqual(self.provider.call_count,1)
        project = self.f.admin.get('/api/project').json['project']
        self.assertEqual(self.write('patch','/api/project',{'revision':project['revision'],'context':'Only supplied account facts apply.'},self.f.admin).status_code,200)
        self.assertEqual(self.accept(r,first.json).status_code,409)
        self.assertIsNone(self.analyst.get(f"/api/requirements/{r['id']}").json['requirement']['analysis_draft'])
        second = self.analyze(r)
        self.assertEqual(self.provider.call_count,2)
        with patch.dict('os.environ', GEMINI_MODEL='a-different-model'):
            self.assertEqual(self.accept(r,second.json).status_code,409)
            self.assertEqual(self.analyze(r).status_code,200)
        self.assertEqual(self.provider.call_count,3)
        changed = self.write('patch',f"/api/requirements/{r['id']}",{**self.payload,'description':'An authenticated customer can view their own open tickets.', 'revision':r['revision'],'acceptance_criteria':[]})
        self.assertEqual(changed.status_code,200,changed.json)
        self.assertEqual(self.analyze(r).status_code,409)
        self.assertEqual(self.accept(changed.json['requirement'],second.json).status_code,409)

    def test_revocation_other_user_and_unknown_project_cannot_reuse_draft(self):
        r = self.create()
        response = self.analyze(r)
        self.assertIsNone(self.engineer.get(f"/api/requirements/{r['id']}").json['requirement']['analysis_draft'])
        self.assertEqual(self.analyze(r,project_id='other').status_code,403)
        self.f.sql('UPDATE users SET project_access=0 WHERE id=2')
        self.assertEqual(self.analyze(r).status_code,403)
        self.assertEqual(self.analyst.get(f"/api/requirements/{r['id']}").status_code,403)
        self.assertEqual(self.accept(r,response.json).status_code,403)
        self.assertEqual(self.analyst.get('/api/project').status_code,403)

    def test_failure_is_not_persisted_and_explicit_retry_succeeds(self):
        r = self.create()
        for category in ('quota_exceeded','network_error','malformed_json','model_unavailable'):
            self.provider.side_effect = lambda _, category=category: dict(status=category,analysis=None)
            failed = self.analyze(r)
            self.assertEqual(failed.status_code,503)
            self.assertEqual(failed.json['status'],'failed')
            self.assertTrue(failed.json['retryable'])
            self.assertFalse(self.f.sql('SELECT * FROM requirement_analysis_drafts'))
        self.provider.side_effect = lambda _: dict(status='success',analysis=valid_analysis())
        self.assertEqual(self.analyze(r).status_code,200)
        self.assertEqual(len(self.f.sql('SELECT * FROM requirement_analysis_drafts')),1)

    def test_inflight_context_change_discards_stale_success(self):
        r = self.create()
        def change_context(_):
            self.f.sql("UPDATE projects SET context='Changed while running',revision=revision+1")
            return dict(status='success',analysis=valid_analysis())
        self.provider.side_effect = change_context
        result = self.analyze(r)
        self.assertEqual(result.status_code,409,result.json)
        self.assertFalse(self.f.sql('SELECT * FROM requirement_analysis_drafts'))

    def test_unsaved_receipt_cannot_be_attached_to_saved_requirement(self):
        analysis = self.write('post','/api/analyze-requirement',self.payload).json
        r = self.create()
        self.assertEqual(self.accept(r,analysis).status_code,409)

    def test_tampering_and_invalid_draft_edits_are_rejected(self):
        r = self.create()
        result = self.analyze(r).json
        tampered = copy.deepcopy(result)
        tampered['risk_score'] = 100
        self.assertEqual(self.accept(r,tampered).status_code,409)
        self.assertEqual(self.accept(r,result,{'source':'confirmed'}).status_code,400)
        self.assertEqual(self.accept(r,result,{'test_scenarios':[]}).status_code,400)

    def test_saved_proposal_reuse_survives_short_lived_receipt_cache_expiry(self):
        r = self.create()
        first = self.analyze(r)
        self.f.sql('DELETE FROM analysis_requests')
        self.assertEqual(self.analyze(r).json,first.json)
        self.assertEqual(self.provider.call_count,1)

    def test_legacy_non_object_analysis_summary_does_not_break_analysis(self):
        r = self.create()
        self.f.sql("UPDATE requirements SET analysis_summary='[]' WHERE id=?",(r['id'],))
        self.assertEqual(self.analyze(r).status_code,200)


if __name__ == '__main__':
    unittest.main()
