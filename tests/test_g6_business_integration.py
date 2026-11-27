"""Focused adapter controls; no PostgreSQL fixture or business workflow."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from tools.g6_business.adapter import Config, Denied, PROFILES, check_endpoint
from tools.g6_business.admission import binding, collect_identity, verify_system_acl
from tools.g6_business.native import database_parameters
from tools.g6_business.provision import authority_parameters
from tools.g6_business.integration import IntegrationSupervisor
from tools.g6_business.routes import compile_candidates

ROOT=Path(__file__).resolve().parents[1]


def config(profile='pc'):
    port,identity,db=PROFILES[profile]
    return Config('123456abcdef','phase5_test_123456abcdef','g6r_123456abcdef',db,identity,
                  (18765,),((18765,'GET','/health'),),profile=profile)


@pytest.mark.parametrize('profile',['pc','laptop'])
def test_profiles_separate_database_from_http(profile):
    c=config(profile).validate()
    with pytest.raises(Denied):check_endpoint(c,'127.0.0.1',c.target[0])
    other=config('laptop' if profile=='pc' else 'pc')
    with pytest.raises(Denied):replace(c,database=other.database,system_identifier=other.system_identifier).validate()


@pytest.mark.parametrize('changes',[{'profile':''},{'profile':'custom'},{'role':'doi_pin_runtime'},
    {'schema':'g6_base'},{'schema':'phase5_test_6b200a1e89a6'},{'ports':(5440,)},{'system_identifier':'wrong'}])
def test_no_profile_or_protected_admission(changes):
    with pytest.raises(Denied):replace(config(),**changes).validate()


def params():
    c=config()
    return dict(host='127.0.0.1',port=c.target[0],dbname=c.database,user=c.role,password='synthetic-only')


def test_native_parameters_pin_hostaddr_and_override_options():
    data,extra=database_parameters(config(),'synthetic-only','',{**params(),'options':'-csearch_path=public'})
    assert data['hostaddr']=='127.0.0.1' and 'phase5_test_123456abcdef,pg_catalog' in data['options']
    assert 'default_transaction_read_only=on' in data['options'] and extra=={}


@pytest.mark.parametrize('changes',[{'host':'localhost'},{'host':'::1'},{'hostaddr':'192.0.2.1'},
    {'port':5433},{'port':5449},{'dbname':'postgres'},{'user':'postgres'},{'user':'doi_pin_runtime'},
    {'password':'wrong'},{'service':'inherited'},{'passfile':'private'}])
def test_native_rejects_before_driver(changes):
    with pytest.raises(Denied):database_parameters(config(),'synthetic-only','',{**params(),**changes})


def test_collectors_refuse_wrong_connection_without_identity_query():
    from types import SimpleNamespace
    c=SimpleNamespace(info=SimpleNamespace(host='127.0.0.1',port=5449,dbname=config().database),execute=lambda *a:pytest.fail('Query sent'))
    with pytest.raises(Denied):binding(config(),c)
    with pytest.raises(Denied):collect_identity(config(),c)


def test_stock_control_metadata_is_not_new_admin_authority():
    verify_system_acl(None,[],[])


@pytest.mark.parametrize('args', [('explicit ACL',[],[]),(None,['pg_read_file'],[]),(None,[],['session_replication_role'])])
def test_system_grant_drift_is_denied(args):
    with pytest.raises(Denied):verify_system_acl(*args)


@pytest.mark.parametrize('url',[
    'postgresql+psycopg://postgres:synthetic@127.0.0.1:5449/g6_laptop',
    'postgresql+psycopg://postgres:synthetic@localhost:5448/doi_pin_g6_df268aa6e107',
    'postgresql+psycopg://doi_pin_runtime:synthetic@127.0.0.1:5448/doi_pin_g6_df268aa6e107',
    'postgresql+psycopg://postgres:synthetic@127.0.0.1:5448/doi_pin_g6_df268aa6e107?service=other'])
def test_provision_authority_has_no_fallback(url):
    with pytest.raises(Denied):authority_parameters(config(),url,'postgres')


def test_s1_registry_compiles_actual_routes_without_execution_authority():
    rows=compile_candidates(ROOT,uuid4(),uuid4())
    assert len(rows)==16 and len({(r['method'],r['path']) for r in rows})==16
    assert all(not r['authorized'] and '{' not in r['path'] and len(r['source']['sha256'])==64 for r in rows)
    assert not any('/mock/v1/refunds' in r['path'] for r in rows)
    with pytest.raises(ValueError):compile_candidates(ROOT,'*',uuid4())


def test_actual_owned_abnormal_child_has_explicit_exit_and_no_business_unlock():
    from dataclasses import asdict
    from types import SimpleNamespace
    from tools.g6_business.adapter import PendingIntegration
    output=ROOT/'.local/business_adapter_controls'/uuid4().hex
    output.mkdir(parents=True,exist_ok=False)
    c=replace(config(),ports=(18765,18766),routes=((18765,'GET','/health'),(18766,'GET','/mock/v1/charges/00000000-0000-0000-0000-000000000000')))
    (output/'integration_public.json').write_text(json.dumps({'config':asdict(c)}))
    (output/'private.json').write_text(json.dumps(dict(runtime_password='synthetic-only',payment_key='synthetic-only',device_key='synthetic-only')))
    s=IntegrationSupervisor(ROOT,output,c)
    with pytest.raises(Denied):s.launch_integration('arbitrary')
    with pytest.raises(Denied):s.stop_integration(SimpleNamespace(pid=1))
    with pytest.raises(PendingIntegration):s.launch_business('api')
    p=s.launch_integration('abnormal')
    assert s.wait_integration(p,expected=17)==17
    s.finish()
    assert s.events(p)[-1]['event']=='intentional_abnormal'


def test_actual_windows_guard_loopback_socketpair_and_native_aliases():
    output=ROOT/'.local/business_adapter_controls'/uuid4().hex
    output.mkdir(parents=True,exist_ok=False)
    code=r'''
import sys,json,socket,threading
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from tools.g6_business.adapter import Config,Denied
from tools.g6_business.native import install
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(302 if self.path=='/redirect' else 200)
  if self.path=='/redirect':self.send_header('Location','http://127.0.0.1:5433/')
  self.end_headers();self.wfile.write(b'ok')
 def log_message(self,*a):pass
server=HTTPServer(('127.0.0.1',0),Handler);port=server.server_port
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
c=Config('123456abcdef','phase5_test_123456abcdef','g6r_123456abcdef','doi_pin_g6_df268aa6e107','7712160968488140838',(port,),((port,'GET','/health'),(port,'GET','/redirect')),profile='pc')
events=[];install(c,'synthetic-only',Path(sys.argv[1]),events.append)
import httpx,psycopg
assert httpx.get('http://127.0.0.1:'+str(port)+'/health',trust_env=False).status_code==200
denied=0
for action in [lambda:httpx.get('http://127.0.0.1:'+str(port)+'/redirect',trust_env=False),lambda:httpx.get('http://127.0.0.1:'+str(port)+'/mock/v1/refunds',trust_env=False),lambda:socket.getaddrinfo('localhost',port),lambda:socket.socket().connect(('127.0.0.1',port)),lambda:socket.socket(socket.AF_INET6).connect(('::1',port)),lambda:psycopg.connect(host='127.0.0.1',port=5433),lambda:psycopg.Connection.connect(host='127.0.0.1',port=5448,user='postgres')]:
 try:action()
 except Denied:denied+=1
 else:raise AssertionError('Unblocked actual client')
a,b=socket.socketpair();a.send(b'x');assert b.recv(1)==b'x';a.close();b.close()
server.shutdown();server.server_close();thread.join(3);assert not thread.is_alive()
print(json.dumps({'denied':denied,'events':events,'pid':__import__('os').getpid(),'parent_pid':__import__('os').getppid()}))
'''
    env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','COMSPEC'}}
    env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'services/backend'))
    proc=subprocess.run([sys.executable,'-B','-c',code,str(output)],cwd=ROOT,env=env,capture_output=True,timeout=20)
    (output/'stdout.log').write_bytes(proc.stdout);(output/'stderr.log').write_bytes(proc.stderr)
    assert proc.returncode==0,proc.stderr.decode(errors='replace')
    facts=json.loads(proc.stdout)
    assert facts['denied']==7 and any(e['event']=='stdlib_socketpair' for e in facts['events'])
    assert any(e['event']=='http' for e in facts['events'])


def test_actual_empty_payment_mock_oracle(monkeypatch):
    from fastapi.testclient import TestClient
    from simulators.payment.main import create_app
    from tools.g6_business.integration_child import verify_empty_mock_response
    import sqlite3
    output=ROOT/'.local/business_adapter_controls'/uuid4().hex
    output.mkdir(parents=True,exist_ok=False)
    ledger=output/'payment.sqlite3'
    monkeypatch.setenv('PAYMENT_SERVICE_KEY','test-only-service-key-over-24-characters')
    with TestClient(create_app(path=ledger)) as c:
        r=c.get('/mock/v1/charges/00000000-0000-0000-0000-000000000000',headers={'X-Service-Key':'test-only-service-key-over-24-characters'})
    body=verify_empty_mock_response(r)
    assert body['result']=='NOT_FOUND'
    with pytest.raises(AssertionError):assert r.status_code==404  # Original oracle fails.
    with sqlite3.connect(ledger) as db:assert db.execute('SELECT count(*) FROM charges').fetchone()[0]==0
    import httpx
    for response in [httpx.Response(404,json=body),httpx.Response(200,json={**body,'result':'SUCCEEDED'}),httpx.Response(200,json={**body,'amount_minor':0}),httpx.Response(200,json={**body,'provider_key':str(uuid4())}),httpx.Response(200,json={**body,'extra':True}),httpx.Response(200,json={}),httpx.Response(200,text='invalid JSON')]:
        with pytest.raises(Denied):verify_empty_mock_response(response)
