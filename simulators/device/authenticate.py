"""Interactive local QR/RFID reader adapter. Never put a credential in argv/logs."""
import argparse
import getpass
import os
import sys
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from app.config import approved_policy


def main():
    parser = argparse.ArgumentParser(description='QR/RFID reader, simulation only')
    parser.add_argument('--station', choices=['S01', 'S02'], required=True)
    parser.add_argument('--method', choices=['QR', 'RFID'], required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--request-id', type=UUID, default=None, help='Reuse this UUID only for retry of the same read')
    args = parser.parse_args()
    approved_policy()
    if urlsplit(args.url).hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Simulation reader is loopback-only')
    key = os.getenv('DEMO_DEVICE_KEY_' + args.station)
    if not key:
        raise ValueError('Device key must be supplied in local environment')
    request_id = args.request_id or uuid4()
    if not sys.stdin.isatty():
        raise ValueError('Use an interactive terminal so getpass can hide the credential')
    credential = getpass.getpass('QR token / RFID (hidden): ')
    print(f'Request ID (reuse for exact retry): {request_id}', flush=True)
    try:
        with httpx.Client(base_url=args.url, timeout=15, trust_env=False) as client:
            response = client.post('/v1/device/verifications', headers={
                'X-Device-Key': key, 'Idempotency-Key': str(request_id)},
                json={'method': args.method, 'credential': credential})
    except httpx.HTTPError:
        raise SystemExit('Transport result unknown. Retry the same credential with the request ID above.') from None
    data = response.json()
    if response.status_code == 201:
        print(f'Simulation verification: {data["state"]}; swap_id={data["id"]}. No resource hold or actuator effect yet.')
    else:
        print(f'HTTP {response.status_code}: {data.get("code", "ERROR")}')


if __name__ == '__main__':
    main()
