"""Read-only API RBAC checks against an already running isolated browser fixture."""
import json
from pathlib import Path
import sys
import httpx

root = Path(__file__).resolve().parents[1]
path = (root / sys.argv[1]).resolve()
assert path.is_relative_to(root / '.cache')
fixture = json.loads(path.read_text(encoding='utf-8'))
assert fixture['schema'].startswith('phase5_test_')
checks = []
with httpx.Client(base_url='http://127.0.0.1:8020') as client:
    for name in ('customer', 'admin', 'technician'):
        login = client.post('/v1/auth/login', json={'username': name, 'password': fixture['passwords'][name]})
        assert login.status_code == 200
        headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
        for route, expected in [('/v1/swaps/' + fixture['swap_id'], 403 if name == 'technician' else 200),
                                ('/v1/users', 200 if name == 'admin' else 403)]:
            response = client.get(route, headers=headers)
            assert response.status_code == expected
            checks.append({'role': name, 'method': 'GET', 'path': route, 'status': response.status_code,
                           'error': response.json() if expected == 403 else None})
    response = client.get('/v1/swaps/' + fixture['swap_id'])
    assert response.status_code == 401
    checks.append({'role': 'anonymous', 'status': 401})
output = root / 'docs/PHASE7_TESTS/remaining_browser_evidence/rbac_resume.json'
output.write_text(json.dumps({'checks': checks, 'result': 'Passed'}, indent=2), encoding='utf-8')
print('7 read-only API authorization checks Passed')
