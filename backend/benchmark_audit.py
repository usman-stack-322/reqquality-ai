"""Repeatable audit baseline against temporary data; never uses the configured DB."""
import json
import logging
from statistics import median
from time import perf_counter
from unittest.mock import patch
import app
from test_admin_dashboard import ManagerTests

logging.disable(logging.CRITICAL)
ManagerTests.setUpClass()
fixture = ManagerTests()
fixture.setUp()
try:
    for index in range(100):
        rid = fixture.requirement(title=f'Requirement {index}', analysis_summary=json.dumps({'improved_requirement': 'Example refinement. ' * 200}))
        fixture.criteria(rid)
        fixture.scenario(rid)
    for user_id, role in [(1, 'SQA Admin'), (2, 'Analyst'), (3, 'SQA Engineer')]:
        client = fixture.client(user_id)
        for endpoint in ['/api/auth/me', '/api/dashboard', '/api/requirements', '/api/requirements?view=summary']:
            samples = []
            for _ in range(7):
                start = perf_counter()
                response = client.get(endpoint)
                samples.append(round((perf_counter() - start) * 1000, 2))
                assert response.status_code == 200, response.status_code
            print(json.dumps({'role': role, 'endpoint': endpoint, 'median_ms': median(samples), 'bytes': len(response.data), 'server_timing': response.headers.get('Server-Timing')}))
finally:
    fixture.tearDown()
