"""Explicit activated foreign-object service. Polling cannot invoke this effect."""
from datetime import datetime, timezone
import json
from uuid import uuid4
from app.domain.recovery import canonical_hash
from app.seed import demo_id
from app.api.recovery_schemas import AuthorizationAcknowledgment
from simulators.device.recovery_fence import active, next_sequence


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS recovery_action_ledger (
      operation_id TEXT PRIMARY KEY, activation_id TEXT NOT NULL UNIQUE,
      activation_hash TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('PREPARED','OBSERVED')),
      prepared_at TEXT NOT NULL, entry TEXT)''')
    conn.commit()


def validate(sim, task, *, prepared=False):
    """Under the SAME SQLite writer lock used by every command effect."""
    conn = sim.conn
    if not conn.in_transaction:
        raise RuntimeError('RECOVERY_EFFECT_REQUIRES_TRANSACTION')
    from simulators.device.recovery_reconciliation import deny_guard
    deny_guard(conn, 'OPERATION', task['operation_id'])
    p = task['activation_payload']
    fence = active(conn)
    ack = conn.execute('SELECT * FROM recovery_authorization_outbox WHERE authorization_id=?',
                       (task['authorization_id'],)).fetchone()
    ledger = conn.execute('SELECT ledger_id FROM recovery_local_identity WHERE singleton=1').fetchone()[0]
    if (task.get('task_kind') != 'ACTION' or task.get('effect_allowed') is not True
            or task.get('purpose') != 'RETURN_FOREIGN_OBJECT'
            or task['station_id'] != str(demo_id(sim.code))
            or canonical_hash(p) != task['activation_hash'] or p['effect_allowed'] is not True
            or p['activation_id'] != task['activation_id'] or p['authorization_id'] != task['authorization_id']
            or p['authorization_hash'] != task['authorization_hash']
            or p['operation_id'] != task['operation_id'] or p['context_hash'] != task['context_hash']
            or p['source_compartment_id'] != task['return_compartment_id']
            or p['actual_serial'] != task['expected_serial'] or p['recipient_id'] != task['customer_id']
            or p['destination'] != 'CUSTOMER' or p['boot_id'] != sim.boot or p['ledger_id'] != ledger
            or not fence or fence['boot_id'] != sim.boot or fence['operation_id'] != task['operation_id']
            or fence['context_hash'] != task['context_hash'] or fence['generation'] != p['fence_generation']
            or not ack or ack['authorization_hash'] != task['authorization_hash']
            or canonical_hash(AuthorizationAcknowledgment.model_validate_json(ack['packet']).model_dump(mode='json')) != p['acknowledgment_hash']
            or json.loads(ack['packet'])['event_id'] != p['acknowledgment_event_id']
            or datetime.fromisoformat(p['expires_at']) <= datetime.now(timezone.utc)
            or datetime.fromisoformat(p['proof_valid_until']) < datetime.now(timezone.utc)):
        raise ValueError('RECOVERY_ACTION_NOT_AUTHORIZED')
    commands = [dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')]
    services = conn.execute('SELECT * FROM service_operations').fetchall()
    if (canonical_hash(commands) != p['command_digest']
            or any(not prepared or r['id'] != task['operation_id'] or r['effects'] != 0 or r['state'] != 'UNKNOWN' for r in services)):
        raise ValueError('RECOVERY_LEDGER_CHANGED')
    slot_row = conn.execute('SELECT body FROM slots WHERE id=?', (p['source_compartment_id'],)).fetchone()
    slot = json.loads(slot_row[0]) if slot_row else None
    presenter = conn.execute('SELECT * FROM service_presenters WHERE serial=?', (p['actual_serial'],)).fetchone()
    if (not slot or slot['door_state'] != 'CLOSED' or slot['lock_released'] or not slot['present']
            or slot['observed_serial'] != p['actual_serial'] or not presenter
            or presenter['customer_id'] != p['recipient_id'] or presenter['swap_id'] != task['swap_id']):
        raise ValueError('RECOVERY_MODEL_CHANGED')
    return slot


def perform(sim, task, *, technician_token, crash_after_prepared=False):
    conn = sim.conn
    initialize(conn)
    prior = conn.execute('SELECT * FROM recovery_action_ledger WHERE operation_id=?', (task['operation_id'],)).fetchone()
    if prior:
        if prior['activation_id'] != task['activation_id'] or prior['activation_hash'] != task['activation_hash']:
            raise ValueError('RECOVERY_CONTEXT_CONFLICT')
        # PREPARED can mean an interrupted effect. Never execute it again, even
        # if this simulator happens to know its model transaction rolled back.
        return 'UNKNOWN' if prior['state'] == 'PREPARED' else prior['state']
    human_headers = {'Authorization':'Bearer ' + technician_token}
    actor = sim.http.get('/v1/me', headers=human_headers); actor.raise_for_status()
    case = sim.http.get(f"/v1/swaps/{task['swap_id']}/recovery", headers=human_headers); case.raise_for_status()
    op = case.json().get('active_operation')
    if (actor.json()['role'] != 'TECHNICIAN' or not op or op['id'] != task['operation_id']
            or op['created_by'] != actor.json()['id'] or op['context_hash'] != task['context_hash']):
        raise ValueError('SERVICE_TECHNICIAN_REQUIRED')
    fresh = sim.http.get('/v1/device/recovery-tasks'); fresh.raise_for_status()
    if task not in fresh.json()['items']:
        raise ValueError('SERVICE_TASK_NOT_AUTHORIZED')
    conn.execute('BEGIN IMMEDIATE')
    try:
        validate(sim, task)
        # An older ledger can lack this witness. Never backfill a no-effect
        # assertion for it. New ledgers leave NEVER_PREPARED atomically.
        conn.execute("""UPDATE recovery_effect_witness SET state='PREPARED'
            WHERE operation_id=? AND state='NEVER_PREPARED'""", (task['operation_id'],))
        conn.execute('INSERT INTO recovery_action_ledger VALUES (?,?,?,?,?,NULL)',
            (task['operation_id'],task['activation_id'],task['activation_hash'],'PREPARED',datetime.now(timezone.utc).isoformat()))
        conn.execute('INSERT INTO service_operations(id,context_hash,state) VALUES (?,?,?)',
            (task['operation_id'],task['context_hash'],'UNKNOWN'))
        conn.commit()
    except BaseException:
        conn.rollback(); raise
    if crash_after_prepared:
        raise RuntimeError('SIMULATED_SERVICE_CRASH_AFTER_PREPARED')
    conn.execute('BEGIN IMMEDIATE')
    try:
        slot = validate(sim, task, prepared=True)
        p = task['activation_payload']
        started = datetime.now(timezone.utc).isoformat()
        actual = slot['observed_serial']
        slot.update(present=False,observed_serial=None,battery_id=None)
        sim._effect_transaction = True
        sim.save_slot(slot)
        conn.execute('INSERT INTO service_positions VALUES (?,?) ON CONFLICT(serial) DO UPDATE SET customer_id=excluded.customer_id',
                     (actual,p['recipient_id']))
        snapshot = sim.snapshot()  # Actual post-effect model, in the same commit.
        completed = datetime.now(timezone.utc).isoformat()
        if (datetime.fromisoformat(completed) >= datetime.fromisoformat(p['expires_at'])
                or datetime.fromisoformat(completed) > datetime.fromisoformat(p['proof_valid_until'])):
            raise ValueError('RECOVERY_ACTION_EXPIRED')
        entry = {'operation_id':task['operation_id'],'activation_id':task['activation_id'],
            'authorization_id':task['authorization_id'],'context_hash':task['context_hash'],
            'state':'OBSERVED','effects':1,'actual_serial':actual,'recipient_id':p['recipient_id'],
            'source_compartment_id':slot['compartment_id'],'destination':'CUSTOMER','boot_id':sim.boot,
            'effect_started_at':started,'effect_completed_at':completed}
        packet = {'protocol_version':'0.2','stage':'POST_ACTION_RECEIPT','event_id':str(uuid4()),
            'operation_id':task['operation_id'],'context_hash':task['context_hash'],
            'authorization_id':task['authorization_id'],'authorization_hash':task['authorization_hash'],
            'activation_id':task['activation_id'],'activation_hash':task['activation_hash'],
            'boot_id':sim.boot,'seq':next_sequence(conn),'ledger_id':p['ledger_id'],
            'fence_generation':p['fence_generation'],'observed_at':datetime.now(timezone.utc).isoformat(),
            'effect_started_at':started,'effect_completed_at':completed,'actual_serial':actual,
            'source_compartment_id':slot['compartment_id'],'destination':'CUSTOMER','recipient_id':p['recipient_id'],
            'snapshot_event_id':snapshot['event_id'],'command_digest':p['command_digest'],
            'service_entry':entry,'service_entry_hash':canonical_hash(entry),
            'result':'OBSERVED','effect_count_delta':1,'simulation_only':True}
        conn.execute("UPDATE recovery_action_ledger SET state='OBSERVED',entry=? WHERE operation_id=?",
                     (json.dumps(entry),task['operation_id']))
        conn.execute("UPDATE service_operations SET state='OBSERVED',effects=1,observation=? WHERE id=?",
                     (json.dumps(packet),task['operation_id']))
        conn.commit()
        return 'OBSERVED'
    except BaseException:
        conn.rollback(); raise
    finally:
        sim._effect_transaction = False
