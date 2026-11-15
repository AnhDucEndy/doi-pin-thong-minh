"""Test-only barrier at the legacy proof decision. Run via smoke_phase8a --logout-race."""
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select, text


def app():
    from app.application import recovery
    from app.main import create_app

    if not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
        raise RuntimeError('An isolated fixture is required')
    directory = Path(os.environ['P8_RACE_DIR'])
    quiet = recovery.quiet

    def barrier(session, *args, **kwargs):
        result = quiet(session, *args, **kwargs)
        if result and kwargs.get('decision_at') and (directory/'armed').exists():
            marker = directory/'decision.tmp'
            marker.write_text(str(session.scalar(text('select pg_backend_pid()'))))
            marker.replace(directory/'decision')
            deadline = time.monotonic() + 10
            while not (directory/'resume').exists():
                if time.monotonic() > deadline:
                    raise RuntimeError('Decision barrier timed out')
                time.sleep(.01)
        return result

    recovery.quiet = barrier
    return create_app()


def verify(first, second, base, body, tech, customer, role, directory, ledgers,
           db, schema, swap, op, demo, fingerprint, backend_pids):
    from smoke_phase4 import fingerprints, wait

    identity = UUID(swap['id'])
    def facts():
        with db.sessions() as session:
            def row(table, **keys):
                return session.execute(select(db.table(table)).filter_by(**keys)).mappings().one()
            def count(table, **keys):
                return session.scalar(select(func.count()).select_from(db.table(table)).filter_by(**keys))
            case = row('recovery_cases', swap_id=identity)
            workflow = row('swap_transactions', id=identity)
            custody = []
            for key in ('old_battery_id', 'new_battery_id'):
                pin = row('batteries', id=workflow[key])
                custody.append([str(pin[k]) for k in ('id','location_kind','holder_user_id','compartment_id')])
            with sqlite3.connect((ledgers/'S01.sqlite3').as_uri()+'?mode=ro', uri=True) as ledger:
                effects = ledger.execute('select effects from service_operations where id=?',(op['id'],)).fetchone()[0]
            return dict(state=workflow['state'], case=case['state'], version=case['version'],
                        consumed=row('recovery_operations', id=UUID(op['id']))['consumed_at'] is not None,
                        old_settled=case['old_pin_settled'], custody=custody, payment=row('payments',swap_id=identity)['state'],
                        holds=count('resource_reservations', swap_id=identity, released_at=None), effects=effects,
                        audits=count('audit_events', aggregate_id=case['id'], action='MANUAL_RECOVERY_SETTLED'))

    before = facts()
    assert before['state']=='REVIEW_REQUIRED' and not before['consumed'] and not before['old_settled']
    assert before['holds']==3 and before['payment']=='SUCCEEDED' and before['audits']==0
    assert len(set(backend_pids))==2
    (directory/'armed').touch()
    with ThreadPoolExecutor(2) as pool:
        settle = pool.submit(first.post,base+'/settle',headers={**tech,'Idempotency-Key':str(uuid4())},json=body)
        try:
            wait(lambda:(directory/'decision').is_file(),'Reached final custody decision',8)
            pid = int((directory/'decision').read_text())
            actor = customer if role=='customer' else tech
            logout = pool.submit(second.post,'/v1/auth/logout',headers={**actor,'Idempotency-Key':str(uuid4())})
            def ordered():
                with db.sessions() as session:
                    return logout.done() or session.scalar(text(
                        'select exists(select from pg_stat_activity where application_name=:name '
                        'and :pid = any(pg_blocking_pids(pid)))'), {'pid':pid, 'name':f'{directory.name}-8031'})
            wait(ordered,'Committed logout or observable PostgreSQL lock wait',4)
            revoked_first = logout.done()
            if revoked_first:
                assert logout.result().status_code==200 and second.get('/v1/me',headers=actor).status_code==401
        finally:
            (directory/'resume').touch()
        decision = settle.result()
        assert logout.result().status_code==200
    after = facts()
    report = dict(role=role, schema=schema, backend_os_pids=backend_pids, settlement_pg_pid=pid, logout_http=200,
                  revoked_before_final_check=revoked_first, settlement_http=decision.status_code,
                  error_code=decision.json().get('code'), before=before, after=after,
                  demo_fingerprint_unchanged=fingerprints(demo)==fingerprint)
    print(json.dumps(report,indent=2))
    (directory/'race.json').write_text(json.dumps(report,indent=2))
    assert report['demo_fingerprint_unchanged']
    if revoked_first:
        assert decision.status_code in (401,403) and after==before, 'Settlement accepted after committed logout'
    else:
        assert decision.status_code==200 and after['consumed'] and after['audits']==before['audits']+1
        assert all(before[k]==after[k] for k in ('custody','payment','holds','effects'))
