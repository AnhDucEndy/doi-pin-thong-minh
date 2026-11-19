"""P8-REC-0.2 local inspection fence; never grants permission to move an object.

The fence and command/service effects use the SAME SQLite writer lock. A fence
survives restart and expiry; neither wall time nor a new boot clears uncertainty.
Only the staged protocol may eventually close it after reconciliation.
"""
from datetime import datetime, timezone
import json
from uuid import uuid4


def initialize(conn):
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS recovery_local_identity (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), ledger_id TEXT NOT NULL UNIQUE);
      CREATE TABLE IF NOT EXISTS recovery_station_fence (
        generation INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL UNIQUE,
        context_hash TEXT NOT NULL, boot_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('ACTIVE','CLOSED')),
        inspection TEXT NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS recovery_one_station_fence
        ON recovery_station_fence(state) WHERE state='ACTIVE';
      CREATE TABLE IF NOT EXISTS recovery_inspection_outbox (
        operation_id TEXT PRIMARY KEY, packet TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS recovery_authorization_outbox (
        authorization_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE,
        authorization_hash TEXT NOT NULL, packet TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
    ''')
    conn.execute('INSERT OR IGNORE INTO recovery_local_identity VALUES (1,?)', (str(uuid4()),))
    conn.commit()


def active(conn):
    return conn.execute("SELECT * FROM recovery_station_fence WHERE state='ACTIVE'").fetchone()


def require_unfenced(conn):
    """Caller must hold BEGIN IMMEDIATE until its complete physical effect commits."""
    if not conn.in_transaction:
        raise RuntimeError('RECOVERY_EFFECT_REQUIRES_TRANSACTION')
    if active(conn):
        raise RuntimeError('RECOVERY_STATION_FENCED')


def inspect(sim, task):
    """Internal adapter primitive, not an API authorization or a handover task.

    Persists actual model/ledger evidence while fencing all effect writers. The
    caller must authenticate the INSPECT task before invoking this primitive.
    Replaying an operation returns its ORIGINAL receipt, including boot/time.
    """
    conn = sim.conn
    if task.get('protocol_version') != '0.2' or task.get('task_kind') != 'INSPECT':
        raise ValueError('RECOVERY_INSPECTION_TASK_REQUIRED')
    if task.get('purpose') != 'RETURN_FOREIGN_OBJECT':
        raise ValueError('RECOVERY_INSPECTION_PURPOSE_INVALID')
    # Station scope comes from the simulator identity and its actual slot model.
    from app.seed import demo_id
    if task.get('station_id') != str(demo_id(sim.code)):
        raise ValueError('RECOVERY_INSPECTION_STATION_INVALID')
    identity = str(task['operation_id'])
    conn.execute('BEGIN IMMEDIATE')
    try:
        prior = conn.execute('SELECT * FROM recovery_station_fence WHERE operation_id=?', (identity,)).fetchone()
        if prior:
            if prior['context_hash'] != task['context_hash']:
                raise ValueError('RECOVERY_CONTEXT_CONFLICT')
            result = json.loads(prior['inspection'])
            conn.rollback()
            return result
        if active(conn):
            raise RuntimeError('RECOVERY_STATION_FENCED')
        if datetime.fromisoformat(task['expires_at'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
            raise ValueError('RECOVERY_INSPECTION_EXPIRED')
        slot_row = conn.execute('SELECT body FROM slots WHERE id=?', (task['return_compartment_id'],)).fetchone()
        if not slot_row:
            raise ValueError('RECOVERY_INSPECTION_SLOT_INVALID')
        slot = json.loads(slot_row['body'])
        actual = slot['observed_serial'] if slot['present'] else None
        presenter = conn.execute('SELECT * FROM service_presenters WHERE serial=?', (actual,)).fetchone()
        command_entries = [dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')]
        service_entries = [dict(r) for r in conn.execute('SELECT * FROM service_operations ORDER BY id')]
        events = [json.loads(r['body']) for r in conn.execute('SELECT body FROM events ORDER BY rowid')]
        # Include full original events, not a generated claim that EXECUTED means
        # delivery. Backend must authenticate/correlate this history separately.
        chain = [e for e in events if e.get('swap_id') == task['swap_id']
                 and e.get('compartment_id') == task['return_compartment_id']]
        ledger = conn.execute('SELECT ledger_id FROM recovery_local_identity WHERE singleton=1').fetchone()[0]
        cursor = conn.execute('''INSERT INTO recovery_station_fence
          (operation_id,context_hash,boot_id,state,inspection) VALUES (?,?,?,'ACTIVE','{}')''',
          (identity, task['context_hash'], sim.boot))
        receipt = {'event_id': str(uuid4()), 'operation_id': identity,
            'protocol_version': '0.2', 'stage': 'PRE_ACTION_INSPECTION',
            'context_hash': task['context_hash'], 'boot_id': sim.boot,
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'ledger_id': ledger, 'fence_generation': cursor.lastrowid,
            'actual_serial': actual, 'slot': slot, 'presenter': dict(presenter) if presenter else None,
            'command_entries': command_entries, 'service_entries': service_entries,
            'wrong_return_events': chain, 'read_only': True, 'effect_count_delta': 0,
            'simulation_only': True}
        conn.execute('UPDATE recovery_station_fence SET inspection=? WHERE generation=?',
                     (json.dumps(receipt, sort_keys=True), cursor.lastrowid))
        conn.execute("INSERT INTO recovery_effect_witness VALUES (?,?,'NEVER_PREPARED')",
                     (identity,receipt['event_id']))
        conn.commit()
        return receipt
    except BaseException:
        conn.rollback()
        raise


def next_sequence(conn):
    prior = conn.execute("SELECT value FROM service_metadata WHERE key='receipt_sequence'").fetchone()
    count = conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]
    value = max(int(prior[0]) if prior else 0, count) + 1
    conn.execute("INSERT INTO service_metadata VALUES ('receipt_sequence',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
    return value


def transport_inspection(sim, task):
    """Caller gets tasks from the authenticated device endpoint; never a handover."""
    import hashlib
    receipt = inspect(sim, task)
    conn = sim.conn
    conn.execute('BEGIN IMMEDIATE')
    try:
        prior = conn.execute('SELECT packet FROM recovery_inspection_outbox WHERE operation_id=?', (task['operation_id'],)).fetchone()
        if prior:
            conn.rollback()
            return json.loads(prior['packet'])
        # Original boot is preserved on replay; never recapture a receipt after restart.
        snapshots = [json.loads(r[0]) for r in conn.execute('SELECT body FROM events ORDER BY rowid DESC')]
        snapshot = next((e for e in snapshots if e['kind']=='SNAPSHOT' and e['boot_id']==receipt['boot_id']
                         and e['observed_at']<=receipt['observed_at']), None)
        if not snapshot:
            raise RuntimeError('RECOVERY_SNAPSHOT_REQUIRED')
        packet = {k:v for k,v in receipt.items() if k!='wrong_return_events'}
        packet.update(seq=next_sequence(conn), snapshot_event_id=snapshot['event_id'],
            wrong_return_event_ids=[e['event_id'] for e in receipt['wrong_return_events']],
            result='OBSERVED' if receipt['actual_serial'] is not None else 'UNKNOWN')
        conn.execute('INSERT INTO recovery_inspection_outbox(operation_id,packet) VALUES (?,?)',
                     (task['operation_id'],json.dumps(packet)))
        conn.commit()
        return packet
    except BaseException:
        conn.rollback()
        raise


def flush(sim):
    for row in sim.conn.execute('SELECT * FROM recovery_inspection_outbox WHERE sent=0').fetchall():
        response = sim.http.post('/v1/device/recovery-observations',json=json.loads(row['packet']))
        if response.status_code==202:
            sim.conn.execute('UPDATE recovery_inspection_outbox SET sent=1 WHERE operation_id=?',(row['operation_id'],))
            sim.conn.commit()
    fence = active(sim.conn)
    if fence and json.loads(fence['inspection']).get('protocol_version') != '0.3' and not sim.conn.execute('SELECT 1 FROM recovery_authorization_outbox WHERE operation_id=?',
                                      (fence['operation_id'],)).fetchone():
        tasks = sim.http.get('/v1/device/recovery-tasks')
        tasks.raise_for_status()
        for task in tasks.json()['items']:
            if task['operation_id']==fence['operation_id'] and task.get('task_kind')=='AUTHORIZATION_INTENT':
                acknowledge_authorization(sim, task)
    for row in sim.conn.execute('SELECT * FROM recovery_authorization_outbox WHERE sent=0').fetchall():
        response = sim.http.post('/v1/device/recovery-observations',json=json.loads(row['packet']))
        if response.status_code == 202:
            sim.conn.execute('UPDATE recovery_authorization_outbox SET sent=1 WHERE authorization_id=?',(row['authorization_id'],))
            sim.conn.commit()


def acknowledge_authorization(sim, task):
    """Persist receipt of an intent, NEVER PREPARED or an actuator effect.

    Caller must first authenticate/re-fetch the exact task. The local fence is
    kept ACTIVE, including after expiration/reboot/rejection. Replay is immutable.
    """
    from app.domain.recovery import canonical_hash
    from app.seed import demo_id
    if (task.get('task_kind') != 'AUTHORIZATION_INTENT' or task.get('effect_allowed') is not False
            or task.get('station_id') != str(demo_id(sim.code))):
        raise ValueError('RECOVERY_INTENT_REQUIRED')
    payload = task['authorization_payload']
    if canonical_hash(payload) != task['authorization_hash'] or payload.get('effect_allowed') is not False:
        raise ValueError('RECOVERY_INTENT_HASH_INVALID')
    conn = sim.conn
    conn.execute('BEGIN IMMEDIATE')
    try:
        prior = conn.execute('SELECT * FROM recovery_authorization_outbox WHERE authorization_id=?',
                             (task['authorization_id'],)).fetchone()
        if prior:
            if prior['authorization_hash'] != task['authorization_hash']:
                raise ValueError('RECOVERY_INTENT_HASH_INVALID')
            conn.rollback()
            return json.loads(prior['packet'])
        fence = active(conn)
        ledger = conn.execute('SELECT ledger_id FROM recovery_local_identity WHERE singleton=1').fetchone()[0]
        if (not fence or fence['operation_id'] != task['operation_id'] or fence['context_hash'] != task['context_hash']
                or payload['operation_id'] != task['operation_id'] or payload['context_hash'] != task['context_hash']
                or payload['authorization_id'] != task['authorization_id'] or payload['boot_id'] != sim.boot
                or fence['boot_id'] != sim.boot or payload['ledger_id'] != ledger
                or payload['fence_generation'] != fence['generation']
                or datetime.fromisoformat(payload['expires_at']) <= datetime.now(timezone.utc)):
            raise RuntimeError('RECOVERY_FENCE_CONFLICT')
        entries = [dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')]
        slot = json.loads(conn.execute('SELECT body FROM slots WHERE id=?',(payload['source_compartment_id'],)).fetchone()[0])
        presenter = conn.execute('SELECT * FROM service_presenters WHERE serial=?',(payload['actual_serial'],)).fetchone()
        if (canonical_hash(entries) != payload['command_digest'] or conn.execute('SELECT count(*) FROM service_operations').fetchone()[0]
                or slot['door_state'] != 'CLOSED' or not slot['present'] or slot['lock_released']
                or slot['observed_serial'] != payload['actual_serial'] or not presenter
                or presenter['customer_id'] != payload['recipient_id'] or presenter['swap_id'] != task['swap_id']):
            raise RuntimeError('RECOVERY_MODEL_CHANGED')
        packet = {'protocol_version':'0.2','message_kind':'AUTHORIZATION_ACK','event_id':str(uuid4()),
            'authorization_id':task['authorization_id'],'authorization_hash':task['authorization_hash'],
            'operation_id':task['operation_id'],'context_hash':task['context_hash'],
            'boot_id':sim.boot,'ledger_id':ledger,'fence_generation':fence['generation'],
            'seq':next_sequence(conn),'observed_at':datetime.now(timezone.utc).isoformat(),
            'stored':True,'effect_count_delta':0,'simulation_only':True}
        conn.execute('INSERT INTO recovery_authorization_outbox(authorization_id,operation_id,authorization_hash,packet) VALUES (?,?,?,?)',
            (task['authorization_id'],task['operation_id'],task['authorization_hash'],json.dumps(packet)))
        conn.commit()
        return packet
    except BaseException:
        conn.rollback()
        raise
