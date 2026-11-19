"""Readonly 0.3 ledger foundations. No authorization, actuator or fence release.

SQLite triggers journal actual writes in their writer transaction. A retained
pre-instrumentation database is marked incomplete; empty history never upgrades
it to a positive genesis. Commands cached before fencing are inventoried too.
"""
from datetime import datetime, timezone
import json

from app.domain.no_delivery import journal_digest
from app.domain.recovery import canonical_hash

TABLES = {
    'slots': ('id', ('id', 'body')),
    'commands': ('id', ('id', 'hash', 'status', 'effects', 'body')),
    'events': ('id', ('id', 'body')),
    'service_operations': ('id', ('id', 'context_hash', 'state', 'effects', 'observation')),
    'service_positions': ('serial', ('serial', 'customer_id')),
    'service_presenters': ('serial', ('serial', 'customer_id', 'swap_id')),
    'recovery_action_ledger': ('operation_id', ('operation_id', 'activation_id', 'activation_hash', 'state', 'prepared_at', 'entry')),
}


def bind(conn):
    """Bind pure SQL formatter before retained triggers can see any model write."""
    conn.create_function('nd_journal_hash', 4,
        lambda prev, table, identity, body: journal_digest(prev, table, identity, json.loads(body)))


def initialize(conn, *, new_ledger, boot_id):
    bind(conn)
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS nd_genesis (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), complete INTEGER NOT NULL CHECK(complete IN (0,1)),
        body TEXT NOT NULL, hash TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS nd_journal (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT, table_name TEXT NOT NULL,
        identity TEXT NOT NULL, body TEXT NOT NULL, previous_hash TEXT, hash TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS nd_fetched (
        kind TEXT NOT NULL, identity TEXT NOT NULL, hash TEXT NOT NULL, body TEXT NOT NULL,
        PRIMARY KEY(kind,identity));
      CREATE TABLE IF NOT EXISTS nd_denials (
        kind TEXT NOT NULL, identity TEXT NOT NULL, operation_id TEXT NOT NULL,
        PRIMARY KEY(kind,identity));
      CREATE TABLE IF NOT EXISTS nd_receipts (
        operation_id TEXT PRIMARY KEY, context_hash TEXT NOT NULL, packet TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS nd_receipt_dispositions (
        operation_id TEXT PRIMARY KEY, status INTEGER NOT NULL, response_hash TEXT NOT NULL);
    ''')
    if not conn.execute('SELECT 1 FROM nd_genesis').fetchone():
        empty = all(not conn.execute('SELECT 1 FROM '+name+' LIMIT 1').fetchone()
                    for name in ('commands', 'events', 'service_operations', 'recovery_action_ledger', 'recovery_station_fence'))
        body = {'boot_id': boot_id, 'created_at': datetime.now(timezone.utc).isoformat(),
                'slots': [json.loads(r[0]) for r in conn.execute('SELECT body FROM slots ORDER BY id')],
                'positions': [dict(r) for r in conn.execute('SELECT * FROM service_positions ORDER BY serial')]}
        conn.execute('INSERT INTO nd_genesis VALUES (1,?,?,?)',
                     (int(new_ledger and empty), json.dumps(body,sort_keys=True),canonical_hash(body)))
    # The same immutable policy protects genesis, original facts and deny records.
    for table in ('nd_genesis', 'nd_journal', 'nd_fetched', 'nd_denials','nd_receipt_dispositions'):
        for action in ('UPDATE', 'DELETE'):
            conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()} BEFORE {action} ON {table} "
                         "BEGIN SELECT RAISE(ABORT,'ND_APPEND_ONLY'); END")
    conn.execute("CREATE TRIGGER IF NOT EXISTS nd_receipts_immutable BEFORE UPDATE OF operation_id,context_hash,packet ON nd_receipts "
                 "BEGIN SELECT RAISE(ABORT,'ND_APPEND_ONLY'); END")
    conn.execute("CREATE TRIGGER IF NOT EXISTS nd_receipts_delete BEFORE DELETE ON nd_receipts "
                 "BEGIN SELECT RAISE(ABORT,'ND_APPEND_ONLY'); END")
    for table, (key, columns) in TABLES.items():
        for action, source in (('INSERT','NEW'), ('UPDATE','NEW'), ('DELETE','OLD')):
            fields = ','.join("'"+c+"',"+source+'.'+c for c in columns)
            body = "json_object('action','"+action+"','row',json_object("+fields+'))'
            previous = '(SELECT hash FROM nd_journal ORDER BY sequence DESC LIMIT 1)'
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS nd_track_{table}_{action.lower()}
              AFTER {action} ON {table} BEGIN
              INSERT INTO nd_journal(table_name,identity,body,previous_hash,hash)
              VALUES ('{table}',{source}.{key},{body},{previous},
                      nd_journal_hash({previous},'{table}',{source}.{key},{body})); END''')
    # Defense at the actual model write, including an already-fetched legacy
    # command/action. Its SQLite writer serializes with fence installation.
    condition = "EXISTS(SELECT 1 FROM recovery_station_fence WHERE state='ACTIVE' AND json_extract(inspection,'$.protocol_version')='0.3')"
    for table in ('slots', 'service_positions', 'service_presenters'):
        for action in ('INSERT','UPDATE','DELETE'):
            conn.execute(f"CREATE TRIGGER IF NOT EXISTS nd_effect_fence_{table}_{action.lower()} "
                         f"BEFORE {action} ON {table} WHEN {condition} "
                         "BEGIN SELECT RAISE(ABORT,'ND_STATION_FENCED'); END")
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        append(conn, 'BOOT', boot_id, {'boot_id':boot_id})
        conn.commit()
    except BaseException:
        conn.rollback(); raise


def append(conn, table, identity, body):
    if not conn.in_transaction:
        raise RuntimeError('ND_WRITER_REQUIRED')
    row = conn.execute('SELECT hash FROM nd_journal ORDER BY sequence DESC LIMIT 1').fetchone()
    previous = row[0] if row else None
    conn.execute('INSERT INTO nd_journal(table_name,identity,body,previous_hash,hash) VALUES (?,?,?,?,?)',
        (table,str(identity),json.dumps(body,sort_keys=True),previous,journal_digest(previous,table,identity,body)))


def verify_history(conn):
    genesis = conn.execute('SELECT * FROM nd_genesis').fetchone()
    if (not genesis or not genesis['complete']
            or canonical_hash(json.loads(genesis['body'])) != genesis['hash']):
        raise RuntimeError('ND_HISTORY_INCOMPLETE')
    previous, sequence = None, 0
    latest = {}
    for row in conn.execute('SELECT * FROM nd_journal ORDER BY sequence'):
        if (row['sequence'] != sequence+1 or row['previous_hash'] != previous
                or row['hash'] != journal_digest(previous,row['table_name'],row['identity'],json.loads(row['body']))):
            raise RuntimeError('ND_HISTORY_INCOMPLETE')
        previous, sequence = row['hash'], row['sequence']
        if row['table_name'] in TABLES:
            latest[(row['table_name'],row['identity'])] = json.loads(row['body'])
            if (json.loads(row['body'])['action']=='DELETE'
                    and row['table_name'] in ('commands','events','service_operations','recovery_action_ledger')):
                raise RuntimeError('ND_HISTORY_INCOMPLETE')
    for name, (key, columns) in TABLES.items():
        # Initial slot/position model is witnessed by immutable genesis; every
        # subsequent change and every effect/source record needs the journal.
        for row in conn.execute('SELECT * FROM '+name):
            item = latest.get((name,row[key]))
            if item:
                if item['action']=='DELETE' or item['row'] != {c:row[c] for c in columns}:
                    raise RuntimeError('ND_HISTORY_INCOMPLETE')
            elif name == 'slots':
                if json.loads(row['body']) not in json.loads(genesis['body'])['slots']:
                    raise RuntimeError('ND_HISTORY_INCOMPLETE')
            elif name == 'service_positions':
                if dict(row) not in json.loads(genesis['body'])['positions']:
                    raise RuntimeError('ND_HISTORY_INCOMPLETE')
            else:
                raise RuntimeError('ND_HISTORY_INCOMPLETE')
    return previous


def register_tasks(conn, kind, items):
    """Called immediately on authenticated fetch, before the caller can cache it.

    Frozen command hash excludes replay ACK metadata. Registry conflict refuses
    rather than changing a cached issuer fact. No network wait under the writer.
    """
    if conn.in_transaction:
        raise RuntimeError('ND_FETCH_OUTSIDE_TRANSACTION_REQUIRED')
    conn.execute('BEGIN IMMEDIATE')
    try:
        from simulators.device.recovery_fence import active
        fence = active(conn)
        staged = fence and json.loads(fence['inspection']).get('protocol_version')=='0.3'
        for item in items:
            identity = item.get('id') if kind=='COMMAND' else item.get('operation_id',item.get('context',{}).get('operation_id'))
            if not identity:
                raise ValueError('ND_FETCH_ID_REQUIRED')
            # Task representations change between stages. Each signed activation
            # is separately inventoried, never collapsed into its operation ID.
            variant = item.get('activation_id') or item.get('authorization_id') or item.get('task_kind','LEGACY')
            identity = str(identity) if kind=='COMMAND' else str(identity)+':'+str(variant)
            hashed = canonical_hash(item)
            prior = conn.execute('SELECT hash FROM nd_fetched WHERE kind=? AND identity=?',(kind,identity)).fetchone()
            if prior and prior[0] != hashed:
                raise RuntimeError('ND_ISSUER_CONTEXT_CONFLICT')
            if not prior:
                conn.execute('INSERT INTO nd_fetched VALUES (?,?,?,?)',(kind,identity,hashed,json.dumps(item,sort_keys=True)))
            if staged:
                conn.execute('INSERT OR IGNORE INTO nd_denials VALUES (?,?,?)',(kind,identity,fence['operation_id']))
        conn.commit()
    except BaseException:
        conn.rollback(); raise


def install_fence(sim, task):
    """Authenticate a readonly task, then atomically deny cached and future work.

    A negative inspection keeps this fence too. This function never submits a
    receipt and never treats missing/UNKNOWN service facts as NEVER_PREPARED.
    """
    from app.api.no_delivery_schemas import P8NDInspectionTask
    from app.seed import demo_id
    from simulators.device.recovery_fence import active
    dto = P8NDInspectionTask.model_validate(task)
    ctx = dto.context
    if canonical_hash({k:v for k,v in task['context'].items() if k!='context_hash'}) != ctx.context_hash:
        raise ValueError('ND_CONTEXT_HASH_INVALID')
    if ctx.station_id != demo_id(sim.code) or ctx.device_id != demo_id('device:'+sim.code):
        raise ValueError('ND_STATION_CONTEXT_MISMATCH')
    # Network fetch is deliberately outside SQLite writer ownership.
    response = sim.http.get('/v1/device/recovery-tasks')
    response.raise_for_status()
    if task not in response.json()['items']:
        raise ValueError('SERVICE_TASK_NOT_AUTHORIZED')
    conn = sim.conn
    conn.execute('BEGIN IMMEDIATE')
    try:
        existing = active(conn)
        if existing and existing['operation_id']==str(ctx.operation_id):
            if existing['context_hash'] != ctx.context_hash:
                raise ValueError('ND_CONTEXT_CONFLICT')
            conn.rollback()
            return dict(existing)
        if ctx.expires_at <= datetime.now(timezone.utc):
            raise ValueError('ND_OPERATION_EXPIRED')
        if existing:
            prior = json.loads(existing['inspection'])
            if (prior.get('protocol_version')!='0.3' or str(ctx.predecessor_id)!=existing['operation_id']
                    or ctx.predecessor_context_hash!=existing['context_hash']):
                raise RuntimeError('RECOVERY_STATION_FENCED')
            conn.execute("UPDATE recovery_station_fence SET state='CLOSED' WHERE generation=?",(existing['generation'],))
        local = {'protocol_version':'0.3','context':ctx.model_dump(mode='json',exclude_unset=True),
                 'read_only':True,'effect_count_delta':0}
        conn.execute("INSERT INTO recovery_station_fence(operation_id,context_hash,boot_id,state,inspection) VALUES (?,?,?,'ACTIVE',?)",
            (str(ctx.operation_id),ctx.context_hash,sim.boot,json.dumps(local,sort_keys=True)))
        # Permanent union denials never disappear on successor, expiry or boot.
        conn.execute('INSERT OR IGNORE INTO nd_denials VALUES (?,?,?)',('FUTURE','*',str(ctx.operation_id)))
        for row in conn.execute('SELECT kind,identity FROM nd_fetched').fetchall():
            conn.execute('INSERT OR IGNORE INTO nd_denials VALUES (?,?,?)',(row['kind'],row['identity'],str(ctx.operation_id)))
        append(conn,'FENCE',str(ctx.operation_id),local)
        result = dict(active(conn))
        conn.commit()
        return result
    except BaseException:
        conn.rollback(); raise


def inspect(sim, task):
    """Current model + complete retained facts. A refusal never removes a fence.

    Snapshot transport/worker waits run outside the SQLite writer. Once the
    fence is committed no effect can change the station model between capture
    and receipt. Replays return the original packet, never a newer timestamp.
    """
    from uuid import uuid4
    from app.api.no_delivery_schemas import P8NDObservation
    from app.domain.device import validate_event
    from app.domain.no_delivery import history_digest
    from simulators.device.recovery_fence import active
    install_fence(sim,task)
    conn=sim.conn;ctx=task['context'];identity=ctx['operation_id']
    prior=conn.execute('SELECT * FROM nd_receipts WHERE operation_id=?',(identity,)).fetchone()
    if prior:
        if prior['context_hash']!=ctx['context_hash']:
            raise ValueError('ND_CONTEXT_CONFLICT')
        return json.loads(prior['packet'])
    snapshot=sim.snapshot()
    receipts=sim.flush()
    sim.settle(receipts,snapshot['seq'])
    # A previous process may have stopped after 202, before worker processing.
    # Query its immutable packet's disposition outside the writer; do not
    # recapture the source or treat the cached QUEUED response as final proof.
    if not refresh_sources(sim):
        raise RuntimeError('ND_SOURCE_HISTORY_UNPROCESSED')
    conn.execute('BEGIN IMMEDIATE')
    try:
        verify_history(conn)
        fence=active(conn)
        if (not fence or fence['operation_id']!=identity or fence['context_hash']!=ctx['context_hash']
                or datetime.fromisoformat(ctx['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc)):
            raise RuntimeError('ND_CONTEXT_CONFLICT')
        row=conn.execute('SELECT body FROM slots WHERE id=?',(ctx['supply_compartment_id'],)).fetchone()
        slot=json.loads(row[0]) if row else None
        if (not slot or not slot['present'] or slot['door_state']!='CLOSED' or slot['lock_released']
                or slot['observed_serial']!=ctx['expected_serial']):
            raise RuntimeError('ND_ACTUAL_MODEL_UNPROVEN')
        actual=slot['observed_serial']  # Model value; expectation is only an interlock.
        if conn.execute('SELECT 1 FROM service_positions WHERE serial=?',(actual,)).fetchone():
            raise RuntimeError('ND_DELIVERY_HISTORY_CONFLICT')
        commands=[dict(r) for r in conn.execute('SELECT * FROM commands ORDER BY id')]
        if any((c['status'],c['effects']) not in (('NOT_EXECUTED',0),('EXECUTED',1)) for c in commands):
            raise RuntimeError('ND_UNRESOLVED_COMMAND')
        events=[json.loads(r[0]) for r in conn.execute('SELECT body FROM events ORDER BY rowid')]
        if any(e['kind']=='COMMAND_ACK' and e['payload'].get('result')=='UNKNOWN' for e in events):
            raise RuntimeError('ND_SOURCE_UNCERTAIN')
        # Physical pickup is a model/evidence fact, not an ACK or ledger status.
        # A delivered-and-returned pin remains disqualifying history.
        for command in commands:
            body=json.loads(command['body'])
            chain=[e for e in events if e.get('command_id')==command['id']]
            if not command['effects'] and any(e['kind'] in ('DOOR','PRESENCE') for e in chain):
                raise RuntimeError('ND_SOURCE_UNCERTAIN')
            if command['effects'] and not any(e['kind']=='PRESENCE' for e in chain):
                raise RuntimeError('ND_HISTORY_INCOMPLETE')
            if (body['kind']=='OPEN_SUPPLY' and body['payload']['expected_serial']==actual
                    and any(e['kind']=='PRESENCE' and e['payload']['present'] is False for e in chain)):
                raise RuntimeError('ND_DELIVERY_HISTORY_CONFLICT')
        fetched=[json.loads(r[0]) for r in conn.execute("SELECT body FROM nd_fetched WHERE kind='SERVICE'")]
        services=[]
        for row in conn.execute('SELECT * FROM service_operations ORDER BY id'):
            if row['state'] not in ('OBSERVED','REJECTED') or not row['observation']:
                raise RuntimeError('ND_UNRESOLVED_SERVICE')
            packet=json.loads(row['observation'])
            original=next((t for t in fetched if t.get('operation_id')==row['id']),None)
            if not original:
                raise RuntimeError('ND_HISTORY_INCOMPLETE')
            purpose=original['purpose']
            observed=packet.get('actual_serial',packet.get('observation',{}).get('actual_serial'))
            if row['effects'] and observed==actual:
                raise RuntimeError('ND_DELIVERY_HISTORY_CONFLICT')
            services.append(dict(operation_id=row['id'],context_hash=row['context_hash'],purpose=purpose,
                state=row['state'],effects=row['effects'],receipt_event_id=packet['event_id'],
                durably_disabled=True))
        command_digest,service_digest=canonical_hash(commands),canonical_hash(services)
        ledger=conn.execute('SELECT ledger_id FROM recovery_local_identity').fetchone()[0]
        # Every source packet must have been accepted/processed. This local check
        # is independently repeated against Backend persisted source facts.
        for event_row in conn.execute('SELECT receipt FROM events'):
            receipt=json.loads(event_row[0]) if event_row[0] else None
            if not receipt or receipt.get('processing_state')!='PROCESSED':
                raise RuntimeError('ND_SOURCE_HISTORY_UNPROCESSED')
        denied_commands=sorted({r[0] for r in conn.execute("SELECT identity FROM nd_denials WHERE kind='COMMAND'")} |
                               {c['id'] for c in commands})
        for command_id in denied_commands:
            conn.execute('INSERT OR IGNORE INTO nd_denials VALUES (?,?,?)',('COMMAND',command_id,identity))
        activations=sorted({t['activation_id'] for t in fetched if t.get('activation_id')})
        for activation_id in activations:
            conn.execute('INSERT OR IGNORE INTO nd_denials VALUES (?,?,?)',('ACTIVATION',activation_id,identity))
        packet=dict(protocol_version='0.3',stage='NO_DELIVERY_INSPECTION',event_id=str(uuid4()),
            operation_id=identity,context_hash=ctx['context_hash'],device_id=ctx['device_id'],boot_id=sim.boot,
            seq=receipt_sequence(sim),observed_at=datetime.now(timezone.utc).isoformat(),
            snapshot_event_id=snapshot['event_id'],snapshot_hash=validate_event(snapshot)[1],
            actual_serial=actual,supply_compartment_id=slot['compartment_id'],present=True,door_state='CLOSED',
            read_only=True,effect_count_delta=0,result='OBSERVED',command_entries=commands,service_entries=services,
            quiescence=dict(ledger_id=ledger,fence_generation=fence['generation'],fence_active=True,
                cached_commands_denied=True,cached_service_tasks_denied=True,all_issuers_fenced=True,
                command_digest=command_digest,service_digest=service_digest,denied_command_ids=denied_commands,
                denied_activation_ids=activations,watermark_event_id=snapshot['event_id'],watermark_hash=validate_event(snapshot)[1]),
            delivery_history=dict(complete=True,swap_id=ctx['swap_id'],serial=actual,delivery_count=0,
                journal_hash=history_digest(ledger,ctx['swap_id'],actual,
                    [{'event_id':e['event_id'],'boot_id':e['boot_id'],'seq':e['seq'],
                      'payload_hash':validate_event(e)[1]} for e in events],command_digest,service_digest),
                event_ids=[e['event_id'] for e in events],boot_ids=list(dict.fromkeys(e['boot_id'] for e in events))))
        # Shape is frozen; no UNKNOWN packet or forged positive fallback.
        P8NDObservation.model_validate(packet)
        conn.execute('INSERT INTO nd_receipts(operation_id,context_hash,packet) VALUES (?,?,?)',
                     (identity,ctx['context_hash'],json.dumps(packet,sort_keys=True)))
        conn.commit()
        sim.seq=max(sim.seq,packet['seq']+1)
        return packet
    except BaseException:
        conn.rollback(); raise


def receipt_sequence(sim):
    """Share a high-watermark with actual current-boot source events.

    Existing 0.1/0.2 counters and old packets are retained. No old sequence or
    timestamp is rewritten; the next source event continues after this receipt.
    Caller owns the same SQLite writer as packet insertion.
    """
    from simulators.device.recovery_fence import next_sequence
    conn=sim.conn
    if not conn.in_transaction:
        raise RuntimeError('ND_WRITER_REQUIRED')
    value=max(next_sequence(conn),sim.seq)
    for row in conn.execute('SELECT body FROM events'):
        event=json.loads(row[0])
        if event['boot_id']==sim.boot:value=max(value,event['seq']+1)
    for table in ('nd_receipts','recovery_inspection_outbox','recovery_authorization_outbox','recovery_closure_outbox'):
        for row in conn.execute('SELECT packet FROM '+table):
            packet=json.loads(row[0])
            if packet['boot_id']==sim.boot:value=max(value,packet['seq']+1)
    conn.execute("UPDATE service_metadata SET value=? WHERE key='receipt_sequence'",(str(value),))
    return value


def refresh_sources(sim):
    """One bounded pass over retained source dispositions; no physical writes."""
    # A service caller may have flushed a trailing source snapshot after capture.
    # 202 is not processing. Do not submit this immutable receipt until every
    # source sent so far has a durable processed disposition. Never recapture or
    # rehabilitate a semantically rejected event under the same identity.
    pending=sim.conn.execute("SELECT id,body FROM events WHERE receipt IS NULL OR json_extract(receipt,'$.processing_state')!='PROCESSED'").fetchall()
    ready=True
    for event in pending:
        response=sim.http.post('/v1/device/events',json=json.loads(event['body']))
        if response.status_code!=202:
            ready=False;continue
        receipt=response.json()
        sim.conn.execute('UPDATE events SET receipt=? WHERE id=?',(json.dumps(receipt),event['id']))
        sim.conn.commit()
        if receipt.get('processing_state')!='PROCESSED':ready=False
    return ready


def flush(sim):
    if not refresh_sources(sim):return
    for row in sim.conn.execute('SELECT operation_id,packet FROM nd_receipts WHERE sent=0').fetchall():
        response=sim.http.post('/v1/device/recovery-observations',json=json.loads(row['packet']))
        if response.status_code in (202,409,422):
            sim.conn.execute('INSERT INTO nd_receipt_dispositions VALUES (?,?,?)',
                             (row['operation_id'],response.status_code,canonical_hash(response.json())))
            sim.conn.execute('UPDATE nd_receipts SET sent=? WHERE operation_id=?',
                             (1 if response.status_code==202 else 2,row['operation_id']))
            sim.conn.commit()
