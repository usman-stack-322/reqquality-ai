"""Lightweight tests for the WBS 3.5.4 evaluation runner."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import app
from evaluation.run_fyp_evaluation import run_evaluation


class FypEvaluationTests(unittest.TestCase):
    def test_fixture_mode_cli_produces_valid_json_and_markdown_outputs(self):
        backend_dir = Path(__file__).resolve().parent
        script = backend_dir / 'evaluation' / 'run_fyp_evaluation.py'
        with tempfile.TemporaryDirectory() as tmpdir:
            json_out = Path(tmpdir) / 'eval_results.json'
            md_out = Path(tmpdir) / 'eval_report.md'
            env = os.environ.copy()
            env['DATABASE_URL'] = ''
            env['GEMINI_API_KEY'] = ''
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    '--mode', 'fixture',
                    '--json-output', str(json_out),
                    '--report-output', str(md_out),
                    '--export-samples', '2',
                ],
                cwd=backend_dir.parent,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json_out.is_file())
            self.assertTrue(md_out.is_file())

            data = json.loads(json_out.read_text(encoding='utf-8'))
            self.assertEqual(data['mode'], 'fixture')
            self.assertEqual(data['dataset_size'], 12)
            self.assertEqual(set(data['schema_validity']['by_category'].keys()), {
                'ambiguous', 'incomplete', 'conflicting', 'boundary_heavy', 'well_formed',
            })
            self.assertEqual(data['schema_validity']['pass_rate_percent'], 100.0)
            self.assertTrue(data['schema_validity']['negative_guard_probes']['all_rejected'])
            self.assertGreater(data['value_safety']['total_introduced_value_catches'], 0)
            self.assertEqual(data['value_safety']['false_positives_on_well_formed_and_boundary'], 0)
            self.assertTrue(data['value_safety']['all_completed_outputs_require_confirmation'])
            self.assertIsNotNone(data['ai_latency_ms']['mean_ms'])
            self.assertIsNotNone(data['ai_latency_ms']['p95_ms'])

            for fmt in ('requirement_pdf', 'project_pdf', 'requirements_csv'):
                self.assertIn(fmt, data['export_timings'])
                self.assertIsNotNone(data['export_timings'][fmt]['total_elapsed_ms']['mean_ms'])
                self.assertIsNotNone(data['export_timings'][fmt]['total_elapsed_ms']['p95_ms'])
                for stage in ('report_data', 'report_render', 'report_response'):
                    self.assertIsNotNone(data['export_timings'][fmt]['stages_ms'][stage]['mean_ms'])

            rbac = data['rbac_verification']
            self.assertTrue(rbac['all_passed'], rbac['checks'])
            checks = {item['check']: item for item in rbac['checks']}
            self.assertEqual(checks['analyst_cannot_self_approve_requirement_review']['actual_status'], 403)
            self.assertEqual(checks['analyst_cannot_self_approve_test_case']['actual_status'], 403)
            self.assertEqual(checks['analyst_cannot_accept_ai_review_revision_proposal']['actual_status'], 403)
            self.assertEqual(checks['role_promoted_author_still_blocked_from_self_approval']['actual_status'], 403)

            markdown = md_out.read_text(encoding='utf-8')
            self.assertIn('WBS 3.5.4 Controlled Evaluation Report', markdown)
            self.assertIn('Schema Validity Pass Rate', markdown)
            self.assertIn('value_safety.py', markdown)
            self.assertIn('Export Pipeline Stage Timings', markdown)
            self.assertIn('Automated RBAC Permission Enforcement Matrix', markdown)

    def test_live_mode_without_api_key_reports_missing_config_without_fallback(self):
        before_url, before_db = app.DATABASE_URL, app.DATABASE
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            json_out = Path(tmpdir) / 'live_results.json'
            md_out = Path(tmpdir) / 'live_report.md'
            data = run_evaluation(
                mode='live',
                json_output=json_out,
                report_output=md_out,
                export_samples=1,
            )
            self.assertEqual(data['mode'], 'live')
            self.assertEqual(data['schema_validity']['valid_cases'], 0)
            self.assertTrue(all(case['code'] == 'missing_api_key' for case in data['cases']))
            self.assertTrue(data['rbac_verification']['all_passed'])
            self.assertTrue(json_out.is_file())
            self.assertTrue(md_out.is_file())
        self.assertEqual(app.DATABASE_URL, before_url)
        self.assertEqual(app.DATABASE, before_db)


if __name__ == '__main__':
    unittest.main()
