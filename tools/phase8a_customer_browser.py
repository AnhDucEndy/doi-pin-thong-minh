"""Isolated read-only Browser smoke fixture; retain schema and evidence."""
from smoke_phase8a import *
from test_phase8a_inspection_transport import setup_inspection
from simulators.device.recovery_fence import transport_inspection, flush
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual', action='store_true',
                        help='Keep fixture services alive until the local stop marker is created; protocol TTLs stay unchanged.')
    args = parser.parse_args()
    directory=ROOT/'.cache'/('customer-browser-'+uuid4().hex[:10])
    directory.mkdir()
    for port in (8040,5178):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:
                raise RuntimeError('Fixture port occupied')
    demo=Database(Settings.from_env()); before=fingerprints(demo)
    generator=environment.__wrapped__();env=next(generator)
    processes=[];logs=[]
    try:
        with TestClient(create_app(env['settings'])) as http:
            def auth(name):return login(http,env,name)
            swap,sim,task,tech=setup_inspection(http,env,auth,directory,committed=True)
            try:
                transport_inspection(sim,task);flush(sim)
            finally:sim.close()
        runtime=dict(os.environ,DATABASE_SCHEMA=env['settings'].schema,
            PYTHONPATH=str(ROOT/'services/backend'),DEV_API_TARGET='http://127.0.0.1:8040')
        def start(args,name,cwd):
            log=(directory/(name+'.log')).open('w',encoding='utf-8');logs.append(log)
            processes.append(subprocess.Popen(args,cwd=cwd,env=runtime,stdout=log,
                stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW))
        start([sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1',
            '--port','8040','--no-access-log'],'api',ROOT)
        start(['node',str(ROOT/'apps/web/node_modules/vite/bin/vite.js'),'--port','5178','--strictPort'],'web',ROOT/'apps/web')
        wait(lambda:httpx.get('http://127.0.0.1:5178/health').status_code==200,'Browser fixture ready',30)
        # Private workspace file. Never print credentials or put them in URL.
        (directory/'private.json').write_text(json.dumps({'schema':env['settings'].schema,
            'swap_id':swap['id'],'passwords':env['passwords']}),encoding='utf-8')
        with env['seed_db'].sessions() as current:
            from app.application import recovery
            operation = recovery.case_for(current, env['seed_db'], UUID(swap['id']))['operation_id']
        (directory/'public.json').write_text(json.dumps({
            'schema':env['settings'].schema,'swap_id':swap['id'],'operation_id':str(operation),
            'frontend':'http://127.0.0.1:5178/','backend':'http://127.0.0.1:8040',
            'processes':[p.pid for p in processes],'mode':'manual' if args.manual else 'smoke',
            'available_fixture':'PRE_ACTION_INSPECTION',
            'freshness_managed':False,'stop_marker':str(directory/'stop')
        },indent=2),encoding='utf-8')
        print('Browser fixture ready: '+str(directory.relative_to(ROOT)),flush=True)
        end=time.monotonic()+900
        while (args.manual or time.monotonic()<end) and not (directory/'stop').exists():
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Browser fixture child exited; inspect retained runtime logs')
            time.sleep(1)
    finally:
        for child in reversed(processes):
            if child.poll() is None:child.terminate();child.wait(timeout=15)
        for log in logs:log.close()
        unchanged=fingerprints(demo)==before
        (directory/'result.json').write_text(json.dumps({'demo_fingerprint_unchanged':unchanged}),encoding='utf-8')
        assert unchanged
        demo.engine.dispose()
        try:next(generator)
        except StopIteration:pass

if __name__=='__main__':main()
