"""Local durable fence regression; NOT PostgreSQL or API end-to-end proof."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from uuid import uuid4

import pytest

from app.application.identity import utcnow
from app.seed import demo_id
from simulators.device import recovery_fence
from simulators.device.service import perform
from test_phase8a_service import task, simulator


def inspection():
    return {**task('RETURN_FOREIGN_OBJECT'), 'protocol_version': '0.2',
            'task_kind': 'INSPECT', 'station_id': str(demo_id('S01'))}


def command():
    return {'id': str(uuid4()), 'device_id': str(demo_id('device:S01')),
        'swap_id': str(uuid4()), 'compartment_id': str(demo_id('S01:slot:1')),
        'kind': 'OPEN_RETURN', 'expires_at': (utcnow()+timedelta(seconds=15)).isoformat(),
        'payload': {'expected_serial': 'CUSTOMER-B001', 'expected_battery_id': str(demo_id('customer:battery')),
                    'customer_id': str(demo_id('customer')), 'simulation_only': True}}


def model(conn):
    return {table: [tuple(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]
            for table in ('slots', 'commands', 'events', 'service_positions', 'service_presenters', 'service_operations')}


def test_inspection_reads_actual_model_without_effect_or_expected_echo(tmp_path):
    op = inspection()
    op['expected_serial'] = 'EXPECTED-IS-NOT-AN-OBSERVATION'
    sim = simulator(tmp_path/'inspect.sqlite3', op)
    try:
        before = model(sim.conn)
        receipt = recovery_fence.inspect(sim, op)
        assert receipt['actual_serial'] == 'S01-B002'
        assert receipt['presenter'] is None  # Never fill a missing presenter from task.customer_id.
        assert receipt['stage'] == 'PRE_ACTION_INSPECTION'
        assert receipt['read_only'] and receipt['effect_count_delta'] == 0
        assert model(sim.conn) == before
        assert recovery_fence.active(sim.conn)['operation_id'] == op['operation_id']
    finally:
        sim.close()


def test_inspection_replay_after_restart_keeps_original_boot_time_and_identity(tmp_path):
    op = inspection()
    path = tmp_path/'replay.sqlite3'
    sim = simulator(path, op)
    first = recovery_fence.inspect(sim, op)
    sim.close()
    sim = simulator(path, op)
    try:
        assert sim.boot != first['boot_id']
        assert recovery_fence.inspect(sim, op) == first
        assert sim.conn.execute('SELECT count(*) FROM recovery_station_fence').fetchone()[0] == 1
        assert sim.conn.execute('SELECT ledger_id FROM recovery_local_identity').fetchone()[0] == first['ledger_id']
    finally:
        sim.close()


def test_already_received_command_cannot_execute_after_inspection(tmp_path):
    op, cached = inspection(), command()  # Downloaded before inspection.
    sim = simulator(tmp_path/'cached.sqlite3', op)
    sim.scenario = 'physical'
    try:
        before = sim.slots()
        recovery_fence.inspect(sim, op)
        with pytest.raises(RuntimeError, match='STATION_FENCED'):
            sim.handle(cached)
        assert sim.slots() == before
        row = sim.conn.execute('SELECT status,effects FROM commands').fetchone()
        assert tuple(row) == ('UNKNOWN', 0)
        assert sim.handle(cached) == 'UNKNOWN'
        assert sim.slots() == before
        assert not sim.conn.in_transaction
    finally:
        sim.close()


def test_fence_blocks_legacy_handover_and_unknown_is_not_retried(tmp_path):
    op = inspection()
    legacy = {k:v for k,v in op.items() if k not in ('protocol_version','task_kind')}
    path = tmp_path/'legacy.sqlite3'
    sim = simulator(path, legacy)
    try:
        recovery_fence.inspect(sim, op)
        before = sim.slots()
        with pytest.raises(RuntimeError, match='STATION_FENCED'):
            perform(sim, legacy, technician_token='fixture-token')
        assert perform(sim, legacy, technician_token='fixture-token') == 'UNKNOWN'
        assert sim.slots() == before
        assert sim.conn.execute('SELECT sum(effects) FROM service_operations').fetchone()[0] == 0
    finally:
        sim.close()


@pytest.mark.parametrize('field,value,error', [
    ('protocol_version', 'P8-REC-0.1', 'TASK_REQUIRED'),
    ('task_kind', 'ACTION', 'TASK_REQUIRED'),
    ('purpose', 'VERIFY_NEW_DELIVERY', 'PURPOSE_INVALID'),
    ('station_id', str(demo_id('S02')), 'STATION_INVALID'),
    ('return_compartment_id', str(demo_id('S02:slot:1')), 'SLOT_INVALID'),
])
def test_invalid_inspection_cannot_install_fence(tmp_path, field, value, error):
    op = inspection()
    sim = simulator(tmp_path/'invalid.sqlite3', op)
    try:
        before = model(sim.conn)
        with pytest.raises(ValueError, match=error):
            recovery_fence.inspect(sim, {**op, field: value})
        assert recovery_fence.active(sim.conn) is None
        assert model(sim.conn) == before
        assert not sim.conn.in_transaction
    finally:
        sim.close()


def test_expired_inspection_and_context_conflict_do_not_replace_evidence(tmp_path):
    op = inspection()
    sim = simulator(tmp_path/'expiry.sqlite3', op)
    try:
        with pytest.raises(ValueError, match='EXPIRED'):
            recovery_fence.inspect(sim, {**op, 'expires_at': (utcnow()-timedelta(seconds=1)).isoformat()})
        first = recovery_fence.inspect(sim, op)
        with pytest.raises(ValueError, match='CONTEXT_CONFLICT'):
            recovery_fence.inspect(sim, {**op, 'context_hash': 'b'*64})
        assert recovery_fence.inspect(sim, op) == first
    finally:
        sim.close()


def test_inspection_preserves_executed_and_unknown_history_without_delivery_claim(tmp_path):
    op = inspection()
    sim = simulator(tmp_path/'history.sqlite3', op)
    try:
        sim.scenario = 'wrong-return'
        returned = command()
        assert sim.handle(returned) == 'EXECUTED'
        sim.scenario = 'crash-after-ledger'
        uncertain = command()
        with pytest.raises(RuntimeError, match='CRASH_AFTER_DURABLE_LEDGER'):
            sim.handle(uncertain)
        op.update(swap_id=returned['swap_id'], return_compartment_id=returned['compartment_id'])
        before = model(sim.conn)
        receipt = recovery_fence.inspect(sim, op)
        assert {e['status'] for e in receipt['command_entries']} == {'EXECUTED', 'UNKNOWN'}
        assert receipt['actual_serial'] == 'SIMULATED-WRONG-BATTERY'
        assert receipt['presenter']['customer_id'] == returned['payload']['customer_id']
        assert receipt['wrong_return_events']
        assert 'new_pin_delivered' not in receipt and 'old_pin_settled' not in receipt
        assert model(sim.conn) == before
    finally:
        sim.close()


def test_two_connections_can_install_only_one_station_fence(tmp_path):
    op = inspection()
    path = tmp_path/'race.sqlite3'
    simulator(path, op).close()
    def run(_):
        own = {**op, 'operation_id': str(uuid4())}
        sim = simulator(path, own)
        try:
            try:
                recovery_fence.inspect(sim, own)
                return 'INSTALLED'
            except RuntimeError as exc:
                assert str(exc) == 'RECOVERY_STATION_FENCED'
                return 'BLOCKED'
        finally:
            sim.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == ['BLOCKED', 'INSTALLED']


def test_command_failure_rolls_back_model_events_and_retains_unknown(tmp_path):
    op = inspection()
    sim = simulator(tmp_path/'rollback.sqlite3', op)
    sim.scenario = 'physical'
    original = sim.emit
    def fail(kind, payload, **refs):
        if kind == 'PRESENCE':
            raise RuntimeError('INJECTED_EVENT_FAILURE')
        return original(kind, payload, **refs)
    sim.emit = fail
    try:
        slots = deepcopy(sim.slots())
        with pytest.raises(RuntimeError, match='INJECTED_EVENT_FAILURE'):
            sim.handle(command())
        assert sim.slots() == slots
        assert sim.conn.execute('SELECT count(*) FROM events').fetchone()[0] == 0
        assert tuple(sim.conn.execute('SELECT status,effects FROM commands').fetchone()) == ('UNKNOWN', 0)
    finally:
        sim.close()
