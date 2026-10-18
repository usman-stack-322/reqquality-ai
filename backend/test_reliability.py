"""Regression reproductions found during follow-up reliability work."""
import copy, json, unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import app
import test_admin_dashboard as fixtures
from test_ai_workflow import valid_analysis

class ReliabilityTests(unittest.TestCase):

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

    def post(self, path, data, client=None):
        return (client or self.analyst).post(path, json=data, headers=fixtures.HEADERS)

    def analyze(self, payload=None):
        with patch('analyzers.ai_analyzer.analyze_with_llm', side_effect=lambda _: dict(status='success', analysis=valid_analysis())):
            response = self.post('/api/analyze-requirement', payload or self.payload)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def create(self):
        response = self.post('/api/requirements', {**self.payload, 'analysis': self.analyze()})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['requirement']

    def test_browser_cannot_forge_ai_provenance_or_confirmed_facts(self):
        analysis = {**valid_analysis(), 'analysis_mode': 'ai_only', 'status': 'completed', 'risk_score': 99}
        response = self.post('/api/requirements', {**self.payload, 'analysis': analysis})
        self.assertEqual(response.status_code, 400, response.json)

    def test_analysis_cannot_be_relabelled_for_different_text(self):
        r = self.create()
        analysis = self.analyze({**self.payload, 'description': 'A warehouse operator can delete inventory.'})
        response = self.analyst.patch(f"/api/requirements/{r['id']}/analysis", json={'title': r['title'], 'description': r['description'], 'revision': r['revision'], 'analysis': analysis}, headers=fixtures.HEADERS)
        self.assertIn(response.status_code, (400, 409), response.json)

    def test_unchanged_ai_criteria_do_not_become_confirmed_during_text_edit(self):
        r = self.create()
        before = r['acceptance_criteria'][0]
        response = self.analyst.patch(f"/api/requirements/{r['id']}", json={**self.payload, 'description': self.payload['description'] + ' Access is read-only.', 'revision': r['revision'], 'acceptance_criteria': [before['description']]}, headers=fixtures.HEADERS)
        self.assertEqual(response.status_code, 200, response.json)
        after = response.json['requirement']['acceptance_criteria'][0]
        self.assertEqual(after['source'], before['source'])
        self.assertEqual(after['needs_confirmation'], before['needs_confirmation'])

    def test_unknown_analysis_fields_and_oversized_scenarios_are_rejected(self):
        from analyzers.llm_analyzer import _validate_analysis
        value = valid_analysis()
        value['test_scenarios'][0]['title'] = 'x' * 20001
        self.assertTrue(_validate_analysis(value) is None, 'Oversized scenario title must be rejected.')
        value = valid_analysis()
        value['test_scenarios'][0].update(source='confirmed', needs_confirmation=False)
        self.assertNotIn('source', _validate_analysis(value)['test_scenarios'][0])
        for field in ('preconditions', 'test_steps'):
            value = valid_analysis()
            value['test_scenarios'][0][field] = ['x'] * 101
            self.assertTrue(_validate_analysis(value) is None, field + ' must be bounded')

    def test_signed_results_are_user_input_and_content_bound(self):
        analysis = self.analyze()
        for changed in ({'priority': 'High'}, {'requirement_type': 'Business'}, {'description': 'Different'}):
            self.assertEqual(self.post('/api/requirements', {**self.payload, **changed, 'analysis': analysis}).status_code, 400)
        tampered = copy.deepcopy(analysis)
        tampered['labeled_analysis']['acceptance_criteria'][0]['needs_confirmation'] = False
        self.assertEqual(self.post('/api/requirements', {**self.payload, 'analysis': tampered}).status_code, 400)
        self.f.sql("INSERT INTO users(name,email,password_hash,role) VALUES('Other','other@example.com',?,'Analyst')", (self.f.password_hash,))
        self.assertEqual(self.post('/api/requirements', {**self.payload, 'analysis': analysis}, self.f.client(5)).status_code, 400)

    def test_saved_clarifications_reach_ai_and_are_bound_to_acceptance(self):
        r = self.create()
        answers = 'Locked accounts are rejected, confirmed by the stakeholder.'
        r = self.analyst.patch(f"/api/requirements/{r['id']}", json={**self.payload, 'revision': r['revision'], 'acceptance_criteria': [v['description'] for v in r['acceptance_criteria']], 'clarifications': answers}, headers=fixtures.HEADERS).json['requirement']
        with patch('analyzers.ai_analyzer.analyze_with_llm', side_effect=lambda _: dict(status='success', analysis=valid_analysis())) as provider:
            analysis = self.post('/api/analyze-requirement', {**self.payload, 'clarifications': answers}).json
            self.assertEqual(provider.call_args.args[0]['clarifications'], answers)
        result = self.analyst.patch(f"/api/requirements/{r['id']}/analysis", json={'revision': r['revision'], 'title': r['title'], 'description': r['description'], 'analysis': analysis}, headers=fixtures.HEADERS)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['requirement']['analysis_summary']['clarifications'], answers)

    def test_noop_save_preserves_review_history(self):
        r = self.create()
        result = self.analyst.patch(f"/api/requirements/{r['id']}", json={**self.payload, 'revision': r['revision'], 'acceptance_criteria': [v['description'] for v in r['acceptance_criteria']]}, headers=fixtures.HEADERS)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['requirement']['history'], r['history'])
        self.assertEqual(result.json['requirement']['revision'], r['revision'])

    def test_expired_worker_cannot_overwrite_newer_analysis(self):
        from flask import g
        from services.analysis_requests import run_analysis
        old = {'status': 'completed', 'marker': 'old'}
        new = {'status': 'completed', 'marker': 'new'}
        with app.app.test_request_context('/api/analyze-requirement'):
            g.current_user = {'id': 2}
            with patch('services.analysis_requests._now', side_effect=[100, 191, 192, 193]):

                def stale_worker():
                    self.assertEqual(run_analysis(self.payload, lambda: new), new)
                    return old
                self.assertEqual(run_analysis(self.payload, stale_worker), old)
            with patch('services.analysis_requests._now', return_value=194):
                self.assertEqual(run_analysis(self.payload, lambda: self.fail('Cached result should be reused')), new)

    def test_overlapping_analysis_does_not_start_second_provider_call(self):
        from flask import g
        from services.analysis_requests import run_analysis
        with app.app.test_request_context('/api/analyze-requirement'):
            g.current_user = {'id': 2}

            def generate():
                overlapping = run_analysis(self.payload, lambda: self.fail('Duplicate provider call'))
                self.assertEqual(overlapping['code'], 'analysis_in_progress')
                return {'status': 'completed'}
            self.assertEqual(run_analysis(self.payload, generate)['status'], 'completed')

    def test_concurrent_save_retry_creates_one_record(self):
        clients = [self.f.client(2), self.f.client(2)]
        barrier = Barrier(2)

        def save(client):
            barrier.wait(timeout=5)
            return client.post('/api/requirements', json=self.payload, headers={**fixtures.HEADERS, 'Idempotency-Key': 'concurrent-save-key'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, clients))
        self.assertEqual([r.status_code for r in results], [201, 201])
        self.assertEqual(results[0].json['requirement']['id'], results[1].json['requirement']['id'])
        self.assertEqual(len(self.f.sql('SELECT id FROM requirements')), 1)
        self.assertEqual(len(self.f.sql("SELECT id FROM requirement_history WHERE action='draft_created'")), 1)

    def test_concurrent_material_edits_reject_stale_writer(self):
        r = self.create()
        clients = [self.f.client(2), self.f.client(2)]
        barrier = Barrier(2)

        def edit(item):
            index, client = item
            barrier.wait(timeout=5)
            return client.patch(f"/api/requirements/{r['id']}", json={**self.payload, 'title': f'Edit {index}', 'revision': r['revision'], 'acceptance_criteria': ['Own tickets can be viewed.']}, headers=fixtures.HEADERS)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, enumerate(clients)))
        self.assertEqual(sorted((r.status_code for r in results)), [200, 409])
        latest = self.analyst.get(f"/api/requirements/{r['id']}").json['requirement']
        winner = next((r.json['requirement']['title'] for r in results if r.status_code == 200))
        self.assertEqual(latest['title'], winner)
        self.assertEqual(latest['revision'], r['revision'] + 1)
if __name__ == '__main__':
    unittest.main()
