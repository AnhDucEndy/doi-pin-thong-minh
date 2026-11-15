"""Read-only audit of retained Playwright fixtures; never creates physical proof."""
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import sys
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'services/backend'),str(ROOT/'tools')]
from sqlalchemy import select, text
from app.config import Settings
from app.infrastructure.db import Database
from smoke_phase4 import fingerprints


def run(destination, prefix='playwright_fixture_*'):
    if prefix not in ('playwright_fixture_*','terminal_fix_*'):
        raise ValueError('Unsupported Browser report group')
    settings=Settings.from_env()
    demo=Database(settings)
    before=fingerprints(demo)
    records=[]
    try:
        for source in sorted((ROOT/'docs/PHASE8A_TESTS').glob(prefix+'/reports/PHASE8A_E2E_E.json')):
            original=json.loads(source.read_text(encoding='utf-8'))
            schema=original['schema']
            if not schema.startswith('phase5_test_'):
                raise ValueError('Only retained test schemas may be audited')
            runtime=(ROOT/original['runtime']).resolve()
            if not runtime.is_relative_to(ROOT/'.cache'):
                raise ValueError('Only retained workspace runtime ledgers may be audited')
            identity=UUID(json.loads((runtime/'manual.json').read_text())['swap_id'])
            db=Database(replace(settings,schema=schema))
            try:
                with db.sessions() as session:
                    session.execute(text('SET TRANSACTION READ ONLY'))
                    def rows(name):
                        table=db.table(name)
                        return session.execute(select(table).where(table.c.swap_id==identity)).mappings().all()
                    commands=rows('device_commands')
                    case=rows('recovery_cases')[0]
                    swap=session.execute(select(db.table('swap_transactions')).where(
                        db.table('swap_transactions').c.id==identity)).mappings().one()
                    assert swap['state']=='REVIEW_REQUIRED'
                    batteries=db.table('batteries')
                    custody=session.execute(select(batteries).where(batteries.c.id.in_(
                        [swap['old_battery_id'],swap['new_battery_id']]))).mappings().all()
                    by_id={row['id']:row for row in custody}
                    assert by_id[swap['old_battery_id']]['location_kind']=='CUSTOMER'
                    assert by_id[swap['old_battery_id']]['holder_user_id']==swap['customer_id']
                    assert by_id[swap['new_battery_id']]['location_kind']=='COMPARTMENT'
                    audits=session.execute(select(db.table('audit_events').c.action).where(
                        db.table('audit_events').c.correlation_id==identity)).scalars().all()
                    operation=db.table('recovery_operations')
                    ops=session.execute(select(operation).where(operation.c.case_id==case['id'])).mappings().all()
                    proof=db.table('recovery_attestations')
                    proofs=session.execute(select(proof).where(proof.c.operation_id.in_([op['id'] for op in ops]))).mappings().all()
                    keys=[(p['operation_id'],p['stage'],p['source_kind']) for p in proofs]
                    assert len(keys)==len(set(keys)), 'Duplicate accepted proof'
                    assert not any(c['kind']=='OPEN_SUPPLY' for c in commands)
                    assert [p['state'] for p in rows('payments')]==['SUCCEEDED']
                    assert sum(h['released_at'] is None for h in rows('resource_reservations'))==3
                    assert not case['old_pin_settled']
                    assert case['new_pin_delivered']=='UNKNOWN'
                    record={'source':str(source.relative_to(ROOT)),'schema':schema,
                        'browser_exit':original['browser_exit'],
                        'swap_state':swap['state'],'case_version':case['version'],
                        'case_state':case['state'],'payment':['SUCCEEDED'],'active_holds':3,
                        'old_pin_settled':case['old_pin_settled'],'new_pin_delivered':case['new_pin_delivered'],
                        'custody':[{k:b[k] for k in ('id','location_kind','holder_user_id','compartment_id')} for b in custody],
                        'command_states':[{k:c[k] for k in ('id','kind','state')} for c in commands],
                        'success_audits':dict(Counter(audits)),
                        'accepted_proof':[{**{k:p[k] for k in ('id','operation_id','stage','source_kind','payload_hash','observed_at')},
                            **{k:p['payload'].get(k) for k in ('result','confirm','actual_serial','recipient_id')}} for p in proofs]}
                    assert Counter(audits)['FOREIGN_OBJECT_RETURN_SETTLED']<=1
                    assert Counter(audits)['RECOVERY_NO_EFFECT_CLOSED']<=1
                with sqlite3.connect((runtime/'ledgers/S01.sqlite3').as_uri()+'?mode=ro',uri=True) as ledger:
                    tables={row[0] for row in ledger.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    record['command_effects']=ledger.execute('SELECT id,status,effects FROM commands').fetchall()
                    record['service_effects']=ledger.execute('SELECT state,effects FROM service_operations').fetchall() if 'service_operations' in tables else None
                    record['fence']=ledger.execute('SELECT state FROM recovery_station_fence').fetchall() if 'recovery_station_fence' in tables else None
                assert all(row[2]<=1 for row in record['command_effects'])
                if record['service_effects'] is not None:
                    assert all(row[1]<=1 for row in record['service_effects'])
                    assert sum(row[1] for row in record['service_effects'])<=1
                records.append(record)
            finally:
                db.engine.dispose()
        assert fingerprints(demo)==before
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('x',encoding='utf-8') as output:
            json.dump({'read_only':True,'fixture_count':len(records),'demo_fingerprint_scope':'8 runner tables',
                       'demo_fingerprint_unchanged':True,'records':records},output,default=str,indent=2)
        print(f'Read-only audit completed: {len(records)} retained Browser fixtures')
    finally:
        demo.engine.dispose()


if __name__=='__main__':
    run(Path(sys.argv[1]).resolve(),sys.argv[2] if len(sys.argv)>2 else 'playwright_fixture_*')
