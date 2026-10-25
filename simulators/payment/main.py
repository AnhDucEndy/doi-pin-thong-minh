import argparse
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn

from app.api.payments import ProviderChargeRequest, secret
from app.application.identity import DomainError
from app.config import ROOT, ConfigNotReady


class Ledger:
    def __init__(self, path, scenario='success', delay=2):
        path = Path(path).resolve()
        if not path.is_relative_to(ROOT) or path.suffix != '.sqlite3':
            raise ValueError('Payment ledger must be a .sqlite3 file inside the workspace')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.scenario, self.delay = path, scenario, delay
        with closing(self.connect()) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('CREATE TABLE IF NOT EXISTS charges (provider_key TEXT PRIMARY KEY, payment_id TEXT UNIQUE NOT NULL, swap_id TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL, reference TEXT UNIQUE NOT NULL, amount INTEGER NOT NULL, currency TEXT NOT NULL, result TEXT NOT NULL, due REAL)')
            connection.execute('CREATE TABLE IF NOT EXISTS callback_deliveries (event_id TEXT PRIMARY KEY, delivered_at REAL NOT NULL)')

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def charge(self, body):
        data = body.model_dump(mode='json')
        hashed = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        with closing(self.connect()) as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM charges WHERE provider_key=?', (str(body.provider_key),)).fetchone()
            if row and row['request_hash'] != hashed:
                raise DomainError(409, 'IDEMPOTENCY_CONFLICT')
            if not row:
                state = 'FAILED' if self.scenario == 'failure' else 'PENDING' if self.scenario in ('timeout','delayed') else 'SUCCEEDED'
                try:
                    connection.execute('INSERT INTO charges VALUES (?,?,?,?,?,?,?,?,?)',
                        (data['provider_key'], data['payment_id'], data['swap_id'], hashed, 'mock-' + uuid4().hex,
                         body.amount_minor, body.currency, state, time.time() + self.delay if self.scenario == 'delayed' else None))
                except sqlite3.IntegrityError as error:
                    raise DomainError(409, 'RESOURCE_CONFLICT') from error
            connection.commit()  # Receipt durable before a simulated lost response.
        if self.scenario == 'lost-response':
            raise DomainError(503, 'MOCK_RESPONSE_LOST')
        return self.query(body.provider_key)

    def query(self, key):
        with closing(self.connect()) as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM charges WHERE provider_key=?', (str(key),)).fetchone()
            if row and row['due'] is not None and time.time() >= row['due'] and row['result'] == 'PENDING':
                connection.execute("UPDATE charges SET result='SUCCEEDED' WHERE provider_key=?", (str(key),))
                row = connection.execute('SELECT * FROM charges WHERE provider_key=?', (str(key),)).fetchone()
            connection.commit()
        return {'provider_key': str(key), 'provider_reference': row['reference'] if row else None,
                'result': row['result'] if row else 'NOT_FOUND', 'amount_minor': row['amount'] if row else None,
                'currency': row['currency'] if row else None}


def create_app(path=None, scenario=None, delay=2):
    ledger = Ledger(path or os.getenv('PAYMENT_LEDGER_PATH', ROOT / '.local/payment/ledger.sqlite3'),
                    scenario or os.getenv('PAYMENT_MOCK_SCENARIO', 'success'), delay)
    app = FastAPI(title='Private payment mock · simulation only', version='0.6.0')
    app.state.ledger = ledger

    def auth(key: str | None = Header(None, alias='X-Service-Key')):
        if not key or not hmac.compare_digest(key.encode(), secret('PAYMENT_SERVICE_KEY').encode()):
            raise DomainError(401, 'AUTH_REQUIRED')

    @app.exception_handler(DomainError)
    async def error(request, exc):
        return JSONResponse(status_code=exc.status, content={'code': exc.code, 'message': 'Mock request rejected',
            'correlation_id': str(uuid4()), 'details': {}})

    @app.exception_handler(ConfigNotReady)
    async def config_error(request, exc):
        return JSONResponse(status_code=503, content={'code':'CONFIG_NOT_READY','message':'Private mock key required',
            'correlation_id':str(uuid4()),'details':{}})

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={'code':'VALIDATION_ERROR','message':'Invalid mock fields',
            'correlation_id':str(uuid4()),'details':{}})

    @app.post('/mock/v1/charges', status_code=202, operation_id='providerCharge')
    def charge(body: ProviderChargeRequest, key: UUID = Header(alias='Idempotency-Key'), authenticated=Depends(auth)):
        if key != body.provider_key:
            raise DomainError(409, 'IDEMPOTENCY_CONFLICT')
        return ledger.charge(body)

    @app.get('/mock/v1/charges/{provider_key}', operation_id='providerQueryCharge')
    def query(provider_key: UUID, authenticated=Depends(auth)):
        return ledger.query(provider_key)

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--scenario', choices=['success','failure','timeout','lost-response','delayed'], default=None)
    args = parser.parse_args()
    uvicorn.run(create_app(scenario=args.scenario), host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
