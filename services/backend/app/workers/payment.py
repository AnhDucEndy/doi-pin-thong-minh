"""Durable CHARGE outbox. Never hold PostgreSQL locks during external HTTP."""
import argparse
from datetime import timedelta
import os
import time
from uuid import UUID
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, update

from app.api.payments import ProviderResult, secret
from app.application import assets, payments
from app.application.identity import utcnow
from app.config import ConfigNotReady, Settings
from app.infrastructure.db import Database
from app.workers.retry import run_tick


def provider_request(payload, query=False):
    base = os.getenv('PAYMENT_MOCK_URL', 'http://127.0.0.1:8001').rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password:
        raise ConfigNotReady('CONFIG_NOT_READY')  # Private loopback mock only, no real financial network.
    key = payload['provider_key']
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        headers = {'X-Service-Key': secret('PAYMENT_SERVICE_KEY')}
        if query:
            response = client.get(base + '/mock/v1/charges/' + str(key), headers=headers)
        else:
            response = client.post(base + '/mock/v1/charges', headers={**headers, 'Idempotency-Key': str(key)}, json=payload)
        response.raise_for_status()
        return ProviderResult.model_validate(response.json()).model_dump(mode='json')


def process_events(db):
    events = db.table('payment_events')
    with db.sessions() as session:
        ids = list(session.scalars(select(events.c.id).where(events.c.processed_at.is_(None)).order_by(events.c.created_at).limit(100)))
    for identity in ids:
        with db.sessions.begin() as session:
            initial = assets.get_row(session, db, 'payment_events', identity)
            swap, payment = payments.lock(session, db, initial['payment_id'])
            event = assets.get_row(session, db, 'payment_events', identity, lock=True)
            if event['processed_at']:
                continue
            payments.apply_result(session, db, swap, payment, event['payload'], utcnow())
            session.execute(update(events).where(events.c.id == identity).values(processed_at=utcnow()))


def tick(db, now=None, transport=None):
    transport = transport or provider_request
    now = now or utcnow()
    process_events(db)
    box = db.table('outbox_messages')
    with db.sessions() as session:
        ids = list(session.scalars(select(box.c.id).where(box.c.kind == 'CHARGE', box.c.delivered_at.is_(None),
            box.c.next_attempt_at <= now).order_by(box.c.created_at).limit(100)))
    for identity in ids:
        with db.sessions.begin() as session:
            initial = assets.get_row(session, db, 'outbox_messages', identity)
            swap, payment = payments.lock(session, db, initial['aggregate_id'])
            message = assets.get_row(session, db, 'outbox_messages', identity, lock=True)
            if message['delivered_at'] or message['next_attempt_at'] > now:
                continue
            if payment['state'] in ('SUCCEEDED', 'FAILED'):
                session.execute(update(box).where(box.c.id == identity).values(delivered_at=now))
                continue
            query = payment['state'] != 'CREATED'
            if not query:
                table = db.table('payments')
                session.execute(update(table).where(table.c.id == payment['id']).values(state='PENDING', version=payment['version'] + 1))
                payments.record(session, db, payment, 'PAYMENT_DISPATCH', {'provider_key':str(payment['provider_key'])})
            elif payment['state'] == 'PENDING':
                payments.apply_result(session, db, swap, payment, {'result':'UNKNOWN'}, now)
            # Commit claim first. A crash may only query the same key on recovery, never charge again.
            session.execute(update(box).where(box.c.id == identity).values(attempts=message['attempts'] + 1,
                next_attempt_at=now + timedelta(seconds=swap['policy_snapshot']['payment_timeout_seconds'])))
            payload = dict(message['payload'])
        try:
            result = transport(payload, query=query)
            result = ProviderResult.model_validate(result).model_dump(mode='json')
        except (httpx.HTTPError, ValueError, ConfigNotReady):
            result = {'result':'UNKNOWN'}
        with db.sessions.begin() as session:
            swap, payment = payments.lock(session, db, UUID(payload['payment_id']))
            payments.apply_result(session, db, swap, payment, result, utcnow())
            payment = assets.get_row(session, db, 'payments', payment['id'])
            if payment['state'] in ('SUCCEEDED', 'FAILED'):
                session.execute(update(box).where(box.c.id == identity).values(delivered_at=utcnow()))
    return len(ids)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--once', action='store_true'); args = parser.parse_args()
    db = Database(Settings.from_env())
    try:
        while True:
            run_tick(lambda: tick(db), 'payment')
            if args.once:
                break
            time.sleep(1)
    finally:
        db.engine.dispose()


if __name__ == '__main__':
    main()
