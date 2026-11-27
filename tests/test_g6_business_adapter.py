"""Focused safety controls: synthetic catalog facts/mock HTTP, no DB or workflow."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json

import httpx
import pytest

from tools.g6_business.adapter import (Config, CLUSTER, Denied, PendingIntegration,
    Supervisor, check_endpoint, client, validate_catalog)

ROOT = Path(__file__).resolve().parents[1]


def config():
    return Config('abcdef123456', 'phase5_test_abcdef123456', 'g6r_abcdef123456',
        'g6_laptop', CLUSTER, (18765,), ((18765, 'GET', '/health'),))


def facts():
    return dict(system_identifier=CLUSTER, database='g6_laptop', schema=config().schema,
        role=config().role, revision='0010_no_delivery_eligibility',
        owner_marker='g6_business:'+config().run_id, schema_owner='dedicated_owner',
        role_flags=[False]*6, memberships=[], cross_schema_privileges=[],
        cross_schema_definers=[], schema_create=False, public_create=False,
        audit_privileges=[True,True,False,False,False], audit_trigger=True,
        runtime_plan_verified=True)


def test_positive_config_and_synthetic_catalog():
    assert config().validate() and validate_catalog(config(), facts())


@pytest.mark.parametrize('key,value', [('system_identifier','wrong'),('schema','phase5_test_ecfa77274ae3'),
    ('role','doi_pin_runtime'),('owner_marker','old'),('role_flags',[True]),
    ('memberships',['owner']),('cross_schema_privileges',['historical']),
    ('cross_schema_definers',['unsafe']),('schema_create',True),('public_create',True),
    ('audit_privileges',[True]*5),('runtime_plan_verified',False)])
def test_catalog_refusals(key,value):
    f=facts();f[key]=value
    with pytest.raises(Denied): validate_catalog(config(), f)


@pytest.mark.parametrize('changes', [dict(schema='phase5_test_ecfa77274ae3'),
    dict(schema='historical'),dict(role='postgres'),dict(ports=()),dict(routes=()),
    dict(system_identifier='7699937118555680806'),dict(run_id='')])
def test_config_refusals(changes):
    with pytest.raises(Denied):replace(config(), **changes).validate()


@pytest.mark.parametrize('host,port',[('127.0.0.1',5432),('127.0.0.1',5448),
    ('127.0.0.1',5449),('127.0.0.1',18766),('example.com',18765),
    ('localhost',18765),('::1',18765)])
def test_endpoint_denied_before_any_transport(host,port):
    with pytest.raises(Denied):check_endpoint(config(),host,port)


def test_real_transport_wrapper_positive_and_secret_free_journal(monkeypatch):
    records=[];calls=[]
    monkeypatch.setenv('HTTP_PROXY','http://invalid.invalid:5432')
    def mock(req):calls.append(req.url.path);return httpx.Response(200,json={'status':'ok'})
    with client(config(),httpx.MockTransport(mock),records.append) as c:
        response=c.get('http://127.0.0.1:18765/health',headers={'Authorization':'Bearer TEST_ONLY_CREDENTIAL'})
    assert response.status_code==200 and calls==['/health']
    assert 'TEST_ONLY_CREDENTIAL' not in json.dumps(records)


@pytest.mark.parametrize('method,path',[('POST','/health'),('GET','/other'),
    ('POST','/mock/v1/refunds'),('GET','/%68ealth'),('GET','/health?x=1')])
def test_route_refusals_do_not_reach_mock(method,path):
    calls=[]
    with client(config(),httpx.MockTransport(lambda req:calls.append(req) or httpx.Response(200)),lambda r:None) as c:
        with pytest.raises(Denied):c.request(method,'http://127.0.0.1:18765'+path)
    assert calls==[]


def test_redirect_refused_not_followed():
    calls=[]
    def mock(req):calls.append(req);return httpx.Response(302,headers={'Location':'http://127.0.0.1:5432/'})
    with client(config(),httpx.MockTransport(mock),lambda r:None) as c:
        with pytest.raises(Denied,match='REDIRECT'):c.get('http://127.0.0.1:18765/health')
    assert len(calls)==1


def supervisor():
    return Supervisor(ROOT,ROOT/'.local/business_adapter_controls'/uuid4().hex,config())


def test_owned_real_control_process_and_wait():
    s=supervisor();p=s.launch_control(ROOT/'tools/g6_business/mock_probe.py')
    assert s.wait(p)==0;s.finish()
    events=[json.loads(x.read_text()) for x in sorted(s.output.glob('event_*.json'))]
    assert events[0]['pid']==p.pid==events[1]['identity']['pid']
    assert events[0]['parent_pid']==events[1]['identity']['parent_pid']


def test_unknown_child_wrong_target_collision_and_historical_ledger():
    s=supervisor()
    with pytest.raises(Denied,match='ENTRYPOINT'):s.launch_control(ROOT/'tools/smoke_phase8b_b1b.py')
    with pytest.raises(Denied,match='NOT_OWNED'):s.terminate(SimpleNamespace(pid=1))
    with pytest.raises(Denied):s.ledger_path('../../historical.sqlite3')
    p=s.ledger_path('owned.sqlite3');p.touch()
    with pytest.raises(Denied,match='LEDGER_REUSE'):s.ledger_path('owned.sqlite3')
    with pytest.raises(Denied,match='OUTPUT_COLLISION'):Supervisor(ROOT,s.output,config())
    with pytest.raises(PendingIntegration):s.launch_business('api')


def test_missing_wait_is_not_complete():
    s=supervisor();p=s.launch_control(ROOT/'tools/g6_business/mock_probe.py')
    try:
        with pytest.raises(Denied,match='MISSING_EXIT_WAIT'):s.finish()
    finally:s.wait(p)
