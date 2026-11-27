"""Explicit real API startup only. Never invoked by imports or controls."""
import os,json,time,sys
from pathlib import Path
import uvicorn
DIRECTORY=PORT=NONCE=None
def write(name,value):
    with (DIRECTORY/name).open('x',encoding='utf-8') as f:json.dump(value,f)
class BoundedServer(uvicorn.Server):
    async def on_tick(self,counter):
        stop=DIRECTORY/'api-stop.json'
        if stop.exists():
            packet=json.loads(stop.read_text())
            if packet!=dict(pid=os.getpid(),nonce=NONCE):raise RuntimeError('Invalid owned API stop identity')
            self.should_exit=True
        if time.monotonic()>=self.stop_deadline:
            self.deadline_reached=True;self.should_exit=True
        return await super().on_tick(counter)
def main():
    global DIRECTORY,PORT,NONCE
    assert os.environ.get('G6_GUARD_READY')=='1'
    DIRECTORY=Path(os.environ['G6_SCENARIO_OUTPUT'])
    PORT=int(os.environ['G6_API_PORT']);NONCE=os.environ['G6_API_NONCE']
    server=BoundedServer(uvicorn.Config('app.main:create_app',factory=True,host='127.0.0.1',port=PORT,
        loop='asyncio',access_log=False,log_level='info',timeout_graceful_shutdown=5))
    server.stop_deadline=time.monotonic()+30;server.deadline_reached=False
    write('api-enter.json',dict(pid=os.getpid(),guard=True,application='app.main:create_app',port=PORT,maximum_seconds=30))
    code=1
    try:
        server.run()
        code=0 if server.started and not server.deadline_reached and (DIRECTORY/'api-stop.json').exists() else 1
    finally:
        write('api-exit.json',dict(pid=os.getpid(),code=code,started=server.started,
            intentional_stop=(DIRECTORY/'api-stop.json').exists(),deadline=server.deadline_reached))
    return code

if __name__=="__main__":raise SystemExit(main())
