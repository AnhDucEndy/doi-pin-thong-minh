"""Two-process legacy settlement ordering checks on the smoke runner's private schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, text, update


def app():
    from app.application import recovery
    from app.main import create_app
    from tools.smoke_phase4 import wait

    if not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
        raise RuntimeError('Expected isolated test schema')
    directory = Path(os.environ['P8_RACE_DIR'])
    audit = recovery.audit

    def barrier(session, db, actor, case, action, after):
        audit(session, db, actor, case, action, after)
        if action == 'MANUAL_RECOVERY_SETTLED' and (directory/'armed').is_file():
            marker = directory/'decision.tmp'
            marker.write_text(str(session.scalar(text('select pg_backend_pid()'))))
            marker.replace(directory/'decision')
            wait(lambda: (directory/'resume').is_file(), 'Release audited settlement', 10)

    recovery.audit = barrier
    return create_app()


def verify_order(first, second, base, body, witness, customer, directory, ledgers,
                 fixture, swap, op, demo, fingerprint, pids):
    from app.application.identity import digest
    from phase8a_logout_race import verify
    from smoke_phase4 import wait
    from test_phase5 import login

    db = fixture['seed_db']
    caller = login(first, fixture, 'technician')
    sessions = db.table('auth_sessions')
    def token(headers):
        with db.sessions() as s:
            return s.execute(select(sessions).where(sessions.c.token_hash ==
                digest(headers['Authorization'].removeprefix('Bearer ')))).mappings().one()

    caller_token, witness_token = token(caller), token(witness)
    assert caller_token['user_id'] == witness_token['user_id'] and caller_token['id'] != witness_token['id']
    identity = caller_token['id']
    # Only shorten the separate caller's test login. Leave all business evidence
    # and policy clocks untouched. Observe a real row wait BEFORE expiry.
    with db.sessions.begin() as s:
        expiry = s.scalar(text('select clock_timestamp()')) + timedelta(seconds=3)
        s.execute(update(sessions).where(sessions.c.id == identity).values(expires_at=expiry))
    with ThreadPoolExecutor(1) as pool:
        with db.sessions.begin() as blocker:
            pid = blocker.scalar(text('select pg_backend_pid()'))
            blocker.execute(select(sessions.c.id).where(sessions.c.id == identity).with_for_update())
            pending = pool.submit(first.post, base+'/settle', headers={**caller,'Idempotency-Key':str(uuid4())},json=body)
            wait(lambda: blocker.scalar(text('select exists(select from pg_stat_activity '
                'where application_name=:name and :pid=any(pg_blocking_pids(pid)))'),
                {'pid':pid,'name':f'{directory.name}-8030'}), 'Settlement waits for caller session', 3)
            assert blocker.scalar(text('select clock_timestamp()')) < expiry
            wait(lambda: blocker.scalar(text('select clock_timestamp()')) >= expiry, 'Actual session expiry', 4)
        refused = pending.result()
    assert refused.status_code == 401 and refused.json()['code'] == 'SESSION_REVOKED', refused.text
    print('Expired caller after observable row wait: 401 SESSION_REVOKED')

    # The unchanged verifier checks DB/ledger facts before and after settlement.
    # This time its marker fires after success audit, while the transaction still
    # holds its session locks. A fresh caller uses the original Technician proof.
    active = login(first, fixture, 'technician')
    verify(first, second, base, body, active, customer, 'technician', directory, ledgers,
           db, fixture['settings'].schema, swap, op, demo, fingerprint, pids)
    report = json.loads((directory/'race.json').read_text())
    assert report['revoked_before_final_check'] is False
    assert report['after']['version'] == body['expected_version'] + 1 and report['after']['old_settled']
    assert second.get('/v1/me', headers=active).status_code == 401
    assert second.get('/v1/me', headers=witness).status_code == 200
    print('Observed logout lock wait, one settlement commit, then logout; witness login remains active')
