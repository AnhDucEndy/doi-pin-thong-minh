"""F3 live smoke: no successful asset mutations in the demo schema."""
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
        health = httpx.get('http://127.0.0.1:8000/health', timeout=10)
        assert health.status_code == 200 and health.json()['phase'] == 3
        checks.append('Phase 3 health / PostgreSQL connected')
        for name in ['admin', 'technician', 'customer']:
            login = client.post('/v1/auth/login', json={'username': name, 'password': os.environ[f'DEMO_{name.upper()}_PASSWORD']})
            assert login.status_code == 200
            auth = {'Authorization': 'Bearer '+login.json()['access_token']}
            result = client.get('/v1/batteries?limit=100', headers=auth)
            assert result.status_code == (403 if name == 'customer' else 200)
            if name != 'customer':
                assert len(result.json()['items']) == (11 if name == 'admin' else 5)
            else:
                assert result.json()['code'] == 'FORBIDDEN'
            checks.append(f'{name}: scoped battery list')
            for station in ['S01','S02']:
                response = client.get(f'/v1/batteries/{demo_id(station+":battery:2")}/telemetry', headers=auth)
                expected = 403 if name == 'customer' or name == 'technician' and station == 'S02' else 200
                assert response.status_code == expected
                if expected == 200:
                    assert response.headers['X-Battery-Available'] == 'false'
                    assert response.json()['items'] and response.json()['items'][0]['quality_ok'] is False
                checks.append(f'{name}: {station} telemetry {expected}')
            if name == 'admin':
                response = client.get(f'/v1/batteries/{uuid4()}/telemetry', headers=auth)
                assert response.status_code == 404 and response.json()['code'] == 'RESOURCE_NOT_FOUND'
                checks.append('Missing battery 404')
                response = client.post('/v1/batteries', headers={**auth,'Idempotency-Key':str(uuid4())}, json={
                    'serial':'SHOULD-NOT-BE-CREATED', 'family':'INVALID', 'location_kind':'UNKNOWN'})
                assert response.status_code == 422 and response.json()['code'] == 'BATTERY_FAMILY_INVALID'
                checks.append('Invalid family 422 / no asset created')
            result = client.post('/v1/auth/logout', headers={**auth,'Idempotency-Key':str(uuid4())})
            assert result.status_code == 200
            checks.append(f'{name}: logout')
    result = {'result':'Passed','asset_mutations':False,'checks':checks}
    (ROOT/'docs/PHASE3_HTTP_SMOKE_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f'{len(checks)} HTTP smoke checks Passed; no secrets printed')


if __name__ == '__main__':
    main()
