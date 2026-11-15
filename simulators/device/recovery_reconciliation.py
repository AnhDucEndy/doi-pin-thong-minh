"""ER-01/ER-02: read-only reconciliation and permanent no-effect interlocks.

Local closure is NOT fence release. Only an authenticated Backend committed
receipt releases exclusivity; permanent deny records survive that release.
"""
from datetime import datetime, timezone
import json
from uuid import uuid4

from app.domain.recovery import canonical_hash
from app.seed import demo_id
from simulators.device import recovery_fence as f


def initialize(conn):
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS recovery_effect_witness (
        operation_id TEXT PRIMARY KEY, inspection_event TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('NEVER_PREPARED','PREPARED','DISABLED')));
      CREATE TABLE IF NOT EXISTS recovery_denied_effects (
        kind TEXT NOT NULL, identity TEXT NOT NULL, closure_id TEXT NOT NULL,
        PRIMARY KEY(kind,identity));
      CREATE TABLE IF NOT EXISTS recovery_closure_outbox (
        closure_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL, packet TEXT NOT NULL, committed INTEGER NOT NULL DEFAULT 0);
    ''')
    conn.commit()


def deny_guard(conn, kind, identity):
    if conn.execute('SELECT 1 FROM recovery_denied_effects WHERE kind=? AND identity=?',
                    (kind, str(identity))).fetchone():
        raise RuntimeError('RECOVERY_EFFECT_PERMANENTLY_DISABLED')


def authenticate(sim, task):
    if (task.get('protocol_version') != '0.2' or task.get('effect_allowed') is not False
            or task.get('station_id') != str(demo_id(sim.code))):
        raise ValueError('RECOVERY_CONTEXT_CONFLICT')
    response = sim.http.get('/v1/device/recovery-tasks')
    response.raise_for_status()
    if task not in response.json()['items']:
        raise ValueError('SERVICE_TASK_NOT_AUTHORIZED')


def latest_snapshot(sim):
    rows = sim.conn.execute('SELECT body FROM events ORDER BY rowid DESC').fetchall()
    packet = next((p for p in map(lambda r: json.loads(r[0]), rows)
                   if p['kind'] == 'SNAPSHOT' and p['boot_id'] == sim.boot), None)
    if not packet:
        raise RuntimeError('RECOVERY_SNAPSHOT_REQUIRED')
    return packet


def close_no_effect(sim, task):
    authenticate(sim, task)
    if task['task_kind'] != 'CLOSE_NO_EFFECT' or canonical_hash(task['payload']) != task['payload_hash']:
        raise ValueError('RECOVERY_CLOSURE_INVALID')
    conn = sim.conn
    conn.execute('BEGIN IMMEDIATE')
    try:
        prior = conn.execute('SELECT * FROM recovery_closure_outbox WHERE closure_id=?',
                             (task['closure_id'],)).fetchone()
        if prior:
            if prior['request_hash'] != task['payload_hash']:
                raise ValueError('RECOVERY_CONTEXT_CONFLICT')
            conn.rollback()
            return json.loads(prior['packet'])
        fence = f.active(conn)
        ledger = conn.execute('SELECT ledger_id FROM recovery_local_identity').fetchone()[0]
        p = task['payload']
        if (not fence or fence['operation_id'] != task['operation_id']
                or fence['context_hash'] != task['context_hash'] or ledger != p['ledger_id']
                or fence['generation'] != p['fence_generation']
                or p['operation_id'] != task['operation_id'] or p['context_hash'] != task['context_hash']):
            raise RuntimeError('RECOVERY_FENCE_CONFLICT')
        # Neither PREPARED nor a missing terminal receipt can be guessed away.
        if conn.execute('SELECT 1 FROM recovery_action_ledger').fetchone() or conn.execute('SELECT 1 FROM service_operations').fetchone():
            raise RuntimeError('RECONCILIATION_REQUIRED')
        entries = [dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')]
        initial = json.loads(fence['inspection'])
        slot = json.loads(conn.execute('SELECT body FROM slots WHERE id=?',
                          (initial['slot']['compartment_id'],)).fetchone()[0])
        if (slot != initial['slot'] or not slot['present'] or slot['observed_serial'] != initial['actual_serial']
                or conn.execute('SELECT 1 FROM service_positions WHERE serial=?',(slot['observed_serial'],)).fetchone()):
            raise RuntimeError('RECONCILIATION_REQUIRED')
        changed = conn.execute("""UPDATE recovery_effect_witness SET state='DISABLED'
            WHERE operation_id=? AND inspection_event=? AND state='NEVER_PREPARED'""",
            (task['operation_id'],initial['event_id']))
        if changed.rowcount != 1:
            raise RuntimeError('RECOVERY_NO_EFFECT_UNPROVEN')
        if (sorted(e['id'] for e in entries) != sorted(p['command_ids'])
                or any((e['status'], e['effects']) not in (('EXECUTED', 1), ('NOT_EXECUTED', 0)) for e in entries)):
            raise RuntimeError('RECONCILIATION_REQUIRED')
        # Absence alone is not the proof: block every permitted writer under its
        # same local lock, retain a permanent permit and exact command deny set.
        conn.execute('INSERT INTO recovery_denied_effects VALUES (?,?,?)',
                     ('OPERATION', task['operation_id'], task['closure_id']))
        for entry in entries:
            conn.execute('INSERT OR IGNORE INTO recovery_denied_effects VALUES (?,?,?)',
                         ('COMMAND', entry['id'], task['closure_id']))
        snapshot = latest_snapshot(sim)
        packet = {'protocol_version':'0.2', 'message_kind':'NO_EFFECT_CLOSURE',
            'event_id':str(uuid4()), 'closure_id':task['closure_id'], 'closure_hash':task['payload_hash'],
            'operation_id':task['operation_id'], 'context_hash':task['context_hash'],
            'boot_id':sim.boot, 'seq':f.next_sequence(conn), 'observed_at':datetime.now(timezone.utc).isoformat(),
            'ledger_id':ledger, 'fence_generation':fence['generation'], 'snapshot_event_id':snapshot['event_id'],
            'command_entries':entries, 'service_entries':[], 'denied_command_ids':sorted(p['command_ids']),
            'inspection_event_id':initial['event_id'], 'prior_effect_state':'NEVER_PREPARED',
            'actual_slot':slot, 'permit_disabled':True, 'effect_count_delta':0, 'simulation_only':True}
        conn.execute('INSERT INTO recovery_closure_outbox(closure_id,operation_id,request_hash,packet) VALUES (?,?,?,?)',
                     (task['closure_id'], task['operation_id'], task['payload_hash'], json.dumps(packet)))
        conn.commit()
        return packet
    except BaseException:
        conn.rollback()
        raise


def acknowledge_closure(sim, task):
    authenticate(sim, task)
    if task['task_kind'] != 'CLOSURE_COMMITTED':
        raise ValueError('RECOVERY_CLOSURE_INVALID')
    conn = sim.conn
    conn.execute('BEGIN IMMEDIATE')
    try:
        row = conn.execute('SELECT * FROM recovery_closure_outbox WHERE closure_id=?', (task['closure_id'],)).fetchone()
        from app.api.recovery_schemas import NoEffectClosure
        if (not row or row['request_hash'] != task['payload_hash'] or row['operation_id'] != task['operation_id']
                or canonical_hash(NoEffectClosure.model_validate_json(row['packet']).model_dump(mode='json')) != task['receipt_hash']):
            raise ValueError('RECOVERY_CLOSURE_INVALID')
        # Deny history is never deleted when station exclusivity is released.
        deny_guard_present = conn.execute("SELECT 1 FROM recovery_denied_effects WHERE kind='OPERATION' AND identity=?",
                                          (task['operation_id'],)).fetchone()
        if not deny_guard_present:
            raise RuntimeError('RECOVERY_CLOSURE_INVALID')
        packet = json.loads(row['packet'])
        witness = conn.execute('SELECT state FROM recovery_effect_witness WHERE operation_id=?',
                               (task['operation_id'],)).fetchone()
        protected = {r[0] for r in conn.execute("SELECT identity FROM recovery_denied_effects WHERE kind='COMMAND'")}
        if (not witness or witness['state']!='DISABLED' or not set(packet['denied_command_ids'])<=protected
                or (not row['committed'] and (
                    [dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')]!=packet['command_entries']
                    or conn.execute('SELECT 1 FROM service_operations').fetchone()
                    or conn.execute('SELECT 1 FROM recovery_action_ledger').fetchone()))):
            raise RuntimeError('RECOVERY_FENCE_CONFLICT')
        conn.execute("UPDATE recovery_station_fence SET state='CLOSED' WHERE operation_id=? AND context_hash=?",
                     (task['operation_id'], task['context_hash']))
        conn.execute('UPDATE recovery_closure_outbox SET committed=1 WHERE closure_id=?', (task['closure_id'],))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def reinspect(sim, task):
    authenticate(sim, task)
    if task['task_kind'] != 'RECONCILE_INSPECT' or not task.get('reconciliation_only'):
        raise ValueError('RECOVERY_INSPECTION_TASK_REQUIRED')
    conn = sim.conn
    # Deliver the immutable original effect receipt first if transport was lost.
    # Verify its stored source snapshot using the normal device inbox, outside
    # the model writer transaction. Never re-emit a physical observation.
    pending = conn.execute('SELECT observation,sent FROM service_operations WHERE id=? AND state=?',
                           (task['predecessor_id'],'OBSERVED')).fetchone()
    if pending and not pending['sent']:
        original = json.loads(pending['observation'])
        root = conn.execute('SELECT body FROM events WHERE id=?',(original['snapshot_event_id'],)).fetchone()
        if not root:
            raise RuntimeError('RECOVERY_SNAPSHOT_REQUIRED')
        state = sim.http.post('/v1/device/events',json=json.loads(root[0]))
        if state.status_code!=202 or state.json().get('processing_state')!='PROCESSED':
            raise RuntimeError('RECOVERY_SNAPSHOT_REQUIRED')
        stored = sim.http.post('/v1/device/recovery-observations',json=original)
        stored.raise_for_status()
        conn.execute('UPDATE service_operations SET sent=1 WHERE id=?',(task['predecessor_id'],))
        conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        prior = conn.execute('SELECT packet FROM recovery_inspection_outbox WHERE operation_id=?', (task['operation_id'],)).fetchone()
        if prior:
            packet = json.loads(prior[0])
            if packet['context_hash'] != task['context_hash']:
                raise ValueError('RECOVERY_CONTEXT_CONFLICT')
            conn.rollback()
            return packet
        fence = f.active(conn)
        if (not fence or fence['operation_id'] != task['predecessor_id']
                or fence['context_hash'] != task['predecessor_context_hash']
                or datetime.fromisoformat(task['expires_at']) <= datetime.now(timezone.utc)):
            raise RuntimeError('RECOVERY_FENCE_CONFLICT')
        slot = json.loads(conn.execute('SELECT body FROM slots WHERE id=?', (task['return_compartment_id'],)).fetchone()[0])
        service = conn.execute('SELECT * FROM service_operations WHERE id=?', (task['predecessor_id'],)).fetchone()
        historical = json.loads(service['observation']) if service and service['state']=='OBSERVED' and service['observation'] else None
        action = conn.execute('SELECT * FROM recovery_action_ledger WHERE operation_id=?',(task['predecessor_id'],)).fetchone()
        if historical and (not action or action['state']!='OBSERVED' or json.loads(action['entry'])!=historical['service_entry']
                or historical['authorization_id']!=task['predecessor_authorization_id']
                or historical['authorization_hash']!=task['predecessor_authorization_hash']):
            raise RuntimeError('RECOVERY_LEDGER_CHANGED')
        # Actual serial is discovered from the durable effect and external model;
        # expected_serial is only a later comparison, never an observation source.
        actual = historical['actual_serial'] if historical else None
        position = conn.execute('SELECT * FROM service_positions WHERE serial=?', (actual,)).fetchone()
        presenter = conn.execute('SELECT * FROM service_presenters WHERE serial=?', (actual,)).fetchone()
        snapshot = latest_snapshot(sim)
        packet = {'protocol_version':'0.2', 'stage':'RECONCILIATION_INSPECTION',
            'event_id':str(uuid4()), 'operation_id':task['operation_id'], 'context_hash':task['context_hash'],
            'predecessor_id':task['predecessor_id'], 'predecessor_context_hash':task['predecessor_context_hash'],
            'boot_id':sim.boot, 'seq':f.next_sequence(conn), 'observed_at':datetime.now(timezone.utc).isoformat(),
            'ledger_id':conn.execute('SELECT ledger_id FROM recovery_local_identity').fetchone()[0],
            'fence_generation':fence['generation'], 'actual_serial':actual if position else None,
            'recipient_id':position['customer_id'] if position else None,
            'historical_receipt':historical, 'slot':slot, 'presenter':dict(presenter) if presenter else None,
            'command_entries':[dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')],
            'service_entries':[dict(r) for r in conn.execute('SELECT * FROM service_operations ORDER BY id')],
            'snapshot_event_id':snapshot['event_id'], 'wrong_return_event_ids':[],
            'result':'OBSERVED' if position and historical else 'UNKNOWN', 'read_only':True,
            'effect_count_delta':0, 'simulation_only':True}
        conn.execute('INSERT INTO recovery_inspection_outbox(operation_id,packet) VALUES (?,?)',
                     (task['operation_id'],json.dumps(packet)))
        conn.commit()
        return packet
    except BaseException:
        conn.rollback()
        raise
