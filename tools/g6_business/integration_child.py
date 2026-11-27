"""Explicit harmless integration entrypoint. No S1 business operations."""
import json
import os
from pathlib import Path
import sys
import time

# Base interpreter -I avoids the Windows venv redirector's PID ambiguity.
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'services/backend'),str(ROOT/'.venv/Lib/site-packages')]


def verify_empty_mock_response(response):
    """Exact existing mock contract; contains no credentials or charge effects."""
    from tools.g6_business.adapter import require
    require(response.status_code==200,'EMPTY_MOCK_STATUS')
    try:body=response.json()
    except ValueError:
        require(False,'EMPTY_MOCK_JSON')
    require(body==dict(provider_key='00000000-0000-0000-0000-000000000000',
        provider_reference=None,result='NOT_FOUND',amount_minor=None,currency=None),'EMPTY_MOCK_BODY')
    return body


def main():
    from tools.g6_business.adapter import Config, require, Denied
    from tools.g6_business.native import install
    from psycopg.conninfo import make_conninfo
    output=Path(sys.argv[1]).resolve();kind=sys.argv[2]
    require(output.is_relative_to(ROOT/'.local'),'OUTPUT_SCOPE')
    require(kind in ('api','payment_mock','device_bootstrap','device_worker','payment_worker','probe','abnormal'),'ENTRYPOINT')
    packet=json.loads((output/'integration_public.json').read_text(encoding='utf-8'))
    config=Config(**{**packet['config'],'ports':tuple(packet['config']['ports']),'routes':tuple(tuple(r) for r in packet['config']['routes'])}).validate()
    # Do not permit public config to authorize business HTTP, arbitrary entrypoints,
    # or protected endpoints. Only health and one nonexistent mock charge query.
    require(len(config.ports)==2 and config.routes==((config.ports[0],'GET','/health'),
        (config.ports[1],'GET','/mock/v1/charges/00000000-0000-0000-0000-000000000000')),'INTEGRATION_ROUTES')
    secret=json.loads((output/'private.json').read_text(encoding='utf-8'))
    require(set(secret)=={'runtime_password','payment_key','device_key'},'PRIVATE_SCOPE')
    child=output/('child-'+kind);child.mkdir(exist_ok=False)
    seq=0
    def record(value):
        nonlocal seq
        seq+=1
        temporary=child/f'event-{seq:04d}.tmp'
        with temporary.open('x',encoding='utf-8') as f:
            json.dump(dict(pid=os.getpid(),parent_pid=os.getppid(),monotonic=time.monotonic(),**value),f);f.flush();os.fsync(f.fileno())
        # Unique immutable publication: readers never parse an in-flight file.
        temporary.rename(child/f'event-{seq:04d}.json')
    record(dict(event='enter',kind=kind,executable=sys.executable))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',DATABASE_SCHEMA=config.schema,
        DATABASE_URL=f'postgresql+psycopg://{config.role}:{secret["runtime_password"]}@127.0.0.1:{config.target[0]}/{config.database}',
        PAYMENT_SERVICE_KEY=secret['payment_key'],DEVICE_KEY_DERIVATION_SECRET=secret['device_key'],
        PAYMENT_MOCK_URL='http://127.0.0.1:'+str(config.ports[1]),PAYMENT_LEDGER_PATH=str(child/'payment.sqlite3'))
    install(config,secret['runtime_password'],child,record)
    if kind=='abnormal':
        record(dict(event='intentional_abnormal',expected_exit=17));return 17
    if kind in ('api','payment_mock'):
        import uvicorn
        if kind=='api':
            from app.main import create_app
            app=create_app()
            port=config.ports[0];allowed='/health'
        else:
            from simulators.payment.main import create_app
            app=create_app(path=child/'payment.sqlite3')
            port=config.ports[1];allowed=config.routes[1][2]
        # Incoming HTTP is constrained too: an alternate raw client cannot invoke
        # a business route through an otherwise admitted server port.
        from fastapi.responses import JSONResponse
        @app.middleware('http')
        async def integration_only(request,call_next):
            if request.method!='GET' or request.url.path!=allowed or request.url.query:
                record(dict(event='incoming_refusal',method=request.method,path=request.url.path))
                return JSONResponse(status_code=403,content={'code':'INTEGRATION_ONLY'})
            return await call_next(request)
        class Server(uvicorn.Server):
            async def startup(self,sockets=None):
                await super().startup(sockets)
                if self.started:record(dict(event='server_ready',port=port))
            async def on_tick(self,counter):
                if (child/'stop.json').exists():
                    require(json.loads((child/'stop.json').read_text())=={'pid':os.getpid()},'OWNED_STOP')
                    self.should_exit=True
                if time.monotonic()>deadline:
                    record(dict(event='deadline_failure'));self.should_exit=True;self.failed=True
                return await super().on_tick(counter)
        server=Server(uvicorn.Config(app,host='127.0.0.1',port=port,loop='asyncio',access_log=False,log_level='warning',timeout_graceful_shutdown=5))
        deadline=time.monotonic()+60;server.failed=False
        server.run()
        require(server.started and not server.failed and (child/'stop.json').exists(),'SERVER_COMPLETION')
    elif kind in ('device_worker','payment_worker'):
        import runpy
        sys.argv=[kind,'--once']
        runpy.run_module('app.workers.'+('device' if kind=='device_worker' else 'payment'),run_name='__main__')
        record(dict(event='worker_once_completed',empty_fixture=True))
    elif kind=='device_bootstrap':
        from simulators.device.main import Simulator
        sim=Simulator('S01',secret['device_key'],'http://127.0.0.1:'+str(config.ports[0]),child/'device.sqlite3')
        require(sim.conn.execute('SELECT count(*) FROM events').fetchone()[0]==0,'SIM_EVENTS')
        require(sim.conn.execute('SELECT count(*) FROM commands').fetchone()[0]==0,'SIM_COMMANDS')
        sim.close();record(dict(event='simulator_bootstrap',cycles=0,events=0,commands=0,physical_effects=0))
    elif kind=='probe':
        import psycopg
        import httpx
        import socket
        params=dict(host='127.0.0.1',hostaddr='127.0.0.1',port=config.target[0],dbname=config.database,user=config.role,password=secret['runtime_password'])
        with psycopg.connect(**params) as c:
            actual=c.execute('SELECT current_database(),session_user,current_user,current_schema()').fetchone()
            require(actual==(config.database,config.role,config.role,config.schema),'ACTUAL_RUNTIME_SESSION')
            record(dict(event='runtime_session',binding=actual,backend_pid=c.info.backend_pid))
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=5) as client:
            r=client.get('http://127.0.0.1:'+str(config.ports[0])+'/health');require(r.status_code==200 and r.json()['database']=='connected','API_HEALTH')
            r=client.get('http://127.0.0.1:'+str(config.ports[1])+config.routes[1][2],headers={'X-Service-Key':secret['payment_key']})
            body=verify_empty_mock_response(r)
            record(dict(event='empty_mock_response',status=r.status_code,body=body))
            for host,port,path in [('127.0.0.1',5433,'/health'),('127.0.0.1',config.target[0],'/health'),('localhost',config.ports[0],'/health'),('[::1]',config.ports[0],'/health'),('127.0.0.1',config.ports[1],'/mock/v1/refunds')]:
                try:client.get(f'http://{host}:{port}{path}')
                except Denied:record(dict(event='denied_before_traffic',host=host,port=port,path=path))
                else:require(False,'HTTP_NEGATIVE_NOT_DENIED')
        for port in range(5432,5450):
            try:psycopg.connect(**{**params,'port':port,'dbname':'protected'})
            except Denied:record(dict(event='native_wrong_binding_denied',port=port))
            else:require(False,'DB_NEGATIVE_NOT_DENIED')
        for address in [('127.0.0.1',5433),('127.0.0.1',config.ports[0]),('::1',config.ports[0]),('example.com',443)]:
            try:
                with socket.socket() as s:s.connect(address)
            except Denied:record(dict(event='raw_socket_denied',address=address))
            else:require(False,'RAW_NEGATIVE_NOT_DENIED')
    record(dict(event='completed',kind=kind,exit_code=0))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        # Driver exceptions may embed parameters. Only class is emitted.
        import traceback
        from tools.g6_business.adapter import Denied
        print(json.dumps(dict(error_type=type(error).__name__,
            code=str(error) if isinstance(error,Denied) else 'REDACTED_LIBRARY_ERROR',
            frames=[dict(file=f.filename,line=f.lineno,function=f.name) for f in traceback.extract_tb(error.__traceback__)])),file=sys.stderr)
        raise SystemExit(1)
