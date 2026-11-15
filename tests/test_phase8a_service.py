"""Durable SQLite service-effect tests; HTTP trust decisions are fixture inputs.

These do not replace PostgreSQL/API or real-process E2E tests.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from uuid import uuid4

import httpx
import pytest

from app.application.identity import utcnow
from app.seed import demo_id
from simulators.device.main import Simulator
from simulators.device.service import perform


def task(purpose='RETURN_OLD_TO_CUSTOMER'):
    return {'operation_id': str(uuid4()), 'swap_id': str(uuid4()), 'purpose': purpose,
        'expected_serial': 'S01-B002', 'context_hash': 'a' * 64,
        'return_compartment_id': str(demo_id('S01:slot:2')), 'customer_id': str(demo_id('customer')),
        'created_by': str(demo_id('technician')), 'expires_at': (utcnow()+timedelta(seconds=120)).isoformat()}


def transport(operation, role='TECHNICIAN'):
    def answer(request):
        if request.url.path == '/v1/me':
            return httpx.Response(200, json={'id': operation['created_by'], 'role': role})
        if request.url.path == '/v1/device/recovery-tasks':
            return httpx.Response(200, json={'items': [operation]})
        return httpx.Response(200, json={'active_operation': {**operation, 'id': operation['operation_id']}})
    return httpx.MockTransport(answer)


def simulator(path, operation, role='TECHNICIAN'):
    return Simulator('S01', 'fixture-key-not-a-real-device-key', ledger=path, transport=transport(operation, role))


def test_handover_effect_once_across_restart(tmp_path):
    operation = task()
    path = tmp_path/'service.sqlite3'
    sim = simulator(path, operation)
    try:
        assert perform(sim, operation, technician_token='fixture-token') == 'OBSERVED'
        assert perform(sim, operation, technician_token='fixture-token') == 'OBSERVED'
        assert sim.conn.execute('SELECT effects FROM service_operations').fetchone()[0] == 1
        assert sim.conn.execute('SELECT serial FROM service_positions WHERE serial=?', ('S01-B002',)).fetchone()[0] == 'S01-B002'
    finally:
        sim.close()
    sim = simulator(path, operation)
    try:
        assert perform(sim, operation, technician_token='fixture-token') == 'OBSERVED'
        assert sim.conn.execute('SELECT effects FROM service_operations').fetchone()[0] == 1
        assert sim.conn.execute('SELECT count(*) FROM commands').fetchone()[0] == 0
        slot = next(s for s in sim.slots() if s['compartment_id'] == operation['return_compartment_id'])
        assert not slot['present'] and slot['door_state'] == 'CLOSED'
    finally:
        sim.close()


def test_prepared_crash_never_retries_unknown_effect(tmp_path):
    operation = task()
    path = tmp_path/'crash.sqlite3'
    sim = simulator(path, operation)
    try:
        with pytest.raises(RuntimeError, match='CRASH_AFTER_PREPARED'):
            perform(sim, operation, technician_token='fixture-token', crash_after_prepared=True)
    finally:
        sim.close()
    sim = simulator(path, operation)
    try:
        assert perform(sim, operation, technician_token='fixture-token') == 'UNKNOWN'
        row = sim.conn.execute('SELECT effects,observation FROM service_operations').fetchone()
        assert row['effects'] == 0 and row['observation'] is None
        assert next(s for s in sim.slots() if s['compartment_id'] == operation['return_compartment_id'])['present']
    finally:
        sim.close()


def test_wrong_return_does_not_emit_network_bms_identity_for_foreign_object(tmp_path):
    operation = task()
    sim = simulator(tmp_path/'wrong-return.sqlite3', operation)
    sim.scenario = 'wrong-return'
    command = {'id': str(uuid4()), 'device_id': str(demo_id('device:S01')),
        'swap_id': str(uuid4()), 'compartment_id': str(demo_id('S01:slot:1')),
        'kind': 'OPEN_RETURN', 'expires_at': (utcnow()+timedelta(seconds=15)).isoformat(),
        'payload': {'expected_serial': 'CUSTOMER-B001', 'expected_battery_id': str(demo_id('customer:battery')),
            'customer_id': str(demo_id('customer')), 'simulation_only': True}}
    try:
        assert sim.handle(command) == 'EXECUTED'
        slot = next(s for s in sim.slots() if s['compartment_id'] == command['compartment_id'])
        assert slot['present'] is True and slot['observed_serial'] == 'SIMULATED-WRONG-BATTERY'
        assert slot['battery_id'] is None
        assert sim.conn.execute('SELECT count(*) FROM service_presenters').fetchone()[0] == 1
    finally:
        sim.close()


def test_actual_model_mismatch_not_expected_serial_echo(tmp_path):
    operation = task()
    operation['expected_serial'] = 'DOES-NOT-EXIST'
    sim = simulator(tmp_path/'mismatch.sqlite3', operation)
    try:
        assert perform(sim, operation, technician_token='fixture-token') == 'UNKNOWN'
        entry = sim.conn.execute('SELECT * FROM service_operations').fetchone()
        assert entry['effects'] == 0
        assert json.loads(entry['observation'])['observation']['actual_serial'] is None
    finally:
        sim.close()


def test_admin_read_privilege_is_not_service_operator(tmp_path):
    operation = task()
    sim = simulator(tmp_path/'admin.sqlite3', operation, 'ADMIN')
    try:
        with pytest.raises(ValueError, match='TECHNICIAN_REQUIRED'):
            perform(sim, operation, technician_token='fixture-token')
        assert sim.conn.execute('SELECT count(*) FROM service_operations').fetchone()[0] == 0
    finally:
        sim.close()


def test_two_service_callers_share_durable_effect_fence(tmp_path):
    operation = task()
    path = tmp_path/'race.sqlite3'
    simulator(path, operation).close()
    def run(_):
        sim = simulator(path, operation)
        try:
            return perform(sim, operation, technician_token='fixture-token')
        finally:
            sim.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert set(pool.map(run, range(2))) <= {'UNKNOWN', 'OBSERVED'}
    sim = simulator(path, operation)
    try:
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0] == 1
    finally:
        sim.close()


@pytest.mark.parametrize('presenter', ['missing', 'different_customer', 'different_swap', 'correct'])
def test_foreign_object_requires_matching_recorded_presenter(tmp_path, presenter):
    operation = task('RETURN_FOREIGN_OBJECT')
    sim = simulator(tmp_path/'foreign.sqlite3', operation)
    try:
        if presenter != 'missing':
            sim.conn.execute('INSERT INTO service_presenters VALUES (?,?,?)', (
                operation['expected_serial'], str(uuid4()) if presenter == 'different_customer' else operation['customer_id'],
                str(uuid4()) if presenter == 'different_swap' else operation['swap_id']))
            sim.conn.commit()
        expected = 'OBSERVED' if presenter == 'correct' else 'UNKNOWN'
        assert perform(sim, operation, technician_token='fixture-token') == expected
        entry = sim.conn.execute('SELECT * FROM service_operations').fetchone()
        assert entry['effects'] == (1 if presenter == 'correct' else 0)
        slot = next(s for s in sim.slots() if s['compartment_id'] == operation['return_compartment_id'])
        assert slot['present'] is (presenter != 'correct')
    finally:
        sim.close()


def test_lost_observation_response_replays_same_receipt_not_service_effect(tmp_path):
    from simulators.device.service import flush
    operation = task()
    path = tmp_path/'response-loss.sqlite3'
    sim = simulator(path, operation)
    received = []
    try:
        assert perform(sim, operation, technician_token='fixture-token') == 'OBSERVED'
        def lose_response(request):
            received.append(json.loads(request.content))
            raise httpx.ReadTimeout('fixture lost response', request=request)
        sim.http.close()
        sim.http = httpx.Client(base_url='http://fixture', transport=httpx.MockTransport(lose_response))
        with pytest.raises(httpx.ReadTimeout):
            flush(sim)
        assert sim.conn.execute('SELECT sent FROM service_operations').fetchone()[0] == 0
    finally:
        sim.close()
    sim = simulator(path, operation)
    try:
        def accept(request):
            received.append(json.loads(request.content))
            return httpx.Response(202, json={'accepted': True, 'duplicate': True})
        sim.http.close()
        sim.http = httpx.Client(base_url='http://fixture', transport=httpx.MockTransport(accept))
        flush(sim)
        assert received[0] == received[1]
        entry = sim.conn.execute('SELECT * FROM service_operations').fetchone()
        assert entry['sent'] == 1 and entry['effects'] == 1
    finally:
        sim.close()
