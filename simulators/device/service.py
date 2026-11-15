"""Explicit, operation-scoped service actions in the existing simulator ledger.

Polling never calls perform(). UNKNOWN is never retried as a physical effect.
All observations read model state; expected_serial is used only as an interlock.
"""
from datetime import datetime, timezone
import json
from uuid import uuid4

from app.seed import demo_id


def initialize(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS service_positions(serial TEXT PRIMARY KEY, customer_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS service_presenters(serial TEXT PRIMARY KEY, customer_id TEXT NOT NULL, swap_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS service_operations(id TEXT PRIMARY KEY, context_hash TEXT NOT NULL,
      state TEXT NOT NULL, effects INTEGER NOT NULL DEFAULT 0, observation TEXT, sent INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS service_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    if not conn.execute("SELECT 1 FROM service_metadata WHERE key='initialized'").fetchone():
        # Seed only a new physical model, never reconstruct possession from a
        # legacy ledger that may already have transferred this pin.
        if not conn.execute('SELECT 1 FROM commands LIMIT 1').fetchone() and not conn.execute('SELECT 1 FROM events LIMIT 1').fetchone():
            conn.execute('INSERT OR IGNORE INTO service_positions VALUES (?,?)', ('CUSTOMER-B001', str(demo_id('customer'))))
        conn.execute("INSERT INTO service_metadata VALUES ('initialized','1')")
        conn.commit()


def command_effect(conn, command):
    """Called in the same commit as the simulator's completed command effect."""
    customer = command['payload'].get('customer_id')
    if not customer:
        return  # Legacy command cannot invent an external holder.
    serial = command['payload']['expected_serial']
    if command['kind'] == 'OPEN_RETURN':
        row = conn.execute('SELECT body FROM slots WHERE id=?', (command['compartment_id'],)).fetchone()
        actual = json.loads(row['body'])['observed_serial'] if row else None
        if actual:
            conn.execute('INSERT INTO service_presenters VALUES (?,?,?) ON CONFLICT(serial) DO UPDATE SET customer_id=excluded.customer_id,swap_id=excluded.swap_id',
                         (actual, customer, command['swap_id']))
        if actual == serial:
            conn.execute('DELETE FROM service_positions WHERE serial=? AND customer_id=?', (serial, customer))
    else:
        conn.execute('INSERT INTO service_positions VALUES (?,?) ON CONFLICT(serial) DO UPDATE SET customer_id=excluded.customer_id',
                     (serial, customer))


def perform(simulator, task, *, technician_token, crash_after_prepared=False):
    if task.get('task_kind') in ('RECONCILE_INSPECT', 'CLOSE_NO_EFFECT', 'CLOSURE_COMMITTED'):
        from simulators.device import recovery_reconciliation as reconciliation
        handler = {'RECONCILE_INSPECT':reconciliation.reinspect,
                   'CLOSE_NO_EFFECT':reconciliation.close_no_effect,
                   'CLOSURE_COMMITTED':reconciliation.acknowledge_closure}[task['task_kind']]
        handler(simulator, task)
        return task['task_kind']
    """Deliberate Technician invocation, never a cycle/poll side effect."""
    sim, conn = simulator, simulator.conn
    if task.get('protocol_version') == '0.2':
        if task.get('task_kind') == 'ACTION':
            from simulators.device.recovery_handover import perform as handover
            return handover(sim, task, technician_token=technician_token, crash_after_prepared=crash_after_prepared)
        # Staged tasks exposed in this increment only permit read-only inspection.
        from simulators.device.recovery_fence import transport_inspection, acknowledge_authorization
        fresh = sim.http.get('/v1/device/recovery-tasks')
        fresh.raise_for_status()
        if task not in fresh.json()['items']:
            raise ValueError('SERVICE_TASK_NOT_AUTHORIZED')
        if task.get('task_kind') == 'AUTHORIZATION_INTENT':
            acknowledge_authorization(sim, task)
            return 'AUTHORIZATION_STORED_NO_EFFECT'
        transport_inspection(sim, task)
        return 'INSPECTED'
    initialize(conn)
    identity = str(task['operation_id'])
    # Re-authorize both human and device immediately before preparing an effect.
    response = sim.http.get(f"/v1/swaps/{task['swap_id']}/recovery",
        headers={'Authorization': 'Bearer ' + technician_token})
    response.raise_for_status()
    case = response.json()
    operation = case.get('active_operation')
    if not operation or str(operation['id']) != identity or operation['context_hash'] != task['context_hash']:
        raise ValueError('SERVICE_CONTEXT_CHANGED')
    # Admin can read but cannot supply a Technician attestation. Verify /me as
    # the separate human principal; never treat Device-Key as a user credential.
    actor = sim.http.get('/v1/me', headers={'Authorization': 'Bearer ' + technician_token})
    actor.raise_for_status()
    user = actor.json()
    if user['role'] != 'TECHNICIAN' or user['id'] != operation['created_by']:
        raise ValueError('SERVICE_TECHNICIAN_REQUIRED')
    fresh = sim.http.get('/v1/device/recovery-tasks')
    fresh.raise_for_status()
    if task not in fresh.json()['items']:
        raise ValueError('SERVICE_TASK_NOT_AUTHORIZED')
    if datetime.fromisoformat(task['expires_at'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
        raise ValueError('SERVICE_TASK_EXPIRED')
    conn.execute('BEGIN IMMEDIATE')
    prior = conn.execute('SELECT * FROM service_operations WHERE id=?', (identity,)).fetchone()
    if prior:
        conn.rollback()
        if prior['context_hash'] != task['context_hash']:
            raise ValueError('SERVICE_CONTEXT_CONFLICT')
        return prior['state']  # Replay never produces a second effect.
    conn.execute('INSERT INTO service_operations(id,context_hash,state) VALUES (?,?,?)',
                 (identity, task['context_hash'], 'UNKNOWN'))
    conn.commit()  # Durable uncertainty BEFORE any external model effect.
    if crash_after_prepared:
        raise RuntimeError('SIMULATED_SERVICE_CRASH_AFTER_PREPARED')
    conn.execute('BEGIN IMMEDIATE')
    try:
        from simulators.device.recovery_fence import require_unfenced
        # Legacy actions cannot cross a staged recovery fence. Read-only model
        # inspections stay allowed; they cannot authorize or clear this fence.
        if task['purpose'] in ('RETURN_OLD_TO_CUSTOMER', 'RETURN_FOREIGN_OBJECT'):
            require_unfenced(conn)
            from simulators.device.recovery_reconciliation import deny_guard
            deny_guard(conn, 'OPERATION', task['operation_id'])
        purpose = task['purpose']
        observed, effects, result = None, 0, 'UNKNOWN'
        customer = task['customer_id']
        if purpose in ('RETURN_OLD_TO_CUSTOMER', 'RETURN_FOREIGN_OBJECT'):
            row = conn.execute('SELECT body FROM slots WHERE id=?', (task['return_compartment_id'],)).fetchone()
            slot = json.loads(row['body']) if row else None
            presenter = conn.execute('SELECT 1 FROM service_presenters WHERE serial=? AND customer_id=? AND swap_id=?',
                                     (task['expected_serial'], customer, task['swap_id'])).fetchone()
            if (slot and slot['door_state'] == 'CLOSED' and slot['present'] and slot['observed_serial'] == task['expected_serial']
                    and (purpose != 'RETURN_FOREIGN_OBJECT' or presenter)):
                observed = slot['observed_serial']
                # Existing model's serial is the observation, not the task's
                # expected value. The scoped service action does not emit a
                # fabricated DOOR/ACK or mark any command OBSERVED.
                slot.update(present=False, observed_serial=None, battery_id=None)
                conn.execute('UPDATE slots SET body=? WHERE id=?', (json.dumps(slot), slot['compartment_id']))
                conn.execute('INSERT INTO service_positions VALUES (?,?) ON CONFLICT(serial) DO UPDATE SET customer_id=excluded.customer_id', (observed, customer))
                effects, result = 1, 'OBSERVED'
        elif purpose in ('VERIFY_OLD_POSSESSION', 'VERIFY_NEW_DELIVERY'):
            row = conn.execute('SELECT serial FROM service_positions WHERE customer_id=? AND serial=?',
                               (customer, task['expected_serial'])).fetchone()
            if row:
                observed, result = row['serial'], 'OBSERVED'
        elif purpose == 'RESUME_SWAP':
            row = conn.execute('SELECT serial FROM service_positions WHERE customer_id=? AND serial=?',
                               (customer, task['expected_serial'])).fetchone()
            slot = next((s for s in sim.slots() if s['compartment_id'] == task['return_compartment_id']), None)
            observed = row['serial'] if row else slot['observed_serial'] if slot and slot['present'] else None
            if observed == task['expected_serial']:
                result = 'OBSERVED'
        from simulators.device.recovery_fence import next_sequence
        seq = next_sequence(conn)
        body = {'event_id': str(uuid4()), 'operation_id': identity, 'context_hash': task['context_hash'],
            'boot_id': sim.boot, 'seq': seq, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'observation': {'result': result, 'actual_serial': observed,
                'supporting_event_ids': [], 'simulation_only': True}}
        conn.execute('UPDATE service_operations SET state=?,effects=?,observation=? WHERE id=?',
                     (result, effects, json.dumps(body), identity))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return result


def flush(simulator):
    """Replay only durable observations; never run physical service here."""
    initialize(simulator.conn)
    from simulators.device.recovery_fence import flush as flush_inspections
    flush_inspections(simulator)
    from simulators.device.recovery_reconciliation import acknowledge_closure
    for row in simulator.conn.execute('SELECT * FROM recovery_closure_outbox WHERE committed=0').fetchall():
        result = simulator.http.post('/v1/device/recovery-observations',json=json.loads(row['packet']))
        if result.status_code==202:
            response = simulator.http.get('/v1/device/recovery-tasks')
            response.raise_for_status()
            task = next((t for t in response.json()['items'] if t.get('task_kind')=='CLOSURE_COMMITTED'
                         and t['closure_id']==row['closure_id']),None)
            if task:
                acknowledge_closure(simulator,task)
    for row in simulator.conn.execute('SELECT * FROM service_operations WHERE observation IS NOT NULL AND sent=0').fetchall():
        packet = json.loads(row['observation'])
        if packet.get('stage') == 'POST_ACTION_RECEIPT':
            # Wait for the worker to accept the actual source snapshot. Never
            # submit a premature semantic refusal and then rewrite its event ID.
            source = simulator.conn.execute('SELECT body FROM events WHERE id=?', (packet['snapshot_event_id'],)).fetchone()
            receipt = simulator.http.post('/v1/device/events', json=json.loads(source['body']))
            if receipt.status_code != 202 or receipt.json().get('processing_state') != 'PROCESSED':
                continue
        response = simulator.http.post('/v1/device/recovery-observations', json=packet)
        if response.status_code == 202:
            simulator.conn.execute('UPDATE service_operations SET sent=1 WHERE id=?', (row['id'],))
            simulator.conn.commit()
