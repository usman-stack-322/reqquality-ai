"""SQLite upgrade rehearsal on a synthetic legacy DB; no real user data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
from database import connect_database
from services.database_service import _initialize_database


class ProjectMigrationTests(unittest.TestCase):
    def test_legacy_ids_content_analysis_and_artifacts_survive_idempotent_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.db'
            c = connect_database(None, path)
            _initialize_database(c)  # original five-table schema; no project/workflow tables
            summary = json.dumps({'improved_requirement':'Historical suggestion','risk_score':45})
            with c:
                c.execute("INSERT INTO users(id,name,email,password_hash,role) VALUES(7,'Legacy','legacy@example.invalid','unused fixture hash','Analyst')")
                c.execute("INSERT INTO requirements(id,title,description,requirement_type,priority,created_by_user_id,analysis_summary,risk_score) VALUES(11,'Original title','Original text','Functional','Low',7,?,45)",(summary,))
                c.execute("INSERT INTO requirement_acceptance_criteria(id,requirement_id,criterion_code,description) VALUES(13,11,'AC-1','Legacy criterion')")
                c.execute("INSERT INTO test_scenarios(id,requirement_id,scenario_code,category,title,preconditions,test_steps,expected_result) VALUES(17,11,'SC-1','Positive','Legacy test','[]','[]','Legacy outcome')")
            c.close()
            with patch.multiple(app,DATABASE_URL=None,DATABASE=path):
                for _ in range(2):
                    c = app.get_connection()
                    try:
                        row = c.execute('SELECT * FROM requirements WHERE id=11').fetchone()
                        self.assertEqual(row['description'],'Original text')
                        self.assertEqual(row['analysis_summary'],summary)
                        self.assertEqual(row['risk_score'],45)
                        self.assertEqual(row['created_by_user_id'],7)
                        self.assertEqual(row['project_id'],'current')
                        self.assertEqual(c.execute('SELECT id FROM test_scenarios').fetchone()[0],17)
                        self.assertEqual(c.execute('SELECT id FROM requirement_acceptance_criteria').fetchone()[0],13)
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM requirement_analysis_drafts').fetchone()[0],0)
                        case=c.execute('SELECT * FROM test_scenarios WHERE id=17').fetchone()
                        self.assertEqual(case['scenario_code'],'SC-1')
                        self.assertEqual(case['test_steps'],'[]')
                        self.assertEqual(case['review_status'],'Draft')
                        self.assertEqual(case['requirement_revision'],row['content_revision'])
                        version=c.execute('SELECT * FROM test_case_versions WHERE scenario_id=17').fetchone()
                        self.assertEqual(json.loads(version['snapshot'])['expected_result'],'Legacy outcome')
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM test_case_versions').fetchone()[0],1)
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM test_executions').fetchone()[0],0)
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM bugs').fetchone()[0],0)
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM bug_history').fetchone()[0],0)
                        versions=c.execute('SELECT * FROM requirement_versions WHERE requirement_id=11').fetchall()
                        self.assertEqual(len(versions),1)
                        self.assertEqual(json.loads(versions[0]['snapshot'])['description'],'Original text')
                        self.assertEqual(c.execute('SELECT COUNT(*) FROM requirement_reviews').fetchone()[0],0)
                        self.assertIsNone(row['reviewed_content_revision'])
                        self.assertEqual(c.execute('PRAGMA foreign_keys').fetchone()[0],1)
                    finally:
                        c.close()


if __name__ == '__main__':
    unittest.main()
