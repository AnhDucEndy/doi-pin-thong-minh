"""Owner-only read projection. References are selected from accepted DB facts."""
from sqlalchemy import select
from app.domain.recovery import canonical_hash


def project(session, db, swap, case, op):
    from app.application import recovery as r
    staged = op['protocol_version'] == '0.2'
    table = db.table('recovery_attestations')
    rows = session.execute(select(table).where(table.c.operation_id == op['id'])).mappings().all()
    stage = 'LEGACY'
    if staged:
        stage = 'RECONCILIATION_INSPECTION' if op['context'].get('reconciliation_only') else (
            'POST_ACTION_RECEIPT' if any(p['source_kind']=='SIMULATOR' and p['stage']=='POST_ACTION_RECEIPT' for p in rows)
            else 'PRE_ACTION_INSPECTION')
    proof = next((p for p in rows if p['source_kind']=='SIMULATOR' and p['stage']==stage), None)
    own = next((p for p in rows if p['source_kind']=='CUSTOMER' and p['stage']==stage), None)
    now = r.utcnow()
    status = 'AVAILABLE' if not staged else 'WAITING_RECEIPT'
    valid = bool(proof and proof['payload_hash']==canonical_hash(proof['payload'])
                 and proof['payload'].get('context_hash')==op['context_hash'])
    if staged and valid:
        dev = r.assets.available_device(session,db,swap['station_id'])
        status = 'AVAILABLE' if (
            proof['payload'].get('result')=='OBSERVED' and dev and dev['enabled']
            and proof['device_id']==dev['id'] and proof['source_boot']==dev['boot_id']
            and r.assets.fresh(proof['observed_at'],now,swap['policy_snapshot'])
        ) else 'UNAVAILABLE'
    if staged and proof and not valid:
        status = 'UNAVAILABLE'
    if own:
        status = 'CONFIRMED' if own['payload'].get('confirm') is True else 'REJECTED'
    permits = db.table('recovery_action_authorizations')
    permit = session.execute(select(permits).where(permits.c.operation_id==op['id'])).mappings().first()
    if permit and permit['revoked_at']:
        status = 'REVOKED'
    if now >= op['expires_at']:
        status = 'EXPIRED'
    if op['consumed_at']:
        status = 'CONSUMED'
    if op['cancelled_at']:
        status = 'CANCELLED'
    if case['operation_id']!=op['id'] or case['state']=='RESOLVED' or swap['state'] not in ('REVIEW_REQUIRED','COMPENSATING'):
        status = 'UNAVAILABLE'
    return {
        'operation_id':op['id'], 'context_hash':op['context_hash'],
        'purpose':op['purpose'], 'expected_serial':op['expected_serial'],
        'station_id':op['station_id'], 'customer_id':op['customer_id'],
        'expires_at':op['expires_at'], 'simulation_only':True,
        'protocol_version':op['protocol_version'], 'stage':stage,
        'case_version':case['version'], 'confirmation_status':status,
        'receipt_id':proof['id'] if staged and valid else None,
        'receipt_hash':proof['payload_hash'] if staged and valid else None,
        'receipt_observed_at':proof['observed_at'] if staged and valid else None,
    }
