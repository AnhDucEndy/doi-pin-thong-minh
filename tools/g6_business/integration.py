"""Bounded integration-only process lifecycle. General business launch stays shut."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .adapter import Supervisor, require

KINDS=frozenset({'api','payment_mock','device_bootstrap','device_worker','payment_worker','probe','abnormal'})


class IntegrationSupervisor(Supervisor):
    def __init__(self,root,output,config):
        self.integration_output=Path(output).resolve()
        super().__init__(root,self.integration_output/'processes',config)
        self.kinds={};self.logs={}

    def launch_integration(self,kind):
        require(kind in KINDS and kind not in self.kinds.values(),'INTEGRATION_ENTRYPOINT')
        script=self.root/'tools/g6_business/integration_child.py'
        allowed={'SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC'}
        env={k:v for k,v in os.environ.items() if k.upper() in allowed}
        env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
        stdout=(self.output/(kind+'.stdout.log')).open('xb');stderr=(self.output/(kind+'.stderr.log')).open('xb')
        command=[sys._base_executable,'-I','-B',str(script),str(self.integration_output),kind]
        p=subprocess.Popen(command,cwd=self.output,env=env,stdout=stdout,stderr=stderr,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.owned[p.pid]=p;self.kinds[p.pid]=kind;self.logs[p.pid]=(stdout,stderr)
        self.record(dict(event='integration_start',kind=kind,pid=p.pid,parent_pid=os.getpid(),command=command,
                         source_hash=hashlib.sha256(script.read_bytes()).hexdigest(),environment_keys=sorted(env)))
        return p

    def events(self,proc):
        require(self.owned.get(proc.pid) is proc,'NOT_OWNED')
        directory=self.integration_output/('child-'+self.kinds[proc.pid])
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(directory.glob('event-*.json'))]

    def ready(self,proc,timeout=20):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            require(proc.poll() is None,'SERVER_EXITED_BEFORE_READINESS')
            events=self.events(proc)
            if any(e['event']=='server_ready' for e in events):
                require(events[0]['pid']==proc.pid and events[0]['parent_pid']==os.getpid(),'ACTUAL_SERVER_PID')
                self.record(dict(event='readiness',pid=proc.pid,kind=self.kinds[proc.pid],server_identity=events[0]))
                return
            time.sleep(.05)  # Bounded readiness polling, not a success substitute.
        require(False,'READINESS_TIMEOUT')

    def wait_integration(self,proc,expected=0,timeout=15):
        require(self.owned.get(proc.pid) is proc,'NOT_OWNED')
        code=proc.wait(timeout=timeout)
        self.exits.add(proc.pid)
        for stream in self.logs[proc.pid]:stream.close()
        events=self.events(proc)
        self.record(dict(event='integration_wait',pid=proc.pid,kind=self.kinds[proc.pid],exit_code=code,expected=expected))
        require(events and events[0]['pid']==proc.pid and events[0]['parent_pid']==os.getpid(),'CHILD_IDENTITY')
        require(code==expected,'INTEGRATION_CHILD_EXIT')
        require((expected==17 and any(e['event']=='intentional_abnormal' for e in events))
                or (expected==0 and events[-1]['event']=='completed'),'CHILD_COMPLETION')
        return code

    def stop_integration(self,proc):
        require(self.owned.get(proc.pid) is proc and proc.poll() is None,'NOT_OWNED_RUNNING')
        events=self.events(proc)
        require(events and events[0]['pid']==proc.pid and events[0]['parent_pid']==os.getpid(),'OWNED_STOP_IDENTITY')
        path=self.integration_output/('child-'+self.kinds[proc.pid])/'stop.json'
        with path.open('x') as f:json.dump(dict(pid=proc.pid),f)
        self.record(dict(event='graceful_stop',pid=proc.pid))
        return self.wait_integration(proc)

    def terminate_remaining(self):
        # Retain failed artifacts. Termination uses the verified Popen handle only.
        for pid,p in self.owned.items():
            if pid in self.exits:continue
            if p.poll() is None:
                self.record(dict(event='owned_failure_termination',pid=pid));p.terminate()
            code=p.wait(timeout=5);self.exits.add(pid)
            for stream in self.logs[pid]:stream.close()
            self.record(dict(event='failure_wait',pid=pid,exit_code=code))


def run_once(root,output,config):
    output=Path(output)
    with (output/'integration_batch_intent.json').open('x') as f:
        json.dump(dict(run_id=config.run_id,retries=0,scope='harmless integration only'),f)
    s=IntegrationSupervisor(root,output,config)
    result={'passed':False}
    try:
        api=s.launch_integration('api');s.ready(api)
        mock=s.launch_integration('payment_mock');s.ready(mock)
        for kind in ('device_bootstrap','device_worker','payment_worker','probe'):
            p=s.launch_integration(kind);s.wait_integration(p)
        p=s.launch_integration('abnormal');s.wait_integration(p,expected=17)
        s.stop_integration(mock);s.stop_integration(api);s.finish()
        result={'passed':True,'children':7,'normal_exits':6,'controlled_abnormal_exit':17}
        return result
    finally:
        if not result['passed']:s.terminate_remaining()
        journal=[json.loads(p.read_text()) for p in sorted(s.output.glob('event_*.json'))]
        with (output/'PROCESS_LIFECYCLE_JOURNAL.json').open('x',encoding='utf-8') as f:
            json.dump(dict(result=result,events=journal),f,indent=2)
