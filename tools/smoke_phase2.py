"""Read-only F2 smoke through Vite proxy; login/logout create normal session audit."""
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/backend'))
from app.config import ROOT
from app.seed import demo_id
import httpx


def main():
    checks = []
    with httpx.Client(base_url='http://127.0.0.1:5173', timeout=10) as client:
        assert client.get('/').status_code == 200
        checks.append('Frontend HTML 200')
        # Vite only proxies /v1; health belongs to the backend directly.
        health = httpx.get('http://127.0.0.1:8000/health', timeout=10)
        assert health.status_code == 200 and health.json()['database'] == 'connected'
        checks.append('Backend health / PostgreSQL connected')
        for role in ['admin', 'customer', 'technician']:
            response = client.post('/v1/auth/login', json={'username': role, 'password': os.environ[f'DEMO_{role.upper()}_PASSWORD']})
            assert response.status_code == 200
            headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
            response = client.get('/v1/stations', headers=headers)
            assert response.status_code == 200 and len(response.json()['items']) == 2
            checks.append(f'{role}: two stations / availability projection')
            for code in ['S01', 'S02']:
                response = client.get(f'/v1/stations/{demo_id(code)}/compartments', headers=headers)
                expected = 200 if role == 'admin' or role == 'technician' and code == 'S01' else 403
                assert response.status_code == expected
                if expected == 200:
                    assert len(response.json()['items']) == 6
                checks.append(f'{role}: {code} compartments {expected}')
            response = client.post('/v1/auth/logout', headers={**headers, 'Idempotency-Key': str(uuid4())})
            assert response.status_code == 200
            checks.append(f'{role}: logout 200')
    result = {'result': 'Passed', 'checks': checks, 'asset_mutations': False}
    (ROOT / 'docs/PHASE2_HTTP_SMOKE_RESULTS.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{len(checks)} HTTP smoke checks Passed; no credentials printed')


if __name__ == '__main__':
    main()
