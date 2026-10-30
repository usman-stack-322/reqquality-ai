"""Export regressions using disposable SQLite and no provider calls."""
import csv
import json
from io import BytesIO, StringIO
from unittest.mock import patch
from pypdf import PdfReader
import app
from database import DatabaseConnection
from services.reports_service import _report_requirements
from test_integrated_reporting import IntegratedReportingTests


class FocusedReportTests(IntegratedReportingTests):
    def test_project_pdf_missing_numeric_scores_are_not_reported_as_zero(self):
        self.f.sql('UPDATE requirements SET risk_score=NULL')
        response=self.engineer.get('/api/reports/project.pdf')
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(response.data)).pages)
        self.assertIn('Not assessed (no numeric scores recorded)',text)
        self.f.sql('UPDATE requirements SET risk_score=0')
        response=self.engineer.get('/api/reports/project.pdf')
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(response.data)).pages)
        self.assertIn('0.0/100',text)
        self.assertNotIn('no numeric scores recorded',text)

    def test_export_timings_separate_data_render_and_response_for_every_format(self):
        for path in (f'/api/requirements/{self.r["id"]}/report.pdf','/api/reports/project.pdf','/api/exports/requirements.csv'):
            response=self.engineer.get(path)
            self.assertEqual(response.status_code,200)
            for stage in ('report_data','report_render','report_response'):
                self.assertIn(stage+';dur=',response.headers['Server-Timing'])

    def test_unanalyzed_draft_metadata_is_not_historical_analysis(self):
        response = self.engineer.get(f'/api/requirements/{self.r["id"]}/report.pdf')
        text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(response.data)).pages)
        self.assertIn('Pending: AI analysis has not been saved.', text)
        self.assertNotIn('Historical analysis', text)
        self.assertNotIn('Analysis describes an earlier revision', text)
        self.assertTrue(all(len(page.images) >= 1 for page in PdfReader(BytesIO(response.data)).pages))
        self.assertLess(len(response.data), 100_000, 'Small reports should not embed the oversized full-resolution brand image.')

    def test_workflow_dashboard_matches_legacy_metrics_without_duplicate_lists(self):
        failed = self.run_case('Fail')
        self.create_bug(failed)
        legacy = self.engineer.get('/api/dashboard').json
        lean = self.engineer.get('/api/dashboard?view=workflow').json
        for key, value in lean.items():
            self.assertEqual(value, legacy[key])
        self.assertNotIn('recent_requirements', lean)
        self.assertNotIn('high_attention_requirements', lean)
        self.assertNotIn('requirement_states', lean)
        self.assertEqual(self.f.client().get('/api/dashboard?view=workflow').status_code, 401)
        self.f.sql('UPDATE users SET project_access=0 WHERE id=3')
        self.assertEqual(self.engineer.get('/api/dashboard?view=workflow').status_code, 403)

    def test_batched_export_matches_detail_and_graph_without_loading_user_proposals(self):
        expected = self.reload()
        expected_graph = self.graph()
        connection = app.get_connection()
        try:
            rows = _report_requirements(connection)
        finally:
            connection.close()
        self.assertEqual(rows[0]['integrated'], expected_graph)
        for key in ('description', 'analysis_summary', 'test_scenarios', 'analysis_outdated'):
            self.assertEqual(rows[0][key], expected[key])
        self.assertIsNone(rows[0]['analysis_draft'])

    def test_export_query_count_does_not_grow_per_requirement_and_never_calls_ai(self):
        def count():
            statements = []
            execute = DatabaseConnection.execute
            def counted(connection, sql, *a, **kw):
                statements.append(sql)
                return execute(connection, sql, *a, **kw)
            with patch.object(DatabaseConnection, 'execute', counted), patch('analyzers.ai_analyzer.analyze_with_llm', side_effect=AssertionError('Exports must not call AI')):
                response = self.engineer.get('/api/exports/requirements.csv')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return len(statements), response
        initial, _ = count()
        for index in range(10):
            self.f.requirement(title=f'Synthetic extra {index}')
        expanded, response = count()
        self.assertEqual(initial, expanded)
        rows = list(csv.DictReader(StringIO(response.data.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 11)
        self.assertNotIn('request_key', json.dumps(rows))
        self.assertNotIn('input_hash', json.dumps(rows))

    def test_long_review_notes_and_special_characters_fit_pdf_and_csv(self):
        note = 'Synthetic review <tag> & punctuation, "quoted"\n' * 250 + 'END-OF-LONG-NOTES'
        self.f.sql('UPDATE requirements SET reviewer_notes=? WHERE id=?', (note, self.r['id']))
        self.f.sql('UPDATE requirements SET title=? WHERE id=?', ('=SUM(1,2), "quoted"', self.r['id']))
        response = self.engineer.get(f'/api/requirements/{self.r["id"]}/report.pdf')
        self.assertEqual(response.status_code, 200)
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.data)).pages)
        self.assertIn('END-OF-LONG-NOTES', text)
        response = self.engineer.get('/api/exports/requirements.csv')
        row = next(csv.DictReader(StringIO(response.data.decode('utf-8-sig'))))
        self.assertEqual(row['reviewer_notes'], note)
        self.assertEqual(row['title'], '\'=SUM(1,2), "quoted"')
