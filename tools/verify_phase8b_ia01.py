"""Read-only collection/artifact validation; never resets data or rewrites evidence."""
import ast
import contextlib
import hashlib
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'services/backend'),str(ROOT/'tests'),str(ROOT)]
PRIOR=ROOT/'docs/PHASE8B_TESTS/b1a_deadlock_collection_20261117.json'


def read(p):return json.loads(p.read_text(encoding='utf8'))


def write(p,value):
    with p.open('x',encoding='utf8') as f:json.dump(value,f,indent=2)


def collect(output):
    import pytest
    prior=read(PRIOR);ids=[]
    class Collector:
        def pytest_collection_finish(self,session):ids.extend(v.nodeid for v in session.items)
    with output.with_suffix('.log').open('x',encoding='utf8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        code=int(pytest.main([*prior['test_paths'],'--collect-only','-q'],plugins=[Collector()]))
    result={'exit_code':code,'count':len(ids),'test_ids':ids,'test_paths':prior['test_paths'],
        'missing':sorted(set(prior['test_ids'])-set(ids)),'extra':sorted(set(ids)-set(prior['test_ids']))}
    write(output,result)
    assert code==0 and not result['missing'] and not result['extra'] and len(ids)==543,result
    print('Collection: exact original543 IDs, no missing/extra')


def validate(label):
    folder=ROOT/'docs/PHASE8B_TESTS'/label
    prior=read(PRIOR);status=read(folder/'exit.json')
    root=ET.parse(folder/'results.xml').getroot();cases=list(root.iter('testcase'))
    actual={(n.attrib['classname'],n.attrib['name']) for n in cases}
    expected={(v.split('::')[0][:-3].replace('/','.'),'::'.join(v.split('::')[1:])) for v in prior['test_ids']}
    before=read(folder/'source_before.json');after=read(folder/'source_after.json')
    delta=[v['path'] for v in before if hashlib.sha256((ROOT/v['path']).read_bytes()).hexdigest().upper()!=v['sha256'].upper()]
    capture=read(folder/'reports/PHASE8B_TESTS/deadlock_detail.json')
    # Read the old finding's source manifest, never rewrite its evidence/probe.
    old=read(ROOT/'docs/PHASE8B_TESTS/b1a_independent_review_20261117_03/source_before.json')
    probe='tests/test_phase8b_independent_review.py'
    oldhash=next(v['sha256'] for v in old if v['path']==probe)
    probe_unchanged=hashlib.sha256((ROOT/probe).read_bytes()).hexdigest().upper()==oldhash.upper()
    callers=[]
    for p in (ROOT/'services/backend/app').rglob('*.py'):
        tree=ast.parse(p.read_text(encoding='utf8'))
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,(ast.Attribute,ast.Name)):
                name=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id
                if name in ('station_lock','station_locks'):
                    callers.append({'path':p.relative_to(ROOT).as_posix(),'line':n.lineno,'helper':name})
    result={'exit_code':status['exit_code'],'tests':len(cases),'unique_ids':len(actual),
        'failures':len(list(root.iter('failure'))),'errors':len(list(root.iter('error'))),'skipped':len(list(root.iter('skipped'))),
        'original_543_missing':sorted(expected-actual),'unexpected_ids':sorted(actual-expected),
        'source_count':len(before),'source_before_after_equal':before==after,'current_source_delta':delta,
        'original_failing_probe_unchanged':probe_unchanged,'demo_eight_tables_and_revision_unchanged':status['demo_fingerprint_unchanged'],
        'deadlocks':capture['deadlocks'],'lock_counts':capture['executed_lock_counts'],'station_callers':callers,
        'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write(folder/'validation.public.json',result)
    assert status['exit_code']==0 and len(cases)==len(actual)==543 and actual==expected
    assert not result['failures'] and not result['errors'] and not result['skipped']
    assert before==after and not delta and probe_unchanged and not capture['deadlocks'] and status['demo_fingerprint_unchanged']
    print('Validated543, original IDs/probe, current hashes, no40P01, unchanged demo8')


if __name__=='__main__':
    if sys.argv[1]=='collect':collect(Path(sys.argv[2]))
    else:validate(sys.argv[1])
