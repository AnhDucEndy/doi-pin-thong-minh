"""Bounded fixture IPC checks with real Node readers; no app or DB workflows.

Usage: python -B tools/verify_phase8a_fixture_ipc.py NEW_LOCAL_OUTPUT NODE_EXE
All evidence is retained. Only publisher-owned temporary snapshots are removed.
"""
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, ElementTree

import phase8a_manual_operator as ipc

OUTPUT = NODE = None


def state(version):
    return {'case_id': 'synthetic', 'state': 'OPEN', 'version': version,
            'active_operation': {'protocol_version': '0.2', 'attestations': []},
            'content': str(version).zfill(6)*8192, 'unicode': 'Kiểm tra IPC'}


def control_json(path, value):
    """Publish a new immutable control/ACK record; never replace old evidence."""
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    with temporary.open('x',encoding='utf-8') as stream:
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    if path.exists():raise FileExistsError(path)
    os.rename(temporary,path)


CONCURRENT_READER = r'''
const fs=require('node:fs'),p=require('node:path'),crypto=require('node:crypto');
const d=process.argv[1],id=process.argv[2],run=process.argv[3];
let reads=0,last=0,highest=0,ack=null;const versions=new Set(),deadline=Date.now()+30000;
function hash(raw){return crypto.createHash('sha256').update(raw).digest('hex');}
function publish(name,value){const file=p.join(d,name),temp=file+'.tmp';
 fs.writeFileSync(temp,JSON.stringify(value),{flag:'wx'});fs.renameSync(temp,file);}
function step(){try{
 const raw=fs.readFileSync(p.join(d,'state.json'),'utf8');if(raw.length===0)throw Error('zero-byte state');
 const v=JSON.parse(raw);
 if(v.case_id!=='synthetic'||v.state!=='OPEN'||!Number.isInteger(v.version)||v.version<last||v.version<1||
 v.active_operation.protocol_version!=='0.2'||!Array.isArray(v.active_operation.attestations)||
 v.content!==String(v.version).padStart(6,'0').repeat(8192)||v.unicode!=='Kiểm tra IPC')throw Error('schema/version inconsistency');
 last=v.version;highest=Math.max(highest,last);reads++;versions.add(last);
 if(reads===1)publish('ready-'+id+'.json',{run,pid:process.pid,reader:id,parsed:last});
 if(fs.existsSync(p.join(d,'final-version.json'))){
  const target=JSON.parse(fs.readFileSync(p.join(d,'final-version.json'),'utf8'));
  if(target.run!==run||!Number.isInteger(target.version)||last>target.version)throw Error('wrong final request');
  if(!ack&&last===target.version){
   if(hash(raw)!==target.sha256)throw Error('final snapshot hash mismatch');
   ack={run,pid:process.pid,reader:id,parsed:last,highest,reads,versions:versions.size,snapshot_sha256:hash(raw)};
   publish('ack-'+id+'.json',ack);
  }
 }
 if(fs.existsSync(p.join(d,'stop'))){
  const stop=JSON.parse(fs.readFileSync(p.join(d,'stop'),'utf8'));
  if(stop.run!==run||!ack||last!==stop.version||highest!==stop.version||ack.parsed!==stop.version)throw Error('stop before final ACK');
  console.log(JSON.stringify({pid:process.pid,reader:id,reads,versions:versions.size,last,highest,
   zero:0,invalid:0,acked:ack.parsed,final_sha256:hash(raw)}));return;
 }
 if(Date.now()>deadline)throw Error('bounded reader deadline');setImmediate(step);
}catch(e){console.error(e.stack);process.exitCode=1;}}step();'''


class IPCTests(unittest.TestCase):
    def setUp(self):
        self.directory = OUTPUT/self._testMethodName
        self.directory.mkdir(exist_ok=False)

    def node(self, script, *args):
        result = subprocess.run([str(NODE), '-e', script, *map(str, args)],
            capture_output=True, text=True, encoding='utf8', timeout=15,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_initial_snapshot_schema_and_serialization(self):
        snapshot = state(1); snapshot['observed_at'] = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ipc.publish_state(self.directory, snapshot)
        actual = self.node('console.log(JSON.stringify(JSON.parse(require("node:fs").readFileSync(process.argv[1],"utf8"))))', self.directory/'state.json')
        self.assertEqual(actual, json.loads(json.dumps(snapshot, default=str)))
        self.assertFalse(list(self.directory.glob('state.json.*.tmp')))

    def test_concurrent_actual_node_reads(self):
        observed = self.concurrent_readers(1,201)['readers'][0]
        self.assertGreater(observed['reads'], 1); self.assertGreater(observed['versions'], 1)
        self.assertEqual(observed['last'], 201)
        (self.directory/'observed.json').write_text(json.dumps(observed), encoding='utf8')
        self.assertFalse(list(self.directory.glob('state.json.*.tmp')))

    def test_windows_node_open_handle_survives_replacement(self):
        ipc.publish_state(self.directory, state(1))
        script = r'''
const fs=require('node:fs'),p=require('node:path'),d=process.argv[1];
const fd=fs.openSync(p.join(d,'state.json'),'r');const old=JSON.parse(fs.readFileSync(fd,'utf8'));let closed=false;
fs.writeFileSync(p.join(d,'opened'),'yes');
const deadline=Date.now()+10000;
function step(){if(!closed&&fs.existsSync(p.join(d,'release'))){fs.closeSync(fd);closed=true;}
if(fs.existsSync(p.join(d,'replaced'))){const current=JSON.parse(fs.readFileSync(p.join(d,'state.json'),'utf8'));console.log(JSON.stringify({old:old.version,current:current.version}));}else if(Date.now()>deadline){if(!closed)fs.closeSync(fd);process.exitCode=1;}else setTimeout(step,2);}step();'''
        original_replace = ipc.os.replace
        collisions = []
        def replace(source, destination):
            try:return original_replace(source, destination)
            except OSError as error:
                collisions.append(getattr(error, 'winerror', None))
                (self.directory/'release').write_text('close owned reader', encoding='utf8')
                raise
        with patch.object(ipc.os, 'replace', side_effect=replace):
            observed = self.live_reader(script, 'opened', 'replaced', lambda: ipc.publish_state(self.directory, state(2)))
        self.assertEqual(observed, {'old': 1, 'current': 2})
        self.assertTrue(collisions)
        self.assertEqual(set(collisions), {5})

    def live_reader(self, script, ready, stop, update):
        child = subprocess.Popen([str(NODE), '-e', script, str(self.directory)], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            until = time.monotonic()+8
            while not (self.directory/ready).exists():
                self.assertIsNone(child.poll()); self.assertLess(time.monotonic(), until); time.sleep(.005)
            update(); (self.directory/stop).write_text('done', encoding='utf8')
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr)
            return json.loads(stdout)
        finally:
            if child.poll() is None:child.terminate(); child.wait(timeout=5)

    def test_replace_failure_visible_no_fallback_or_other_cleanup(self):
        ipc.publish_state(self.directory, state(1)); before = (self.directory/'state.json').read_bytes()
        other = self.directory/'state.json.historical.tmp'; other.write_text('keep', encoding='utf8')
        with patch.object(ipc.os, 'replace', side_effect=PermissionError('synthetic sharing denial')) as replace:
            with self.assertRaises(ipc.StatePublicationError) as error:ipc.publish_state(self.directory, state(2))
        self.assertIsInstance(error.exception.__cause__, PermissionError); self.assertEqual(replace.call_count, 1)
        self.assertEqual((self.directory/'state.json').read_bytes(), before)
        self.assertEqual(other.read_text(), 'keep'); self.assertEqual(list(self.directory.glob('state.json.*.tmp')), [other])

    def test_flush_and_serialization_failures_preserve_previous(self):
        ipc.publish_state(self.directory, state(1)); before = (self.directory/'state.json').read_bytes()
        with patch.object(ipc.os, 'fsync', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(ipc.StatePublicationError):ipc.publish_state(self.directory, state(2))
        circular = {}; circular['self'] = circular
        with self.assertRaises(ValueError):ipc.publish_state(self.directory, circular)
        self.assertEqual((self.directory/'state.json').read_bytes(), before)
        self.assertFalse(list(self.directory.glob('state.json.*.tmp')))

    def test_temp_collision_does_not_adopt_or_delete(self):
        ipc.publish_state(self.directory, state(1))
        other = self.directory/'state.json.collision.tmp'; other.write_text('keep', encoding='utf8')
        with patch.object(ipc, 'uuid4', return_value=SimpleNamespace(hex='collision')):
            with self.assertRaises(ipc.StatePublicationError):ipc.publish_state(self.directory, state(2))
        self.assertEqual(other.read_text(), 'keep')
        self.assertEqual(json.loads((self.directory/'state.json').read_text())['version'], 1)

    def test_additional_three_node_readers_monotonic_stress(self):
        result=self.concurrent_readers(3,401)
        self.assertEqual(result['updates'],400)
        self.assertEqual(len(result['acks']),3)

    def concurrent_readers(self, count, final_version):
        """One writer sequence; stop only after every real reader ACKs final."""
        directory=self.directory;run=uuid4().hex;readers=[];logs=[];events=[]
        def event(kind,**facts):
            with (directory/'ordering.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(dict(kind=kind,at_ns=time.time_ns(),**facts))+'\n')
                stream.flush();os.fsync(stream.fileno())
        def acknowledgments(final_hash,seconds,phase):
            started=time.monotonic();deadline=started+seconds;accepted={}
            while True:
                for index,child in enumerate(readers):
                    file=directory/('ack-'+str(index)+'.json')
                    if file.exists():
                        ack=json.loads(file.read_text(encoding='utf-8'))
                        self.assertEqual((ack['run'],ack['pid'],ack['reader'],ack['parsed'],ack['highest'],ack['snapshot_sha256']),
                            (run,child.pid,str(index),final_version,final_version,final_hash))
                        self.assertGreater(ack['reads'],1);self.assertGreater(ack['versions'],1)
                        accepted[index]=ack
                    self.assertIsNone(child.poll(),'Reader exited before acknowledged stop')
                if len(accepted)==count:return [accepted[i] for i in range(count)]
                if time.monotonic()>=deadline:
                    control_json(directory/(phase+'-timeout.json'),dict(timeout_seconds=seconds,
                        elapsed_seconds=time.monotonic()-started,missing=[i for i in range(count) if i not in accepted],
                        children=[dict(pid=c.pid,exit=c.poll()) for c in readers]))
                    raise TimeoutError('Final-version ACK timeout')
                time.sleep(.005)  # Bounded condition polling, never a success-by-delay.
        ipc.publish_state(directory,state(1))
        try:
            for index in range(count):
                stdout=(directory/('reader-'+str(index)+'.stdout.json')).open('x',encoding='utf-8')
                stderr=(directory/('reader-'+str(index)+'.stderr.txt')).open('x',encoding='utf-8');logs.extend([stdout,stderr])
                readers.append(subprocess.Popen([str(NODE),'-e',CONCURRENT_READER,str(directory),str(index),run],
                    stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
            deadline=time.monotonic()+8
            while not all((directory/('ready-'+str(i)+'.json')).exists() for i in range(count)):
                self.assertTrue(all(c.poll() is None for c in readers),'Reader failed before ready')
                self.assertLess(time.monotonic(),deadline,'Initial reader readiness timeout');time.sleep(.005)
            for i,c in enumerate(readers):
                self.assertEqual(json.loads((directory/('ready-'+str(i)+'.json')).read_text(encoding='utf-8')),
                    dict(run=run,pid=c.pid,reader=str(i),parsed=1))
            event('ALL_READERS_READY',pids=[c.pid for c in readers])
            with self.assertRaisesRegex(TimeoutError,'ACK timeout'):
                acknowledgments(None,.2,'expected-pre-final')
            self.assertFalse((directory/'stop').exists());self.assertFalse(list(directory.glob('ack-*.json')))
            event('EXPECTED_ACK_TIMEOUT_WITHOUT_FINAL_REQUEST')
            native_replace=ipc.os.replace
            def replace(source, destination):
                entry={'at':time.time(),'pid':os.getpid()}
                try:
                    native_replace(source,destination);entry['success']=True
                except OSError as error:
                    entry.update(success=False,winerror=getattr(error,'winerror',None),errno=error.errno)
                    raise
                finally:events.append(entry)
            with patch.object(ipc.os,'replace',side_effect=replace):
                for version in range(2,final_version+1):ipc.publish_state(directory,state(version))
            raw=(directory/'state.json').read_bytes();self.assertEqual(json.loads(raw)['version'],final_version)
            final_hash=hashlib.sha256(raw).hexdigest();event('FINAL_PUBLICATION_COMPLETED',version=final_version,sha256=final_hash)
            control_json(directory/'final-version.json',dict(run=run,version=final_version,sha256=final_hash))
            acks=acknowledgments(final_hash,10,'final')
            control_json(directory/'acks-before-stop.json',dict(acks=acks,final_version=final_version))
            event('ALL_FINAL_ACKS_VALIDATED',pids=[c.pid for c in readers],version=final_version)
            control_json(directory/'stop',dict(run=run,version=final_version));event('STOP_SIGNALED_AFTER_ALL_ACKS')
            for child in readers:self.assertEqual(child.wait(timeout=5),0,'Node error; see retained stderr')
            for log in logs:log.close()
            logs=[];observations=[]
            for index,child in enumerate(readers):
                self.assertEqual((directory/('reader-'+str(index)+'.stderr.txt')).read_text(encoding='utf-8'),'')
                observed=json.loads((directory/('reader-'+str(index)+'.stdout.json')).read_text(encoding='utf-8'))
                self.assertEqual(observed['pid'],child.pid);self.assertGreater(observed['reads'],1);self.assertGreater(observed['versions'],1)
                self.assertEqual((observed['last'],observed['highest'],observed['acked']),(final_version,)*3)
                self.assertEqual(observed['final_sha256'],final_hash);self.assertEqual((observed['zero'],observed['invalid']),(0,0))
                observations.append(observed)
            self.assertEqual(hashlib.sha256((directory/'state.json').read_bytes()).hexdigest(),final_hash)
            self.assertFalse(list(directory.glob('state.json.*.tmp')))
            result=dict(updates=final_version-1,final_version=final_version,acks=acks,readers=observations,
                replace_attempts=events,final_sha256=final_hash,ACK_timeout_seconds=10,stop_only_after_all_ACKs=True)
            control_json(directory/'stress-result.json',result)
            return result
        finally:
            terminal=[]
            for child in readers:
                before=child.poll()
                if before is None:child.terminate();child.wait(timeout=5)
                terminal.append(dict(pid=child.pid,exit=child.returncode,owned_failure_stop=before is None))
            for log in logs:log.close()
            control_json(directory/'terminal_processes.json',terminal)

    def test_operator_failure_outcome(self):
        import httpx
        operation='11111111-1111-4111-8111-111111111111';request_id='request-'+operation.replace('-','')
        canary='SYNTHETIC_SENSITIVE_CANARY';checks=[]
        def outcome(status=409,code='RECONCILIATION_REQUIRED',body_operation=operation):
            request=httpx.Request('POST','http://user:'+canary+'@127.0.0.1/v1/device/recovery-observations?secret='+canary,
                headers={'Authorization':'Bearer '+canary,'X-Device-Key':canary},
                json={'operation_id':body_operation,'password':canary,'token':canary})
            response=httpx.Response(status,request=request,json={'code':code,'message':canary,'password':canary})
            error=httpx.HTTPStatusError(canary,request=request,response=response)
            return ipc.failure_outcome(error,action='REINSPECT',operation=operation,request_id=request_id)
        valid=outcome()
        self.assertEqual(valid,dict(completed=False,error_type='HTTPStatusError',action='REINSPECT',
            operation_id=operation,request_id=request_id,http_status=409,error_code='RECONCILIATION_REQUIRED',
            http_method='POST',http_path='/v1/device/recovery-observations',request_operation_id=operation))
        checks.append('valid409')
        for status in (500,401,403):
            with self.subTest(status=status):self.assertEqual(outcome(status)['http_status'],status);checks.append('status'+str(status))
        self.assertEqual(outcome(code='EVIDENCE_REQUIRED')['error_code'],'EVIDENCE_REQUIRED');checks.append('wrong-code-retained')
        self.assertEqual(outcome(code=canary)['error_code'],None);checks.append('unknown-code-redacted')
        self.assertEqual(outcome(body_operation='22222222-2222-4222-8222-222222222222')['request_operation_id'],
            '22222222-2222-4222-8222-222222222222');checks.append('actual-request-operation-retained')
        self.assertNotIn(canary,json.dumps(valid));self.assertEqual(len(valid),10);checks.append('allowlist-redaction')
        control_json(self.directory/'operator_failure_fixture.json',dict(outcome=valid,
            expected=dict(operation_id=operation,request_id=request_id),serializer_checks=checks))

    def test_additional_native_held_reader_denial_is_bounded(self):
        ipc.publish_state(self.directory, state(1))
        script = r'''
const fs=require('node:fs'),p=require('node:path'),d=process.argv[1];
const fd=fs.openSync(p.join(d,'state.json'),'r');const old=JSON.parse(fs.readFileSync(fd,'utf8'));
fs.writeFileSync(p.join(d,'ready'),'ready');const deadline=Date.now()+10000;
function step(){if(fs.existsSync(p.join(d,'stop'))){fs.closeSync(fd);console.log(JSON.stringify({pid:process.pid,old:old.version}));}else if(Date.now()>deadline){fs.closeSync(fd);process.exitCode=1;}else setTimeout(step,2);}step();'''
        def update():
            started = time.monotonic()
            with patch.object(ipc.os, 'replace', wraps=ipc.os.replace) as replace:
                with self.assertRaises(ipc.StatePublicationError) as error:ipc.publish_state(self.directory, state(2))
            elapsed = time.monotonic()-started
            self.assertEqual(error.exception.__cause__.winerror, 5)
            self.assertGreater(replace.call_count, 1)
            self.assertLessEqual(replace.call_count, ipc.STATE_PUBLISH_MAX_ATTEMPTS)
            self.assertLess(elapsed, 1.5)  # OS scheduling margin; configured deadline remains .5s.
            self.assertEqual(json.loads((self.directory/'state.json').read_text())['version'], 1)
            self.assertFalse(list(self.directory.glob('state.json.*.tmp')))
            (self.directory/'bounded-denial.json').write_text(json.dumps({'attempts': replace.call_count, 'elapsed': elapsed, 'winerror': 5}), encoding='utf8')
        observed = self.live_reader(script, 'ready', 'stop', update)
        self.assertEqual(observed['old'], 1)

    def test_additional_permanent_access_denial_and_other_errors(self):
        ipc.publish_state(self.directory, state(1))
        for code, retry in ((5, True), (32, False)):
            denial = PermissionError(13, 'synthetic persistent denial'); denial.winerror = code
            started = time.monotonic()
            with patch.object(ipc.os, 'replace', side_effect=denial) as replace:
                with self.assertRaises(ipc.StatePublicationError) as error:ipc.publish_state(self.directory, state(2))
            self.assertIs(error.exception.__cause__, denial)
            self.assertLessEqual(replace.call_count, ipc.STATE_PUBLISH_MAX_ATTEMPTS)
            self.assertGreater(replace.call_count, 1) if retry else self.assertEqual(replace.call_count, 1)
            self.assertLess(time.monotonic()-started, 1.5)
            self.assertEqual(json.loads((self.directory/'state.json').read_text())['version'], 1)
            self.assertFalse(list(self.directory.glob('state.json.*.tmp')))

    def test_initial_state_before_ready_and_playwright(self):self.handoff_probe(False)

    def test_initial_failure_prevents_playwright(self):self.handoff_probe(True)

    def handoff_probe(self, fail):
        class StopProbe(Exception):pass
        class Web:
            stopped = False
            pid = 4242
            def poll(self):return 0 if self.stopped else None
            def terminate(self):self.stopped = True
            def wait(self, *args):return 0
        web = Web(); launches = []; snapshot = state(1)
        def popen(args, **kwargs):
            if any('@playwright/test/cli.js' in str(x).replace('\\', '/') for x in args):
                launches.append('playwright')
                self.assertEqual(json.loads((self.directory/'state.json').read_text()), snapshot)
                public = json.loads((self.directory/'manual.json').read_text())
                self.assertTrue(public['ready'])
                self.assertEqual(public['web_pid'], web.pid)
                self.assertIsInstance(public['web_pid'], int)
                self.assertGreater(public['web_pid'], 0)
                raise StopProbe()
            return web
        fixture = {'settings': SimpleNamespace(schema='phase5_test_synthetic'), 'passwords': {}}
        import socket
        with socket.socket() as sock:sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        env = {'P8_MANUAL_WEB_PORT': str(port), 'P8_PLAYWRIGHT_SPEC': 'staged.spec.ts'}
        with patch.dict(sys.modules, {'smoke_phase8a': SimpleNamespace(wait=lambda cb, *args: self.assertTrue(cb()))}), patch('httpx.get', return_value=SimpleNamespace(status_code=200)), patch('subprocess.Popen', side_effect=popen):
            args = (self.directory, self.directory, fixture, {'id': 'synthetic'}, env, lambda *a: None, None, lambda: snapshot, {})
            if fail:
                with patch.object(ipc, 'publish_state', side_effect=ipc.StatePublicationError('synthetic failure')):
                    with self.assertRaises(ipc.StatePublicationError):ipc.handoff(*args)
                self.assertFalse(launches); self.assertFalse((self.directory/'manual.json').exists())
            else:
                with self.assertRaises(StopProbe):ipc.handoff(*args)
                self.assertEqual(launches, ['playwright'])
        self.assertTrue(web.stopped)


def main():
    global OUTPUT, NODE
    OUTPUT = Path(sys.argv[1]).resolve(); NODE = Path(sys.argv[2]).resolve()
    root = Path(__file__).resolve().parents[1]
    if not OUTPUT.is_relative_to(root/'.local') or not NODE.is_file():raise ValueError('New workspace .local output and existing Node required')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    with (OUTPUT/'run.log').open('x', encoding='utf8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IPCTests))
    errors = {t.id(): ('error', detail) for t, detail in result.errors}
    errors.update({t.id(): ('failure', detail) for t, detail in result.failures})
    xml = Element('testsuite', name='Fixture IPC actual Windows Node', tests=str(result.testsRun), failures=str(len(result.failures)), errors=str(len(result.errors)), skipped=str(len(result.skipped)))
    for name in unittest.defaultTestLoader.getTestCaseNames(IPCTests):
        case = SubElement(xml, 'testcase', classname='IPCTests', name=name)
        if IPCTests(name).id() in errors:
            kind, detail = errors[IPCTests(name).id()]; SubElement(case, kind).text = detail
    ElementTree(xml).write(OUTPUT/'results.xml', encoding='utf-8', xml_declaration=True)
    summary = {'passed': result.wasSuccessful(), 'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped), 'platform': sys.platform, 'python': sys.version.split()[0], 'node_executable': str(NODE)}
    with (OUTPUT/'result.json').open('x', encoding='utf8') as f:json.dump(summary, f, indent=2)
    print(json.dumps(summary)); return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':sys.exit(main())
