"""Storage contract probes: isolated PostgreSQL, no custody/physical fixture writes.

These test database defenses, not authorization policy or end-to-end recovery.
"""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import DBAPIError

from app.application.identity import utcnow
from test_phase8a_api import start_case, begin
from test_phase5 import race_environment


def staged_operation(client, environment, auth, *, committed=False):
    if committed:
        from test_phase6 import book, consent, outcome
        from test_phase4 import row
        from app.workers import payment
        from app.application.swaps import review
        actor = auth('customer')
        swap = book(client, environment, actor, environment['seed_db'])
        assert consent(client, actor, swap).status_code == 202
        payment.tick(client.app.state.db, transport=outcome)
        db = client.app.state.db
        with db.sessions.begin() as session:
            review(session, db, row(client, 'swap_transactions', UUID(swap['id'])), 'TEST_STORAGE_CONSTRAINTS')
        tech = auth('technician')
        case = client.get(f"/v1/swaps/{swap['id']}/recovery", headers=tech).json()
    else:
        swap, tech, case = start_case(client, environment, auth)
    response = begin(client, swap, tech, case)
    assert response.status_code == 200
    db = client.app.state.db
    with db.sessions.begin() as session:
        operations = db.table('recovery_operations')
        legacy = dict(session.execute(select(operations).where(
            operations.c.id == UUID(response.json()['active_operation']['id']))).mappings().one())
        # Deliberately insert ONLY an operation for DB constraint tests. This is
        # not a simulated observation, authorization, or successful settlement.
        staged = {**legacy, 'id': uuid4(), 'purpose': 'RETURN_FOREIGN_OBJECT', 'pin_id': None,
                  'protocol_version': '0.2'}
        session.execute(insert(operations).values(**staged))
    return staged, legacy


def attestation(client, op, stage, source='SIMULATOR', reference=None):
    from app.seed import demo_id
    now = utcnow()
    return dict(id=uuid4(), event_id=uuid4(), operation_id=op['id'], stage=stage,
        reference_receipt_id=reference, source_kind=source,
        actor_user_id=None if source=='SIMULATOR' else op['created_by'] if source=='TECHNICIAN' else op['customer_id'],
        device_id=demo_id('device:S01') if source=='SIMULATOR' else None,
        source_boot=uuid4() if source=='SIMULATOR' else None, source_seq=1 if source=='SIMULATOR' else None,
        observed_at=now, received_at=now, payload={}, payload_hash='a'*64)


def test_db_allows_distinct_pre_and_post_but_not_duplicate_source(client, environment, auth):
    op, _ = staged_operation(client, environment, auth)
    db = client.app.state.db
    with db.sessions.begin() as session:
        table = db.table('recovery_attestations')
        for stage in ('PRE_ACTION_INSPECTION', 'POST_ACTION_RECEIPT'):
            receipt = attestation(client, op, stage)
            session.execute(insert(table).values(**receipt))
            for source in ('TECHNICIAN', 'CUSTOMER'):
                session.execute(insert(table).values(**attestation(client, op, stage, source, receipt['id'])))
        assert len(session.execute(select(table).where(table.c.operation_id==op['id'])).all()) == 6
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(insert(table).values(**attestation(client, op, 'PRE_ACTION_INSPECTION')))


@pytest.mark.parametrize('fault', ['wrong_stage', 'wrong_operation', 'human_reference', 'missing_reference', 'before_receipt'])
def test_db_rejects_invalid_human_receipt_binding(client, environment, auth, fault):
    op, legacy = staged_operation(client, environment, auth)
    db = client.app.state.db
    with db.sessions.begin() as session:
        table = db.table('recovery_attestations')
        receipt = attestation(client, legacy if fault=='wrong_operation' else op,
            'LEGACY' if fault=='wrong_operation' else 'PRE_ACTION_INSPECTION')
        session.execute(insert(table).values(**receipt))
        human = attestation(client, op, 'POST_ACTION_RECEIPT' if fault=='wrong_stage' else 'PRE_ACTION_INSPECTION',
                            'CUSTOMER', None if fault=='missing_reference' else receipt['id'])
        if fault=='human_reference':
            tech = attestation(client, op, 'PRE_ACTION_INSPECTION', 'TECHNICIAN', receipt['id'])
            session.execute(insert(table).values(**tech))
            human['reference_receipt_id'] = tech['id']
        if fault=='before_receipt':
            human['observed_at'] = op['created_at']
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(insert(table).values(**human))
        assert session.scalar(select(table.c.id).where(table.c.id==human['id'])) is None


@pytest.mark.parametrize('legacy', [False, True])
def test_db_disallows_legacy_stage_protocol_crossing(client, environment, auth, legacy):
    op, old = staged_operation(client, environment, auth)
    db = client.app.state.db
    with db.sessions.begin() as session:
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(insert(db.table('recovery_attestations')).values(**attestation(client,
                    old if legacy else op, 'PRE_ACTION_INSPECTION' if legacy else 'LEGACY')))


def test_authorization_grants_do_not_allow_mutating_context(environment):
    schema = environment['settings'].schema
    with environment['owner'].connect() as conn:
        name = f'{schema}.recovery_action_authorizations'
        assert conn.scalar(text("SELECT has_column_privilege('doi_pin_runtime',:name,'revoked_at','UPDATE')"), {'name': name})
        for column in ('operation_id', 'inspection_id', 'authorized_by', 'expires_at', 'payload'):
            assert not conn.scalar(text("SELECT has_column_privilege('doi_pin_runtime',:name,:column,'UPDATE')"), {'name': name, 'column': column})
        assert not conn.scalar(text("SELECT has_table_privilege('doi_pin_runtime',:name,'DELETE')"), {'name': name})


def permit_fixture(client, op):
    """Storage-only rows; never call settlement with these synthetic DB probes."""
    db = client.app.state.db
    receipt = attestation(client, op, 'PRE_ACTION_INSPECTION')
    tech = attestation(client, op, 'PRE_ACTION_INSPECTION', 'TECHNICIAN', receipt['id'])
    customer = attestation(client, op, 'PRE_ACTION_INSPECTION', 'CUSTOMER', receipt['id'])
    with db.sessions.begin() as session:
        for record in (receipt, tech, customer):
            session.execute(insert(db.table('recovery_attestations')).values(**record))
    return dict(id=uuid4(), operation_id=op['id'], context_hash=op['context_hash'], inspection_id=receipt['id'],
        technician_attestation_id=tech['id'], customer_attestation_id=customer['id'], device_id=receipt['device_id'],
        boot_id=receipt['source_boot'], ledger_id=uuid4(), fence_generation=1, authorized_by=op['created_by'],
        issued_at=utcnow(), expires_at=op['expires_at'], authorization_hash='b'*64, payload={})


def test_authorization_immutable_and_rollback_does_not_consume_operation(client, environment, auth):
    from sqlalchemy import update
    op, _ = staged_operation(client, environment, auth)
    permit = permit_fixture(client, op)
    db = client.app.state.db
    with db.sessions.begin() as session:
        table = db.table('recovery_action_authorizations')
        with pytest.raises(RuntimeError, match='INJECTED_ROLLBACK'):
            with session.begin_nested():
                session.execute(insert(table).values(**permit))
                raise RuntimeError('INJECTED_ROLLBACK')
        assert session.scalar(select(table.c.id).where(table.c.operation_id==op['id'])) is None
        session.execute(insert(table).values(**permit))
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(update(table).where(table.c.id==permit['id']).values(context_hash='c'*64))
        session.execute(update(table).where(table.c.id==permit['id']).values(revoked_at=utcnow()))
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(update(table).where(table.c.id==permit['id']).values(revoked_at=None))
        operations = db.table('recovery_operations')
        assert session.scalar(select(operations.c.consumed_at).where(operations.c.id==op['id'])) is None


def test_two_postgresql_connections_cannot_store_two_authorizations(race_environment):
    """Two DB PIDs, NOT two Backend OS processes or complete policy authorization."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.infrastructure.db import Database
    from test_phase5 import login
    env = race_environment
    with TestClient(create_app(env['settings'])) as client:
        auth = lambda name='admin': login(client, env, name)
        op, _ = staged_operation(client, env, auth, committed=True)
        permit = permit_fixture(client, op)
        db = Database(env['settings'])
        barrier = Barrier(2)
        def run(_):
            with db.sessions() as session:
                pid = session.scalar(text('SELECT pg_backend_pid()'))
                barrier.wait(timeout=10)
                try:
                    session.execute(insert(db.table('recovery_action_authorizations')).values(**{**permit, 'id': uuid4()}))
                    session.commit()
                    return pid, 'STORED'
                except DBAPIError as exc:
                    session.rollback()
                    assert exc.orig.sqlstate == '23505'
                    return pid, 'DUPLICATE_REJECTED'
        try:
            # Reflect before entering the race: no metadata initialization race.
            table = db.table('recovery_action_authorizations')
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, range(2)))
            assert len({pid for pid, result in results}) == 2
            assert sorted(result for pid, result in results) == ['DUPLICATE_REJECTED', 'STORED']
            with db.sessions() as session:
                assert len(session.execute(select(table).where(table.c.operation_id==op['id'])).all()) == 1
        finally:
            db.engine.dispose()
