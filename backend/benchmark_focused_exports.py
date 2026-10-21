"""Isolated repeatable export measurements. No provider or configured database use."""
import argparse
import json
import logging
import time
from pathlib import Path
from unittest.mock import patch
import app
from database import DatabaseConnection
from benchmark_release import summary
from test_integrated_reporting import IntegratedReportingTests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    IntegratedReportingTests.setUpClass()
    fixture = IntegratedReportingTests()
    fixture.setUp()
    try:
        for index in range(19):
            fixture.f.requirement(title=f'Synthetic export {index}')
        results = {}
        for label, path in [('requirement_pdf', f'/api/requirements/{fixture.r["id"]}/report.pdf'),
                            ('project_pdf', '/api/reports/project.pdf'),
                            ('csv', '/api/exports/requirements.csv')]:
            times, counts = [], []
            for _ in range(20):
                count = 0
                execute = DatabaseConnection.execute
                def measured(connection, *a, **kw):
                    nonlocal count
                    count += 1
                    return execute(connection, *a, **kw)
                with patch.object(DatabaseConnection, 'execute', measured):
                    started = time.perf_counter()
                    response = fixture.engineer.get(path)
                    response.get_data()
                    times.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200, response.status_code
                counts.append(count)
            results[label] = dict(**summary(times), sql_statements=counts)
        data = dict(environment='Windows / Flask test client / temporary SQLite, sequential; 20 requirements, one detailed case; no AI; initialized schema; first is not hosting cold start', results=results)
        Path(args.output).write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(json.dumps({key: {k: v for k, v in value.items() if k != 'sql_statements'} for key, value in results.items()}))
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
