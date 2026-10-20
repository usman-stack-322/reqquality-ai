"""Rehearse V1 upgrades on disposable read-only backups, logging no row contents."""
import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
import app

logging.disable(logging.CRITICAL)
root = Path(__file__).resolve().parent
for source_path in (root / 'instance').glob('*.db'):
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / 'copy.db'
        source = sqlite3.connect(source_path.resolve().as_uri() + '?mode=ro', uri=True)
        target = sqlite3.connect(destination)
        source.backup(target)
        source.close()
        before = {}
        for table in ('requirements', 'test_scenarios', 'requirement_acceptance_criteria'):
            columns = [row[1] for row in target.execute(f'PRAGMA table_info({table})')]
            before[table] = (columns, target.execute(f'SELECT * FROM {table} ORDER BY id').fetchall())
        target.close()
        with patch.multiple(app, DATABASE_URL=None, DATABASE=destination):
            for attempt in range(2):
                c = app.get_connection()
                try:
                    for table, (columns, rows) in before.items():
                        after = c.execute(f'SELECT {",".join(columns)} FROM {table} ORDER BY id').fetchall()
                        assert [tuple(row) for row in after] == rows, table
                    assert c.execute('PRAGMA foreign_keys').fetchone()[0] == 1
                    assert c.execute('SELECT COUNT(*) FROM test_executions').fetchone()[0] == 0
                    assert c.execute('SELECT COUNT(*) FROM bugs').fetchone()[0] == 0
                    assert c.execute('SELECT COUNT(*) FROM bug_history').fetchone()[0] == 0
                finally:
                    c.close()
        print(json.dumps({'database': source_path.name, 'original_rows_unchanged': True,
                          'counts': {table: len(value[1]) for table, value in before.items()},
                          'upgrade_twice': 'passed', 'synthetic_executions_or_bugs': 0,
                          'source': 'read-only backup; untouched'}))
