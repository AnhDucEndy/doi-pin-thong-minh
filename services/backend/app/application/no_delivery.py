"""Readonly 0.3 Recovery adapter. No custody, release, actuator or money effect."""
from datetime import timedelta
import hashlib
import json
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select, update, func

from app.api import no_delivery_schemas as dto
from app.application import recovery as r
from app.application.identity import DomainError, idempotent
from app.domain.no_delivery import history_digest
from app.domain.recovery import canonical_hash

STAGE='NO_DELIVERY_INSPECTION'


def refuse(code='EVIDENCE_REQUIRED', status=422):
    raise DomainError(status,code)


def station_fence(session, db, station_id):
    table=db.table('recovery_operations')
    # No 0.3 release protocol exists in B1b. TTL, redemption and even terminal
    # operation markers cannot attest that durable device denials are closed.
    # Prefer the current case pointer so a cancelled predecessor cannot displace
    # its successor; retain a conservative fence if metadata alone is changed.
    cases=db.table('recovery_cases')
    current=select(cases.c.operation_id).where(cases.c.operation_id.is_not(None))
    return session.execute(select(table).where(table.c.station_id==station_id,
        table.c.protocol_version=='0.3').order_by(table.c.id.in_(current).desc(),
        table.c.created_at.desc(),table.c.id)).mappings().first()


def tasks(session,db,dev):
    op=station_fence(session,db,dev['station_id'])
    if op is None:return None
    case=r.case_for(session,db,op['swap_id']);swap=r.assets.get_row(session,db,'swap_transactions',op['swap_id'])
    creator=r.assets.get_row(session,db,'users',op['created_by'])
    if creator['state']!='ACTIVE' or creator['role']!='TECHNICIAN':return {'items':[]}
    try:
        r.assets.scope(session,db,creator,dev['station_id'])
        operation(session,db,swap,case,op['id'])
    except DomainError:return {'items':[]}
    return {'items':[dict(protocol_version='0.3',task_kind='VERIFY_NO_DELIVERY_INSPECT',
                          context=op['context'],effect_allowed=False)]}


def rows(session, db, op_id):
    table=db.table('recovery_attestations')
    return session.execute(select(table).where(table.c.operation_id==op_id,
        table.c.stage==STAGE).order_by(table.c.received_at,table.c.id)).mappings().all()


def authority(session,db,actor,swap,tokens,role):
    user=r.assets.get_row(session,db,'users',actor['user']['id'])
    token=tokens[actor['session']['id']]
    if (token['user_id']!=user['id'] or user['state']!='ACTIVE'
            or token['revoked_at'] or token['expires_at']<=r.utcnow()):
        refuse('SESSION_REVOKED',401)
    if user['role']!=role:refuse('FORBIDDEN',403)
    if role=='TECHNICIAN':r.assets.scope(session,db,user,swap['station_id'])
    if role=='CUSTOMER' and user['id']!=swap['customer_id']:refuse('FORBIDDEN',403)
    return user


def protected(request,session,actor,key,swap_id,body,status,role,execute):
    """Station/users/resources/payment/children, then sorted exact sessions.

    Replays revalidate caller authority after idempotency wait. Witness validity
    is checked by a new decision, never renewed by a replay of a committed fact.
    """
    db=request.app.state.db;state={}
    def authorize():
        swap,case=r.lock_context(session,db,swap_id,actor['user']['id'])
        payment=db.table('payments')
        charge=session.execute(select(payment).where(payment.c.swap_id==swap_id).with_for_update()).mappings().first()
        operations=db.table('recovery_operations');attestations=db.table('recovery_attestations')
        op_ids=list(session.scalars(select(operations.c.id).where(operations.c.case_id==case['id'])))
        proofs=session.execute(select(attestations).where(attestations.c.operation_id.in_(op_ids))).mappings().all()
        identities={actor['session']['id']}
        for proof in proofs:
            if proof['source_kind'] in ('TECHNICIAN','CUSTOMER'):
                try:identities.add(UUID(proof['payload']['auth_session_id']))
                except (KeyError,ValueError,TypeError):refuse()
        certs=db.table('refund_eligibility_certificates')
        identities.update(v for v in session.scalars(select(certs.c.issuer_session_id).where(
            certs.c.operation_id.in_(op_ids))) if v is not None)
        tokens={identity:r.assets.get_row(session,db,'auth_sessions',identity,lock=True)
                for identity in sorted(identities)}
        authority(session,db,actor,swap,tokens,role)
        state.update(swap=swap,case=case,charge=charge,tokens=tokens)
    return idempotent(session,db,actor['user']['id'],request.method+' '+request.url.path,
        key,body.model_dump(mode='json',exclude_unset=True),status,
        lambda:execute(db,**state),authorize=authorize)


def operation(session,db,swap,case,identity=None):
    op=r.assets.get_row(session,db,'recovery_operations',identity or case['operation_id'])
    if (op['protocol_version']!='0.3' or op['purpose']!='VERIFY_NO_DELIVERY'
            or op['id']!=case['operation_id'] or op['swap_id']!=swap['id']
            or op['case_id']!=case['id'] or op['station_id']!=swap['station_id']
            or op['customer_id']!=swap['customer_id']):
        refuse('RECOVERY_CONTEXT_MISMATCH',409)
    r.open_operation(op)
    if swap['state'] not in ('REVIEW_REQUIRED','COMPENSATING') or case['state']=='RESOLVED':
        refuse('STATE_CONFLICT',409)
    return op


def audit_snapshot(session,db,case):
    result=r.audit_snapshot(session,db,case)
    certificates=db.table('refund_eligibility_certificates')
    result['no_delivery_certificates']={str(v['id']):jsonable_encoder({k:v[k] for k in
        ('id','operation_id','payment_id','receipt_id','technician_attestation_id','customer_attestation_id',
         'issued_by','issuer_session_id','validated_at','valid_until','payload_hash')})
        for v in session.execute(select(certificates).where(certificates.c.operation_id.in_(
            select(db.table('recovery_operations').c.id).where(db.table('recovery_operations').c.case_id==case['id'])))).mappings()}
    rev=db.table('refund_certificate_revocations')
    result['no_delivery_revocations']=[jsonable_encoder(dict(v)) for v in session.execute(select(rev).where(
        rev.c.certificate_id.in_([UUID(k) for k in result['no_delivery_certificates']])).order_by(rev.c.id)).mappings()]
    redemptions=db.table('refund_certificate_redemptions')
    result['no_delivery_redemptions']=[jsonable_encoder(dict(v)) for v in session.execute(select(redemptions).where(
        redemptions.c.certificate_id.in_([UUID(k) for k in result['no_delivery_certificates']])).order_by(redemptions.c.certificate_id)).mappings()]
    return result


def audit(session,db,actor,case,action,before,**references):
    # References are server-selected identifiers/hashes; no notes/raw packets.
    session.execute(insert(db.table('audit_events')).values(id=uuid4(),
        actor_type='USER' if actor.get('role') else 'DEVICE',actor_id=str(actor['id']),
        aggregate_type='recovery',aggregate_id=case['id'],action=action,
        before_data=before,after_data={**audit_snapshot(session,db,case),
            'references':jsonable_encoder(references)},correlation_id=case['swap_id']))


def record(request,session,actor,key,swap_id,body):
    def execute(db,swap,case,charge,tokens):
        r.assets.version(case,body.expected_version)
        if swap['state'] not in ('REVIEW_REQUIRED','COMPENSATING') or case['state']=='RESOLVED':
            refuse('STATE_CONFLICT',409)
        if isinstance(body,dto.P8NDBeginRequest):
            return begin(session,db,actor,swap,case,body,tokens)
        op=operation(session,db,swap,case,body.statement.operation_id)
        if isinstance(body,dto.P8NDTechnicianAttestation):
            human(session,db,actor,swap,case,op,body.statement,tokens,'TECHNICIAN')
        else:
            issue_certificate(session,db,actor,swap,case,op,body.statement,charge,tokens)
        case=r.case_for(session,db,swap_id)
        return get(session,db,actor,swap,case,op)
    return protected(request,session,actor,key,swap_id,body,200,'TECHNICIAN',execute)


def begin(session,db,actor,swap,case,body,tokens):
    table=db.table('recovery_operations');previous=None
    current=station_fence(session,db,swap['station_id'])
    prior=body.statement.predecessor_id
    if current:
        if not prior or current['id']!=prior or current['case_id']!=case['id']:
            refuse('RECOVERY_OPERATION_ACTIVE',409)
        rejected=any(p['source_kind'] in ('TECHNICIAN','CUSTOMER') and p['payload'].get('confirm') is False
                     for p in rows(session,db,current['id']))
        if current['consumed_at'] or current['cancelled_at'] or not (rejected or r.utcnow()>=current['expires_at']):
            refuse('RECOVERY_OPERATION_ACTIVE',409)
        previous=current
    elif prior:refuse('RECOVERY_CONTEXT_MISMATCH',409)
    if session.execute(select(table.c.id).where(table.c.station_id==swap['station_id'],
            table.c.protocol_version.is_distinct_from('0.3'),table.c.consumed_at.is_(None),
            table.c.cancelled_at.is_(None))).first():
        refuse('QUIESCENCE_REQUIRED',409)
    new=r.assets.get_row(session,db,'batteries',swap['new_battery_id'])
    dev=r.assets.available_device(session,db,swap['station_id'])
    if not dev or not dev['enabled']:refuse()
    before=audit_snapshot(session,db,case)
    now=r.utcnow();identity=uuid4()
    authority(session,db,actor,swap,tokens,'TECHNICIAN')
    context=jsonable_encoder(dict(protocol_version='0.3',purpose='VERIFY_NO_DELIVERY',operation_id=identity,
        case_id=case['id'],swap_id=swap['id'],station_id=swap['station_id'],device_id=dev['id'],
        customer_id=swap['customer_id'],created_by=actor['user']['id'],new_battery_id=new['id'],
        expected_serial=new['serial'],supply_compartment_id=swap['supply_compartment_id'],
        return_compartment_id=swap['return_compartment_id'],base_case_version=case['version'],
        base_swap_version=swap['version'],created_at=now.isoformat().replace('+00:00','Z'),
        expires_at=(now+timedelta(seconds=120)).isoformat().replace('+00:00','Z')))
    if previous:context.update(predecessor_id=str(previous['id']),predecessor_context_hash=previous['context_hash'])
    context['context_hash']=canonical_hash(context)
    dto.P8NDContext.model_validate(context)
    if previous:
        session.execute(update(table).where(table.c.id==previous['id']).values(cancelled_at=now))
    session.execute(insert(table).values(id=identity,protocol_version='0.3',purpose='VERIFY_NO_DELIVERY',
        case_id=case['id'],swap_id=swap['id'],station_id=swap['station_id'],customer_id=swap['customer_id'],
        created_by=actor['user']['id'],pin_id=new['id'],expected_serial=new['serial'],context=context,
        context_hash=context['context_hash'],created_at=now,expires_at=now+timedelta(seconds=120),
        base_case_version=case['version'],base_swap_version=swap['version'],supersedes_id=prior))
    case=r.change_case(session,db,case,operation_id=identity,assigned_to=actor['user']['id'],new_pin_delivered='UNKNOWN')
    op=r.assets.get_row(session,db,'recovery_operations',identity)
    audit(session,db,actor['user'],case,'ND_SUCCESSOR_LINKED' if previous else 'ND_OPERATION_CREATED',before,operation_id=identity)
    authority(session,db,actor,swap,tokens,'TECHNICIAN')
    return get(session,db,actor,swap,case,op)


def confirmation(request,session,actor,key,swap_id,body):
    def execute(db,swap,case,charge,tokens):
        op=operation(session,db,swap,case,body.operation_id)
        identity=human(session,db,actor,swap,case,op,body,tokens,'CUSTOMER')
        return {'id':identity,'operation_id':op['id'],'accepted':True,'confirmed':body.confirm}
    return protected(request,session,actor,key,swap_id,body,201,'CUSTOMER',execute)


def human(session,db,actor,swap,case,op,body,tokens,source):
    if (body.stage!=STAGE or body.context_hash!=op['context_hash']
            or actor['user']['id']!=op['created_by' if source=='TECHNICIAN' else 'customer_id']):
        refuse('RECOVERY_CONTEXT_MISMATCH',409)
    proof=r.assets.get_row(session,db,'recovery_attestations',body.receipt_id)
    if (proof['operation_id']!=op['id'] or proof['stage']!=STAGE or proof['source_kind']!='SIMULATOR'
            or proof['payload_hash']!=body.receipt_hash):refuse('RECOVERY_CONTEXT_MISMATCH',409)
    if source=='TECHNICIAN' and body.actual_serial!=op['expected_serial']:refuse()
    table=db.table('recovery_attestations')
    if session.execute(select(table.c.id).where(table.c.operation_id==op['id'],table.c.stage==STAGE,
                                               table.c.source_kind==source)).first():
        refuse('RECOVERY_ATTESTATION_EXISTS',409)
    # Independent currentness/history validation is required even for a REJECT;
    # the statement attaches to this current observation, never a stale boot.
    validate_observation(session,db,swap,case,op,proof['payload'])
    before=audit_snapshot(session,db,case)
    authority(session,db,actor,swap,tokens,source)
    now=r.utcnow();r.open_operation(op)
    if not all(r.assets.fresh(t,now,swap['policy_snapshot']) for t in (proof['observed_at'],proof['received_at'])):
        refuse('EVENT_STALE')
    confirmed=body.observation=='CONFIRM' if source=='TECHNICIAN' else body.confirm
    payload=dict(protocol_version='0.3',stage=STAGE,context_hash=op['context_hash'],
        receipt_id=str(proof['id']),receipt_hash=proof['payload_hash'],actual_serial=op['expected_serial'],
        confirm=confirmed,auth_session_id=str(actor['session']['id']))
    identity=uuid4()
    session.execute(insert(table).values(id=identity,event_id=uuid4(),operation_id=op['id'],stage=STAGE,
        reference_receipt_id=proof['id'],source_kind=source,actor_user_id=actor['user']['id'],
        observed_at=now,received_at=now,payload=payload,payload_hash=canonical_hash(payload)))
    case=r.change_case(session,db,case,new_pin_delivered='UNKNOWN')
    audit(session,db,actor['user'],case,'ND_HUMAN_ATTESTED',before,operation_id=op['id'],attestation_id=identity,confirmed=confirmed)
    validate_observation(session,db,swap,case,op,proof['payload'])
    authority(session,db,actor,swap,tokens,source)
    r.open_operation(op)
    if not all(r.assets.fresh(t,r.utcnow(),swap['policy_snapshot']) for t in (proof['observed_at'],proof['received_at'])):
        refuse('EVENT_STALE')
    return identity


def certificate_proof(session,db,swap,case,op,tokens):
    proof=rows(session,db,op['id']);by_source={p['source_kind']:p for p in proof}
    if len(proof)!=3 or set(by_source)!={'SIMULATOR','TECHNICIAN','CUSTOMER'}:refuse()
    sim=by_source['SIMULATOR']
    packet,dev=validate_observation(session,db,swap,case,op,sim['payload'])
    for p in proof:
        if p['payload_hash']!=canonical_hash(p['payload']):refuse()
        if p['source_kind']!='SIMULATOR':
            role=p['source_kind'];expected=op['created_by' if role=='TECHNICIAN' else 'customer_id']
            if (p['actor_user_id']!=expected or p['reference_receipt_id']!=sim['id']
                    or p['payload'].get('confirm') is not True or p['payload'].get('context_hash')!=op['context_hash']
                    or p['payload'].get('receipt_hash')!=sim['payload_hash']
                    or p['payload'].get('actual_serial')!=op['expected_serial'] or p['observed_at']<sim['received_at']):refuse()
            sid=UUID(p['payload']['auth_session_id'])
            authority(session,db,{'user':{'id':expected},'session':{'id':sid}},swap,tokens,role)
    now=r.utcnow();r.open_operation(op)
    if any(not op['created_at']<=p['observed_at']<=p['received_at']<=now for p in proof):refuse('EVENT_STALE')
    until=min([op['expires_at']]+[p[k]+timedelta(seconds=15) for p in proof for k in ('observed_at','received_at')])
    if now>=until:refuse('EVENT_STALE')
    return by_source,packet,dev,until


def issue_certificate(session,db,actor,swap,case,op,reference,charge,tokens):
    if actor['user']['id']!=op['created_by']:refuse('FORBIDDEN',403)
    if (not charge or charge['state']!='SUCCEEDED' or not charge['verified_at'] or not charge['provider_reference']
            or charge['currency']!='VND' or charge['amount_minor']!=swap['amount_minor']):refuse('STATE_CONFLICT',409)
    proof,packet,dev,until=certificate_proof(session,db,swap,case,op,tokens)
    sim=proof['SIMULATOR']
    if (reference.context_hash!=op['context_hash'] or reference.stage!=STAGE
            or reference.receipt_id!=sim['id'] or reference.receipt_hash!=sim['payload_hash']):
        refuse('RECOVERY_CONTEXT_MISMATCH',409)
    table=db.table('refund_eligibility_certificates')
    if session.execute(select(table.c.id).where(table.c.operation_id==op['id'])).first():refuse('STATE_CONFLICT',409)
    before=audit_snapshot(session,db,case)
    authority(session,db,actor,swap,tokens,'TECHNICIAN')
    now=r.utcnow()
    if now>=until:refuse('EVENT_STALE')
    case=r.change_case(session,db,case,state='EVIDENCE_RECORDED',new_pin_delivered='NO')
    identity=uuid4();q=packet.quiescence
    certificate=dto.P8NDEligibilityCertificate.model_validate(jsonable_encoder(dict(protocol_version='0.3',
        certificate_id=identity,operation_id=op['id'],context_hash=op['context_hash'],case_id=case['id'],
        case_version=case['version'],swap_id=swap['id'],swap_version=swap['version'],payment_id=charge['id'],
        station_id=swap['station_id'],device_id=dev['id'],boot_id=dev['boot_id'],serial=op['expected_serial'],
        receipt_id=sim['id'],receipt_hash=sim['payload_hash'],technician_attestation_id=proof['TECHNICIAN']['id'],
        customer_attestation_id=proof['CUSTOMER']['id'],ledger_id=q.ledger_id,fence_generation=q.fence_generation,
        command_digest=q.command_digest,service_digest=q.service_digest,validated_at=now,valid_until=until,
        new_pin_delivered='NO',effect_count_delta=0))).model_dump(mode='json')
    session.execute(insert(table).values(id=identity,operation_id=op['id'],payment_id=charge['id'],
        receipt_id=sim['id'],technician_attestation_id=proof['TECHNICIAN']['id'],customer_attestation_id=proof['CUSTOMER']['id'],
        issued_by=actor['user']['id'],issuer_session_id=actor['session']['id'],validated_at=now,valid_until=until,
        payload=certificate,payload_hash=canonical_hash(certificate)))
    audit(session,db,actor['user'],case,'ND_CERTIFICATE_ISSUED',before,certificate_id=identity,operation_id=op['id'])
    authority(session,db,actor,swap,tokens,'TECHNICIAN')
    certificate_proof(session,db,swap,case,op,tokens)


def revoke_contradictions(session,db,device_id,event_id):
    """Accepted worker projection only, under the existing station mutex.

    Pending inbox and refused packets do not revoke facts. Expiration is never
    renewed; a boot/model contradiction invalidates the immutable certificate
    by a new append-only row, not an UPDATE or financial/custody compensation.
    """
    if 'refund_certificate_revocations' not in db.tables:return
    certs=db.table('refund_eligibility_certificates');ops=db.table('recovery_operations')
    dev=r.assets.get_row(session,db,'devices',device_id)
    revocations=db.table('refund_certificate_revocations')
    for cert in session.execute(select(certs).join(ops,certs.c.operation_id==ops.c.id)
        .where(ops.c.station_id==dev['station_id'],~select(revocations.c.id).where(
            revocations.c.certificate_id==certs.c.id).exists())).mappings().all():
        op=r.assets.get_row(session,db,'recovery_operations',cert['operation_id'])
        slot=r.assets.get_row(session,db,'compartments',UUID(op['context']['supply_compartment_id']))
        pin=r.assets.get_row(session,db,'batteries',UUID(op['context']['new_battery_id']))
        commands=db.table('device_commands')
        uncertain=session.execute(select(commands.c.id).where(commands.c.device_id==dev['id'],
                                                              commands.c.state=='UNKNOWN')).first()
        event=r.assets.get_row(session,db,'device_events',event_id)
        accepted_uncertainty=(event['kind']=='COMMAND_ACK' and event['payload'].get('result')=='UNKNOWN')
        conflict=(not dev['enabled'] or str(dev['boot_id'])!=cert['payload']['boot_id'] or uncertain or accepted_uncertainty
            or slot['door_state']!='CLOSED' or not slot['observed_present']
            or slot['observed_serial']!=cert['payload']['serial'] or pin['compartment_id']!=slot['id']
            or pin['holder_user_id'] is not None or pin['location_kind']!='COMPARTMENT')
        if not conflict:continue
        case=r.case_for(session,db,op['swap_id']);before=audit_snapshot(session,db,case)
        session.execute(insert(revocations).values(id=uuid4(),certificate_id=cert['id'],
            revoked_at=r.utcnow(),reason_code='CURRENT_PROJECTION_CONTRADICTION',source_event_id=event_id,
            correlation_id=case['swap_id']))
        if case['new_pin_delivered']=='NO':case=r.change_case(session,db,case,new_pin_delivered='UNKNOWN')
        audit(session,db,dev,case,'ND_CERTIFICATE_REVOKED',before,certificate_id=cert['id'],source_event_id=event_id)


def validate_observation(session,db,swap,case,op,packet):
    """Reconstruct captured history from persisted facts, then validate currentness.

    A current serial/complete scalar/ACK is never sufficient. Current safe
    heartbeat/telemetry suffixes cannot renew the receipt's freshness deadline.
    """
    body=dto.P8NDObservation.model_validate(packet)
    dev=r.assets.available_device(session,db,swap['station_id'])
    if (not dev or not dev['enabled'] or body.device_id!=dev['id'] or body.boot_id!=dev['boot_id']
            or op['context']['device_id']!=str(dev['id']) or body.operation_id!=op['id']
            or body.context_hash!=op['context_hash'] or body.actual_serial!=op['expected_serial']
            or body.supply_compartment_id!=swap['supply_compartment_id'] or op['base_swap_version']!=swap['version']):refuse()
    events=db.table('device_events')
    all_events=session.execute(select(events).where(events.c.device_id==dev['id'])
                              .order_by(events.c.observed_at,events.c.id)).mappings().all()
    # Only explicit immutable seed telemetry is outside actual Simulator history.
    actual=[e for e in all_events if e['processing_error']!='SIMULATION_SEED_UNVERIFIED']
    if any(not e['accepted'] or not e['processed_at'] for e in actual):refuse('QUIESCENCE_REQUIRED',409)
    # A terminal command row is historical disposition, not permission to ignore
    # a newly accepted conflicting source. 0.3 cannot resolve UNKNOWN by keeping
    # the earlier NACK/ACK row or looking only at the captured prefix digest.
    if any(e['kind']=='COMMAND_ACK' and e['payload'].get('result')=='UNKNOWN' for e in actual):
        refuse('QUIESCENCE_REQUIRED',409)
    event_ids=[str(e['id']) for e in actual]
    listed=[str(i) for i in body.delivery_history.event_ids]
    if (len(listed)!=len(set(listed)) or not listed or event_ids[:len(listed)]!=listed):
        refuse('QUIESCENCE_REQUIRED',409)
    captured=actual[:len(listed)]
    snapshot=next((e for e in captured if e['id']==body.snapshot_event_id),None)
    if (not snapshot or snapshot['kind']!='SNAPSHOT' or snapshot['boot_id']!=dev['boot_id']
            or snapshot['payload_hash']!=body.snapshot_hash or snapshot['observed_at']>body.observed_at
            or body.seq<=snapshot['seq'] or list(dict.fromkeys(str(e['boot_id']) for e in captured))!=
                [str(i) for i in body.delivery_history.boot_ids]):refuse()
    quiescence=body.quiescence;history=body.delivery_history
    if (quiescence.watermark_event_id!=snapshot['id'] or quiescence.watermark_hash!=snapshot['payload_hash']
            or history.swap_id!=swap['id'] or history.serial!=op['expected_serial']):refuse()
    slot=r.assets.get_row(session,db,'compartments',swap['supply_compartment_id'])
    pin=r.assets.get_row(session,db,'batteries',swap['new_battery_id'])
    latest=r.assets.snapshot(session,db,dev,r.utcnow())
    original=next((s for s in snapshot['payload']['slots'] if s['compartment_id']==str(slot['id'])),None)
    current=next((s for s in latest['payload']['slots'] if s['compartment_id']==str(slot['id'])),None) if latest else None
    if (not original or not current or current!=original or original['door_state']!='CLOSED'
            or original['present'] is not True or original['observed_serial']!=op['expected_serial']
            or pin['serial']!=op['expected_serial'] or pin['compartment_id']!=slot['id']
            or pin['holder_user_id'] is not None or pin['location_kind']!='COMPARTMENT'
            or slot['door_state']!='CLOSED' or not slot['observed_present']
            or slot['observed_serial']!=pin['serial'] or not r.assets.current_observation(session,db,dev,slot)):
        refuse()
    commands=db.table('device_commands')
    known=session.execute(select(commands).where(commands.c.device_id==dev['id']).order_by(commands.c.id)).mappings().all()
    entries={e.id:e for e in body.command_entries}
    if len(entries)!=len(body.command_entries):refuse('QUIESCENCE_REQUIRED',409)
    if not set(entries).issubset({c['id'] for c in known}):refuse('QUIESCENCE_REQUIRED',409)
    denied=set(quiescence.denied_command_ids)
    if len(denied)!=len(quiescence.denied_command_ids):refuse('QUIESCENCE_REQUIRED',409)
    for command in known:
        if command['state']=='UNKNOWN':refuse('QUIESCENCE_REQUIRED',409)
        item=entries.get(command['id'])
        if item is None:
            # Never-dispatched QUEUED/EXPIRED issuer facts are independently
            # protected by station fence. DISPATCHED is never guessed absent.
            if command['state'] not in ('QUEUED','EXPIRED'):refuse('QUIESCENCE_REQUIRED',409)
            continue
        if command['id'] not in denied or item.status=='UNKNOWN':refuse('QUIESCENCE_REQUIRED',409)
        try:original_command=json.loads(item.body)
        except (ValueError,TypeError):refuse()
        keys=('id','device_id','swap_id','compartment_id','kind','expires_at','payload')
        try:raw={k:original_command[k] for k in keys}
        except KeyError:refuse()
        expected={k:jsonable_encoder(command[k]) for k in keys}
        if (raw!=expected or item.hash!=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()
                or (item.status,item.effects) not in (('EXECUTED',1),('NOT_EXECUTED',0))):refuse()
        chain=[e for e in actual if e['command_id']==command['id']]
        if not item.effects and any(e['kind'] in ('DOOR','PRESENCE') for e in chain):
            refuse('QUIESCENCE_REQUIRED',409)
        if item.effects and not any(e['kind']=='PRESENCE' for e in chain):refuse('QUIESCENCE_REQUIRED',409)
        if (command['kind']=='OPEN_SUPPLY' and command['payload']['expected_serial']==pin['serial']
                and any(e['kind']=='PRESENCE' and e['payload']['present'] is False for e in chain)):
            refuse()
    # Snapshot command ledger is a separate authenticated source. Match exact
    # entries without silently discarding duplicate identities.
    snapshot_ledger=snapshot['payload']['command_ledger']
    if len({e['command_id'] for e in snapshot_ledger})!=len(snapshot_ledger):refuse()
    if {e['command_id']:e['status'] for e in snapshot_ledger}!={str(e.id):e.status for e in body.command_entries}:
        refuse('QUIESCENCE_REQUIRED',409)
    command_digest=canonical_hash([e.model_dump(mode='json') for e in body.command_entries])
    service_digest=canonical_hash([e.model_dump(mode='json') for e in body.service_entries])
    operations=db.table('recovery_operations');attestations=db.table('recovery_attestations')
    service_proofs=session.execute(select(attestations).join(operations,attestations.c.operation_id==operations.c.id)
        .where(operations.c.station_id==swap['station_id'],attestations.c.source_kind=='SIMULATOR',
               attestations.c.stage.in_(['LEGACY','POST_ACTION_RECEIPT']))).mappings().all()
    by_event={p['event_id']:p for p in service_proofs}
    if (len({e.operation_id for e in body.service_entries})!=len(body.service_entries)
            or {e.receipt_event_id for e in body.service_entries}!=set(by_event)):
        refuse('QUIESCENCE_REQUIRED',409)
    for entry in body.service_entries:
        if entry.state not in ('OBSERVED','REJECTED') or not entry.durably_disabled:refuse('QUIESCENCE_REQUIRED',409)
        proof=by_event[entry.receipt_event_id]
        original_op=r.assets.get_row(session,db,'recovery_operations',entry.operation_id)
        if (proof['operation_id']!=entry.operation_id or original_op['context_hash']!=entry.context_hash
                or original_op['purpose']!=entry.purpose or not original_op['consumed_at']):refuse('QUIESCENCE_REQUIRED',409)
        observed=proof['payload'].get('actual_serial')
        if entry.effects and observed==pin['serial']:refuse()
        if proof['payload_hash']!=canonical_hash(proof['payload']):refuse()
    activations=db.table('recovery_action_activations')
    expected_activations=set(session.scalars(select(activations.c.id).join(operations,activations.c.operation_id==operations.c.id)
        .where(operations.c.station_id==swap['station_id'])))
    if expected_activations!=set(quiescence.denied_activation_ids):refuse('QUIESCENCE_REQUIRED',409)
    if (quiescence.command_digest!=command_digest or quiescence.service_digest!=service_digest
            or history.journal_hash!=history_digest(quiescence.ledger_id,swap['id'],pin['serial'],
                [{'event_id':e['id'],'boot_id':e['boot_id'],'seq':e['seq'],'payload_hash':e['payload_hash']} for e in captured],
                command_digest,service_digest)):refuse('QUIESCENCE_REQUIRED',409)
    now=r.utcnow();r.open_operation(op)
    if not all(r.assets.fresh(t,now,swap['policy_snapshot']) for t in
        (body.observed_at,snapshot['observed_at'],snapshot['received_at'],slot['observed_at'],dev['last_received_at'])):
        refuse('EVENT_STALE')
    if not op['created_at']<=body.observed_at<=now:refuse('EVENT_STALE')
    return body,dev


def receive(session,db,actor,body):
    r.assets.station_lock(session,db,actor['station_id'])
    dev=r.assets.get_row(session,db,'devices',actor['id'],lock=True)
    if not dev['enabled'] or dev['key_hash']!=actor['key_hash']:refuse('DEVICE_DISABLED',403)
    inbox=db.table('recovery_inspection_inbox');packet=body.model_dump(mode='json',exclude_unset=True)
    hashed=canonical_hash(packet)
    prior=session.execute(select(inbox).where(inbox.c.event_id==body.event_id)).mappings().first()
    if prior:
        if prior['device_id']!=dev['id'] or prior['payload_hash']!=hashed:refuse('IDEMPOTENCY_CONFLICT',409)
        result=dict(prior['response'])
        if prior['status']==202:result['duplicate']=True
        return JSONResponse(result,status_code=prior['status'])
    try:
        with session.begin_nested():
            initial=r.assets.get_row(session,db,'recovery_operations',body.operation_id)
            if initial['station_id']!=dev['station_id']:refuse('DEVICE_STATION_FORBIDDEN',403)
            swap,case=r.lock_context(session,db,initial['swap_id'])
            op=operation(session,db,swap,case,body.operation_id)
            proof_table=db.table('recovery_attestations')
            if session.execute(select(proof_table.c.id).where(proof_table.c.operation_id==op['id'],
                    proof_table.c.stage==STAGE,proof_table.c.source_kind=='SIMULATOR')).first():
                refuse('RECOVERY_ATTESTATION_EXISTS',409)
            _,dev=validate_observation(session,db,swap,case,op,packet)
            highwater=[]
            for name,boot,seq,time in (('recovery_attestations','source_boot','source_seq','observed_at'),
                ('recovery_authorization_acks','boot_id','seq','observed_at'),
                ('recovery_closure_receipts','boot_id','seq','observed_at')):
                table=db.table(name)
                highwater.extend(session.execute(select(table.c[seq],table.c[time]).where(table.c.device_id==dev['id'],
                    table.c[boot]==body.boot_id)).all())
            if any(body.seq<=seq or body.observed_at<=time for seq,time in highwater):refuse('EVENT_OUT_OF_ORDER')
            before=audit_snapshot(session,db,case);now=r.utcnow()
            identity=uuid4()
            session.execute(insert(proof_table).values(id=identity,event_id=body.event_id,operation_id=op['id'],
                stage=STAGE,source_kind='SIMULATOR',device_id=dev['id'],observed_at=body.observed_at,
                received_at=now,payload=packet,payload_hash=hashed,source_boot=body.boot_id,
                source_seq=body.seq,source_event_id=body.snapshot_event_id))
            case=r.change_case(session,db,case,evidence_event_id=body.snapshot_event_id,new_pin_delivered='UNKNOWN')
            audit(session,db,dev,case,'ND_INSPECTION_ACCEPTED',before,operation_id=op['id'],attestation_id=identity)
            validate_observation(session,db,swap,case,op,packet)
            response={'accepted':True,'duplicate':False,'id':str(identity)};status=202
    except DomainError as exc:
        if exc.status not in (409,422):raise
        status=exc.status;response={'code':exc.code,'message':exc.message,'correlation_id':str(uuid4()),'details':{}}
    session.execute(insert(inbox).values(event_id=body.event_id,device_id=dev['id'],payload_hash=hashed,
                                        payload=packet,status=status,response=response))
    return JSONResponse(jsonable_encoder(response),status_code=status)


def get(session,db,actor,swap,case,op):
    proofs=rows(session,db,op['id'])
    certs=db.table('refund_eligibility_certificates')
    cert=session.execute(select(certs).where(certs.c.operation_id==op['id'])).mappings().first()
    value=dict(protocol_version='0.3',case_id=case['id'],swap_id=swap['id'],version=case['version'],
        new_pin_delivered=case['new_pin_delivered'],old_pin_settled=case['old_pin_settled'],operation=op['context'],
        proofs=[dict(id=p['id'],operation_id=p['operation_id'],source_kind=p['source_kind'],stage=p['stage'],
            payload_hash=p['payload_hash'],reference_receipt_id=p['reference_receipt_id'],
            observed_at=p['observed_at'],received_at=p['received_at'],confirmed=p['payload'].get('confirm')) for p in proofs],
        certificate=cert['payload'] if cert else None)
    return dto.P8NDNoDeliveryResponse.model_validate(jsonable_encoder(value)).model_dump(mode='json',exclude_unset=True)


def project(session,db,swap,case,op):
    if (op['case_id']!=case['id'] or op['swap_id']!=swap['id'] or op['station_id']!=swap['station_id']
            or op['customer_id']!=swap['customer_id'] or op['purpose']!='VERIFY_NO_DELIVERY'):return None
    proof=rows(session,db,op['id']);sim=next((p for p in proof if p['source_kind']=='SIMULATOR'),None)
    human=next((p for p in proof if p['source_kind']=='CUSTOMER'),None)
    state='UNAVAILABLE'
    if op['consumed_at']:state='CONSUMED'
    elif op['cancelled_at']:state='REVOKED'
    elif r.utcnow()>=op['expires_at']:state='EXPIRED'
    elif human:state='CONFIRMED' if human['payload'].get('confirm') is True else 'REJECTED'
    elif sim:
        try:validate_observation(session,db,swap,case,op,sim['payload']);state='AVAILABLE'
        except DomainError:pass
    return dto.P8NDCustomerProjection.model_validate(jsonable_encoder(dict(protocol_version='0.3',purpose='VERIFY_NO_DELIVERY',
        operation_id=op['id'],context_hash=op['context_hash'],stage=STAGE,receipt_id=sim['id'] if sim else None,
        receipt_hash=sim['payload_hash'] if sim else None,expires_at=op['expires_at'],expected_serial=op['expected_serial'],
        confirmation_status=state))).model_dump(mode='json')
