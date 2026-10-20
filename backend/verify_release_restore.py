"""Backup/restore rehearsal exclusively on disposable synthetic SQLite evidence."""
import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
import app
from test_integrated_reporting import IntegratedReportingTests

logging.disable(logging.CRITICAL)
IntegratedReportingTests.setUpClass();f=IntegratedReportingTests();f.setUp()
try:
    failed=f.run_case('Fail');bug=f.create_bug(failed);passed=f.run_case('Pass');f.approve()
    for status in ('In Progress','Ready for Retest','Closed'):
        data=dict(revision=bug['revision'],status=status)
        if status=='Closed':data['retest_execution_id']=passed['id']
        response=f.write('patch',f'/api/bugs/{bug["id"]}/status',data);assert response.status_code==200
        bug=response.json['bug']
    original=f.graph()
    source_path=app.DATABASE
    with tempfile.TemporaryDirectory() as directory:
        backup=Path(directory)/'backup.db';restored=Path(directory)/'restored.db'
        source=sqlite3.connect(source_path.resolve().as_uri()+'?mode=ro',uri=True)
        target=sqlite3.connect(backup);source.backup(target);target.close();source.close()
        f.edit_source('Customers can view the subject of tickets they own.')
        assert f.graph()['current_content_revision']!=original['current_content_revision']
        source=sqlite3.connect(backup.resolve().as_uri()+'?mode=ro',uri=True)
        target=sqlite3.connect(restored);source.backup(target);target.close();source.close()
        with patch.object(app,'DATABASE',restored):
            client=f.f.client(3)
            graph=client.get(f'/api/requirements/{f.r["id"]}/traceability').json
            assert graph==original
            c=app.get_connection()
            try:
                assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                assert not c.execute('PRAGMA foreign_key_check').fetchall()
            finally:c.close()
        print(json.dumps(dict(source='disposable synthetic SQLite only',backup_restored_to_new_path=True,graph_exact_match=True,history_bug_closure_and_execution_integrity='passed',post_backup_writes_not_in_restored_copy=True,sqlite_integrity='ok',foreign_key_check='passed')))
finally:f.doCleanups()
