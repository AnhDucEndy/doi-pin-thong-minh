"""Safe, transaction-local audit snapshots. No locks, clocks or state changes.

Callers already own Recovery's station/user/resource locks. Capture BEFORE any
write, before final time guards, and read AFTER through the same transaction.
Only these columns are audit data: never copy a row/context/payload wholesale.
"""
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

FIELDS = {
    'recovery_cases': ('id','swap_id','state','reason_code','assigned_to','operation_id',
        'evidence_event_id','old_pin_settled','new_pin_delivered','version','created_at','resolved_at'),
    'recovery_operations': ('id','case_id','swap_id','station_id','customer_id','created_by',
        'purpose','protocol_version','expected_serial','context_hash','base_case_version',
        'base_swap_version','supersedes_id','created_at','expires_at','consumed_at','cancelled_at'),
    'recovery_attestations': ('id','operation_id','event_id','stage','source_kind','actor_user_id',
        'device_id','source_event_id','source_boot','source_seq','reference_receipt_id',
        'observed_at','received_at','payload_hash'),
    'recovery_action_authorizations': ('id','operation_id','context_hash','inspection_id',
        'technician_attestation_id','customer_attestation_id','device_id','boot_id','ledger_id',
        'fence_generation','authorized_by','issued_at','expires_at','revoked_at','authorization_hash'),
    'recovery_authorization_acks': ('id','authorization_id','event_id','device_id','boot_id',
        'seq','observed_at','received_at','payload_hash'),
    'recovery_action_activations': ('id','operation_id','authorization_id','acknowledgment_id',
        'activated_by','issued_at','expires_at','payload_hash'),
    'recovery_closure_intents': ('id','operation_id','created_by','auth_session_id','created_at','payload_hash'),
    'recovery_closure_receipts': ('id','closure_id','event_id','device_id','boot_id','seq',
        'observed_at','received_at','payload_hash'),
    'swap_transactions': ('id','state','version','review_reason','station_id','customer_id','old_battery_id',
        'new_battery_id','return_compartment_id','supply_compartment_id','return_observed_at',
        'pickup_observed_at','closed_at'),
    'batteries': ('id','serial','location_kind','holder_user_id','compartment_id','version'),
    'resource_reservations': ('id','swap_id','battery_id','compartment_id','released_at'),
    'device_commands': ('id','swap_id','device_id','compartment_id','kind','state','created_at',
        'expires_at','evidence_event_id','payload_hash'),
    'payments': ('id','swap_id','state','amount_minor','currency','verified_at'),
}


def snapshot(session, db, case):
    def rows(name, column, values):
        if name not in db.tables or not values:
            return {}
        table = db.table(name)
        columns = [table.c[k] for k in FIELDS[name] if k in table.c]
        result = session.execute(select(*columns).where(table.c[column].in_(values))
                                 .order_by(table.c.id)).mappings().all()
        return {str(row['id']): jsonable_encoder(dict(row)) for row in result}

    cases = rows('recovery_cases', 'id', [case['id']])
    swaps = rows('swap_transactions', 'id', [case['swap_id']])
    operations = rows('recovery_operations', 'case_id', [case['id']])
    op_ids = [row['id'] for row in operations.values()]
    permits = rows('recovery_action_authorizations', 'operation_id', op_ids)
    closures = rows('recovery_closure_intents', 'operation_id', op_ids)
    pins = {row[k] for row in swaps.values() for k in ('old_battery_id','new_battery_id') if row.get(k)}
    return {'snapshot_version': 1, 'case': next(iter(cases.values())),
        'operations': operations,
        'attestations': rows('recovery_attestations','operation_id',op_ids),
        'authorizations': permits,
        'authorization_acks': rows('recovery_authorization_acks','authorization_id',[p['id'] for p in permits.values()]),
        'activations': rows('recovery_action_activations','operation_id',op_ids),
        'closure_intents': closures,
        'closure_receipts': rows('recovery_closure_receipts','closure_id',[c['id'] for c in closures.values()]),
        'swap': next(iter(swaps.values())), 'batteries': rows('batteries','id',pins),
        'holds': rows('resource_reservations','swap_id',[case['swap_id']]),
        'commands': rows('device_commands','swap_id',[case['swap_id']]),
        'payments': rows('payments','swap_id',[case['swap_id']])}


SECRET_KEYS = {'password','password_hash','token','token_hash','access_token','refresh_token',
    'qr','qr_token','raw_qr','secret','api_key','device_key','authorization','signature',
    'payload','raw_payload','headers','note','resolution_note','x_device_key','cookie','set_cookie','credentials'}


def safe(value):
    """Existing audit details are server-built refs; exclude secret/raw fields."""
    if isinstance(value, dict):
        return {k: safe(v) for k,v in value.items() if k.lower().replace('-','_') not in SECRET_KEYS}
    if isinstance(value, (list,tuple)):
        return [safe(x) for x in value]
    return jsonable_encoder(value)


def created(session, db, case, worker):
    """An INSERT..ON CONFLICT that returned a new case has no before-object."""
    if case is not None:
        from app.application import recovery
        recovery.audit(session, db, {'id': worker}, case, 'RECOVERY_CASE_CREATED',
            {'swap_id': case['swap_id']}, before=None, actor_type='SYSTEM')
