"""Explicit, additive demo fixtures for an existing, initialized SQLite database.

No configured DATABASE_URL, migrations, user creation, provider calls or credentials.
Run --help for usage. Existing samples (including edits) are preserved on rerun.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3


SAMPLES = (
    ('clear', 'Owned support ticket', 'An authenticated customer can view the subject and description of a support ticket they own.',
     'High', 'Ready for Review', 'An owner sees the subject and description of their ticket.', 'Positive',
     'Open a ticket owned by the signed-in customer.', 'The owned ticket subject and description appear.'),
    ('ambiguous', 'Fast search', 'The system should return useful search results quickly.',
     'Medium', 'Needs Revision', 'TO BE CONFIRMED: define response time, load and relevance measures.', 'Negative',
     'Search under the agreed workload.', 'BLOCKED pending clarification of measurable response time and relevance.'),
    ('incomplete', 'Payment failure notification', 'Notify the customer when a payment fails.',
     'High', 'In Review', 'TO BE CONFIRMED: define channel, retry policy and notification deadline.', 'Negative',
     'Simulate a declined payment in the payment sandbox.', 'BLOCKED pending clarification of channel and delivery deadline.'),
    ('edge', 'Reject another customer ticket', 'When a customer requests a ticket owned by another customer, return access denied without exposing ticket content.',
     'High', 'Draft', 'A non-owner receives access denied and no ticket subject or description.', 'Edge-case',
     'Request another customer ticket while authenticated.', 'Access is denied and no ticket content is disclosed.'),
)


def seed(connection, owner_id, reviewer_id):
    """One atomic transaction; SQLite write lock also serializes concurrent reruns."""
    from services.case_service import register_generated_cases
    from services.integrated_service import remember_version
    from services.requirement_helpers import _get_requirement_detail, _utc_timestamp

    if connection.dialect != 'sqlite':
        raise ValueError('Demo seeding supports explicitly selected SQLite databases only.')
    created = skipped = 0
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        owner = connection.execute('SELECT * FROM users WHERE id=?', (owner_id,)).fetchone()
        reviewer = connection.execute('SELECT * FROM users WHERE id=?', (reviewer_id,)).fetchone()
        if not owner or not owner['is_active'] or not owner['project_access'] or owner['role'] not in ('Analyst', 'admin'):
            raise ValueError('Select an existing active Analyst or admin with project access as owner.')
        if not reviewer or not reviewer['is_active'] or not reviewer['project_access'] or reviewer['role'] != 'SQA Engineer':
            raise ValueError('Select an existing active SQA Engineer with project access as reviewer.')
        for code, title, description, priority, status, criterion, category, step, expected in SAMPLES:
            # Durable marker uses the existing unique submission receipt, rather
            # than a mutable title. Scope to the project, even if owner changes.
            key = 'demo-v1-' + code
            prior = connection.execute('SELECT input_hash FROM requirement_submissions WHERE request_key=?', (key,)).fetchall()
            if any(row['input_hash'] != 'hand-authored-demo-v1' for row in prior):
                raise ValueError('A non-demo submission already uses a demo receipt key.')
            if prior:
                skipped += 1
                continue
            now = _utc_timestamp()
            summary = json.dumps({'demo': True, 'status': 'not_analyzed',
                                  'note': 'Hand-authored demo fixture; run AI analysis explicitly.'})
            rid = connection.execute(
                'INSERT INTO requirements(title,description,requirement_type,priority,user_priority,review_status,created_by_user_id,assigned_reviewer_user_id,analysis_summary,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                ('[DEMO] ' + title, '[DEMO] ' + description, 'Functional', priority, priority, status, owner_id, reviewer_id, summary, now)).lastrowid
            connection.execute('INSERT INTO requirement_acceptance_criteria(requirement_id,criterion_code,description,source,needs_confirmation) VALUES(?,?,?,?,1)',
                               (rid, 'AC-001', criterion, 'original'))
            connection.execute('INSERT INTO test_scenarios(requirement_id,scenario_code,category,title,preconditions,test_steps,expected_result,criterion_codes,source,needs_confirmation) VALUES(?,?,?,?,?,?,?,?,?,1)',
                               (rid, 'SC-001', category, '[DEMO] ' + title, json.dumps(['Synthetic test accounts and tickets exist.']), json.dumps([step]), expected, json.dumps(['AC-001']), 'original'))
            register_generated_cases(connection, rid)
            detail = _get_requirement_detail(connection, rid, include_history=False)
            remember_version(connection, detail, owner_id, now, 'hand-authored demo fixture')
            if status in ('In Review', 'Needs Revision'):
                notes = '[DEMO] Synthetic review: resolve the marked acceptance-criteria questions before approval.'
                connection.execute('UPDATE requirements SET reviewer_notes=?,reviewed_by_user_id=?,reviewed_at=?,reviewed_content_revision=1 WHERE id=?', (notes, reviewer_id, now, rid))
                evidence = {'demo': True, 'requirement_revision': 1, 'execution_ids': [], 'bug_ids': [],
                            'case_version_ids': [v[0] for v in connection.execute('SELECT v.id FROM test_case_versions v JOIN test_scenarios s ON s.id=v.scenario_id WHERE s.requirement_id=?', (rid,))]}
                connection.execute('INSERT INTO requirement_reviews(requirement_id,project_id,content_revision,status,reviewer_id,reviewer_name,notes,reviewed_at,snapshot) VALUES(?,?,?,?,?,?,?,?,?)',
                                   (rid, 'current', 1, status, reviewer_id, reviewer['name'], notes, now, json.dumps(evidence)))
            connection.execute('INSERT INTO requirement_submissions(user_id,request_key,input_hash,requirement_id) VALUES(?,?,?,?)', (owner_id, key, 'hand-authored-demo-v1', rid))
            created += 1
    return {'created': created, 'skipped': skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite', type=Path, required=True, help='Existing initialized local/demo SQLite file; never uses DATABASE_URL.')
    parser.add_argument('--owner-id', type=int, required=True)
    parser.add_argument('--reviewer-id', type=int, required=True)
    args = parser.parse_args()
    target = args.sqlite.resolve(strict=True)
    # Set before app imports in the helpers. dotenv cannot replace explicit empty
    # configuration; the selected database is opened directly without migrations.
    os.environ['DATABASE_URL'] = ''
    # The service layer imports app configuration and app registers its routes.
    # Initialize that module first to avoid a standalone-CLI circular import.
    import app  # noqa: F401
    from database import DatabaseConnection
    raw = sqlite3.connect(target.as_uri() + '?mode=rw', uri=True)
    raw.row_factory = sqlite3.Row
    raw.execute('PRAGMA foreign_keys=ON')
    connection = DatabaseConnection(raw, 'sqlite')
    try:
        before = connection.execute('SELECT COUNT(*) FROM requirements').fetchone()[0]
        result = seed(connection, args.owner_id, args.reviewer_id)
        print(json.dumps({'database': str(target), 'requirements_before': before, **result}))
    except (ValueError, sqlite3.Error) as error:
        raise SystemExit('Demo seed failed; transaction rolled back. Check schema and selected account roles. ' + type(error).__name__) from None
    finally:
        connection.close()


if __name__ == '__main__':
    main()
