"""On-demand Windows Task Scheduler boundary for the existing B1b runner.

No provisioning, retry, resume or cleanup. Status is read-only. A Windows
shutdown can still leave nonterminal evidence; it never establishes a pass.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE = ROOT/'.local/pc-b1b'
OS_KEYS = {'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE',
           'APPDATA','LOCALAPPDATA','PROGRAMDATA','COMSPEC','USERNAME'}
EXTRA = ('tools/launch_phase8b_windows.py','tests/test_phase8b_tooling.py',
         'tests/test_provision_database.py','tests/test_phase8b_fixture_isolation.py',
         'docs/PC_B1B_TEST_EXECUTION_PROTOCOL.md','docs/PC_REFERENCE_0002_COMPATIBILITY.md')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path, value):
    with Path(path).open('x', encoding='utf8') as f:
        json.dump(value, f, indent=2, default=str)
        f.flush(); os.fsync(f.fileno())


def source_hashes():
    files = subprocess.check_output(['git','--no-optional-locks','ls-files','-z'],cwd=ROOT).decode().split('\0')
    return {p:sha(ROOT/p) for p in sorted(set(filter(None,files))|set(EXTRA)) if (ROOT/p).is_file()}


def canonical(node):
    return re.sub(r'^(tests/test_phase8a_contract.py::test_client_cannot_select_settlement_result\[(?:actor_id|holder_user_id)-)[a-f0-9-]{36}(\])$',r'\1<import-uuid4>\2',node)


def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest().upper()


def local(path):
    p = Path(path).resolve()
    if not p.is_relative_to(BASE.resolve()): raise ValueError('Ignored local evidence path required')
    return p


def child_command(request, request_digest=None):
    if request['mode']=='synthetic':
        if not request_digest: raise ValueError('Pinned synthetic request required')
        return [request['python'],'-B',str(SELF),'_synthetic',request['request'], '--digest',request_digest]
    return [request['python'],'-B',str(ROOT/'tools/run_phase8b.py'),request['label'],
            '--profile','business','--execution-profile','full','--isolation',request['isolation']]


def load_request(path, expected_digest=None, verify_sources=False):
    path = local(path)
    if path.name!='request.json' or not re.fullmatch(r'windows-launch-[a-f0-9]{32}',path.parent.name):
        raise ValueError('Exclusive launcher request required')
    if expected_digest is not None and sha(path)!=expected_digest: raise ValueError('Request hash mismatch')
    q = read(path)
    fields = {'version','id','root','directory','request','mode','label','python','pythonw',
              'python_sha','pythonw_sha','user','task','sources','seconds','exit_code',
              'isolation','isolation_sha','preservation','preservation_sha','head'}
    if set(q)!=fields or q['version']!=1 or q['mode'] not in ('synthetic','business'):
        raise ValueError('Request contract mismatch')
    if (q['id']!=path.parent.name.removeprefix('windows-launch-') or
        Path(q['root']).resolve()!=ROOT or Path(q['directory']).resolve()!=path.parent or
        Path(q['request']).resolve()!=path or not re.fullmatch(r'[A-Za-z0-9_]+',q['label']) or
        q['task']!='DoiPinB1b_'+q['id']): raise ValueError('Request identity mismatch')
    base = Path(sys._base_executable).resolve().with_name('python.exe')
    if Path(q['python']).resolve()!=base or Path(q['pythonw']).resolve()!=base.with_name('pythonw.exe'):
        raise ValueError('Pinned Python required')
    if sha(q['python'])!=q['python_sha'] or sha(q['pythonw'])!=q['pythonw_sha']:
        raise ValueError('Python executable changed')
    if not re.fullmatch(r'[^\\]+\\[^\\]+',q['user']): raise ValueError('Exact interactive user required')
    if q['mode']=='synthetic':
        if type(q['seconds']) is not int or not 2<=q['seconds']<=180 or type(q['exit_code']) is not int or not 0<=q['exit_code']<=31:
            raise ValueError('Bounded synthetic request required')
        if any(q[k] is not None for k in ('isolation','isolation_sha','preservation','preservation_sha')):
            raise ValueError('Synthetic request cannot contain database identity')
    else:
        if q['seconds']!=18000 or q['exit_code']!=0: raise ValueError('Business deadline contract')
        for field in ('isolation','preservation'):
            p = local(q[field])
            if sha(p)!=q[field+'_sha']: raise ValueError('Business manifest changed')
    if verify_sources:
        if source_hashes()!=q['sources']: raise ValueError('Source freeze mismatch')
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=q['head']:
            raise ValueError('HEAD changed')
        if subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT).strip():
            raise ValueError('Index must remain unchanged')
    return q


def environment(mode):
    env = {k:v for k,v in os.environ.items() if k.upper() in OS_KEYS}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf8',PYTHONUNBUFFERED='1',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONNOUSERSITE='1')
    if mode=='synthetic': env['PYTHON_DOTENV_DISABLED']='1'
    else: env['PYTHONPATH']=os.pathsep.join([str(ROOT/'.venv/Lib/site-packages'),str(ROOT/'services/backend'),str(ROOT)])
    return env


def powershell(script):
    import base64
    exe=Path(os.environ['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    encoded=base64.b64encode(("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"+script).encode('utf-16-le')).decode()
    result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
        cwd=ROOT,capture_output=True,encoding='utf8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode: raise PermissionError('Task Scheduler operation failed; no alternate privilege path')
    return json.loads(result.stdout.lstrip('\ufeff'))


def ps(value): return "'"+str(value).replace("'","''")+"'"


def action_arguments(path):
    return subprocess.list2cmdline(['-B',str(SELF),'run',str(path),'--digest',sha(path)])


def verify_task(request, xml, effective):
    # XML may omit defaults. Only authenticated COM properties establish the
    # effective principal/settings; absence or an unknown type fails closed.
    if not isinstance(effective,dict):raise ValueError('Effective COM properties required')
    integers={'run_level':0,'logon_type':3,'restart_count':0,'multiple_instances':2,'triggers':0,'actions':1}
    booleans={'start_when_available':False,'enabled':True,'allow_demand_start':True}
    if (any(type(effective.get(k)) is not int or effective[k]!=v for k,v in integers.items()) or
        any(type(effective.get(k)) is not bool or effective[k] is not v for k,v in booleans.items())):
        raise ValueError('Effective task lifecycle policy mismatch')
    sid=effective.get('expected_user_sid')
    if (not isinstance(sid,str) or not re.fullmatch(r'S-1-5-21-(?:\d+-){3}\d+',sid) or
        any(effective.get(k)!=sid for k in ('user_sid','owner_sid','caller_sid')) or
        effective.get('name')!=request['task'] or effective.get('path')!='\\'+request['task']):
        raise ValueError('Effective task account/owner/identity mismatch')
    if (effective.get('execution_limit')!='PT5H' or effective.get('command')!=request['pythonw'] or
        effective.get('arguments')!=action_arguments(request['request']) or effective.get('cwd')!=str(ROOT)):
        raise ValueError('Effective task action/deadline mismatch')
    ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    tree=ET.fromstring(xml);actions=tree.findall('t:Actions/t:Exec',ns)
    def value(path,default=None):return tree.findtext(path,default,ns)
    principals=tree.findall('t:Principals/t:Principal',ns)
    if len(principals)!=1 or principals[0].find('t:GroupId',ns) is not None:
        raise ValueError('One explicit user principal required')
    xml_user=value('t:Principals/t:Principal/t:UserId')
    accounts={sid.casefold(),request['user'].casefold()}
    if isinstance(effective.get('user_id'),str):accounts.add(effective['user_id'].casefold())
    if not isinstance(xml_user,str) or xml_user.casefold() not in accounts:
        raise ValueError('XML principal and effective account disagree')
    if len(actions)!=1 or len(tree.findall('t:Actions/*',ns))!=1 or list(tree.find('t:Triggers',ns) or []):
        raise ValueError('One on-demand action without triggers required')
    action=actions[0]
    if (action.findtext('t:Command',namespaces=ns)!=request['pythonw'] or
        action.findtext('t:Arguments',namespaces=ns)!=action_arguments(request['request']) or
        action.findtext('t:WorkingDirectory',namespaces=ns)!=str(ROOT)):
        raise ValueError('Task action identity mismatch')
    expected={'t:Settings/t:MultipleInstancesPolicy':'IgnoreNew',
              't:Settings/t:ExecutionTimeLimit':'PT5H','t:Principals/t:Principal/t:LogonType':'InteractiveToken'}
    if any(value(path)!=wanted for path,wanted in expected.items()) or value('t:Settings/t:RestartOnFailure/t:Count','0')!='0':
        raise ValueError('Task lifecycle policy mismatch')
    # StartWhenAvailable: schema minOccurs=0/default=false. RunLevel: no
    # inference from omitted XML; effective COM RunLevel must already be 0.
    optional={'t:Settings/t:StartWhenAvailable':'false',
              't:Principals/t:Principal/t:RunLevel':'LeastPrivilege'}
    if any(value(path) not in (None,wanted) or len(tree.findall(path,ns))>1 for path,wanted in optional.items()):
        raise ValueError('XML/effective task policy disagreement')


def prepare(mode, seconds=30, exit_code=0, isolation=None, preservation=None):
    uid=uuid4().hex;folder=BASE/('windows-launch-'+uid);folder.mkdir(exist_ok=False)
    user=powershell('[Security.Principal.WindowsIdentity]::GetCurrent().Name | ConvertTo-Json')
    python=Path(sys._base_executable).resolve().with_name('python.exe');pythonw=python.with_name('pythonw.exe')
    label=('independent_full_' if mode=='business' else 'synthetic_')+uid
    q=dict(version=1,id=uid,root=str(ROOT),directory=str(folder),request=str(folder/'request.json'),
        mode=mode,label=label,python=str(python),pythonw=str(pythonw),python_sha=sha(python),pythonw_sha=sha(pythonw),
        user=user,task='DoiPinB1b_'+uid,sources=source_hashes(),seconds=18000 if mode=='business' else seconds,
        exit_code=exit_code,isolation=str(local(isolation)) if isolation else None,
        preservation=str(local(preservation)) if preservation else None,
        isolation_sha=sha(isolation) if isolation else None,preservation_sha=sha(preservation) if preservation else None,
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    write(folder/'request.json',q);load_request(folder/'request.json',verify_sources=True)
    return folder/'request.json'


def register(path):
    q=load_request(path,verify_sources=True);folder=Path(q['directory'])
    if any((folder/name).exists() for name in ('task_registration.json','registration_reservation.json','claim.json','submission.json')):
        raise FileExistsError('Task registration evidence already reserved')
    args=action_arguments(path)
    write(folder/'registration_reservation.json',dict(request_sha=sha(path),task=q['task']))
    script=f"""
    if([Security.Principal.WindowsIdentity]::GetCurrent().Name -ine {ps(q['user'])}){{throw 'User mismatch'}}
    $s=New-Object -ComObject Schedule.Service;$s.Connect();$f=$s.GetFolder('\\');$d=$s.NewTask(0)
    $d.RegistrationInfo.Description='B1b explicit one-shot; no retry, no reboot trigger'
    $d.Principal.UserId={ps(q['user'])};$d.Principal.LogonType=3;$d.Principal.RunLevel=0
    $d.Settings.Enabled=$true;$d.Settings.AllowDemandStart=$true;$d.Settings.StartWhenAvailable=$false
    $d.Settings.DisallowStartIfOnBatteries=$false;$d.Settings.StopIfGoingOnBatteries=$false
    $d.Settings.MultipleInstances=2;$d.Settings.RestartCount=0;$d.Settings.ExecutionTimeLimit='PT5H'
    $a=$d.Actions.Create(0);$a.Path={ps(q['pythonw'])};$a.Arguments={ps(args)};$a.WorkingDirectory={ps(ROOT)}
    $t=$f.RegisterTaskDefinition({ps(q['task'])},$d,2,{ps(q['user'])},$null,3,$null)
    @{{name=$t.Name;xml=$t.Xml;state=$t.State;user={ps(q['user'])};request_sha={ps(sha(path))}}}|ConvertTo-Json -Depth 4
    """
    powershell(script)  # TASK_CREATE only: an existing task is never updated.
    result=task_info(q);verify_task(q,result['xml'],result['effective'])
    result['request_sha']=sha(path);write(folder/'task_registration.json',result)
    return result


def task_info(q):
    return powershell(f"""$s=New-Object -ComObject Schedule.Service;$s.Connect();$t=$s.GetFolder('\\').GetTask({ps(q['task'])});
    $d=$t.Definition;$a=$d.Actions.Item(1);$sid=[Security.Principal.SecurityIdentifier]
    $caller=[Security.Principal.WindowsIdentity]::GetCurrent()
    $expected=([Security.Principal.NTAccount]::new({ps(q['user'])})).Translate($sid).Value
    $user=([Security.Principal.NTAccount]::new($d.Principal.UserId)).Translate($sid).Value
    $owner=[Security.AccessControl.RawSecurityDescriptor]::new($t.GetSecurityDescriptor(1)).Owner.Value
    $e=@{{name=$t.Name;path=$t.Path;expected_user_sid=$expected;user_id=$d.Principal.UserId;user_sid=$user;owner_sid=$owner;caller_sid=$caller.User.Value;
      run_level=$d.Principal.RunLevel;logon_type=$d.Principal.LogonType;start_when_available=$d.Settings.StartWhenAvailable;
      restart_count=$d.Settings.RestartCount;multiple_instances=$d.Settings.MultipleInstances;triggers=$d.Triggers.Count;actions=$d.Actions.Count;
      execution_limit=$d.Settings.ExecutionTimeLimit;enabled=$d.Settings.Enabled;allow_demand_start=$d.Settings.AllowDemandStart;
      command=$a.Path;arguments=$a.Arguments;cwd=$a.WorkingDirectory}}
    @{{name=$t.Name;state=$t.State;last_result=$t.LastTaskResult;xml=$t.Xml;effective=$e;
      instances=@($t.GetInstances(0)|ForEach-Object {{@{{guid=$_.InstanceGuid;engine_pid=$_.EnginePID;state=$_.State}}}})}}|ConvertTo-Json -Depth 5""")


def submit(path):
    q=load_request(path,verify_sources=True);folder=Path(q['directory'])
    if any((folder/name).exists() for name in ('claim.json','submission.json','submission_reservation.json')): raise FileExistsError('Request already submitted')
    reg=read(folder/'task_registration.json')
    if reg['request_sha']!=sha(path): raise ValueError('Registered request hash mismatch')
    live=task_info(q);verify_task(q,live['xml'],live['effective'])
    if live['xml']!=reg['xml'] or live['effective']!=reg['effective'] or live['instances']:raise ValueError('Task changed or already running')
    # Exclusive reservation precedes RPC; even a failed submission is never retried.
    write(folder/'submission_reservation.json',dict(request_sha=sha(path),submitter=process_info(os.getpid())))
    result=powershell(f"""$s=New-Object -ComObject Schedule.Service;$s.Connect();$t=$s.GetFolder('\\').GetTask({ps(q['task'])});
    $r=$t.Run($null);@{{guid=$r.InstanceGuid;engine_pid=$r.EnginePID;state=$r.State}}|ConvertTo-Json""")
    result.update(submitter=process_info(os.getpid()),request_sha=sha(path),task=q['task'])
    write(folder/'submission.json',result);return result


class Startup(C.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR)]+[(x,W.DWORD) for x in ('x','y','sx','sy','cx','cy','fill','flags')]+[('show',W.WORD),('reserved_size',W.WORD),('reserved_bytes',C.c_void_p),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]


class Process(C.Structure):
    _fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]


class BasicLimits(C.Structure):
    _fields_=[('user',C.c_int64),('job_user',C.c_int64),('flags',W.DWORD),('min_ws',C.c_size_t),('max_ws',C.c_size_t),('active',W.DWORD),('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]


class Limits(C.Structure):
    _fields_=[('basic',BasicLimits),('io',C.c_ulonglong*6),('process_memory',C.c_size_t),('job_memory',C.c_size_t),('peak_process',C.c_size_t),('peak_job',C.c_size_t)]


class Accounting(C.Structure):
    _fields_=[('times',C.c_int64*4),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]


class Entry(C.Structure):
    _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',C.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('exe',W.WCHAR*260)]


def api():
    k=C.WinDLL('kernel32',use_last_error=True)
    declarations={
      'OpenProcess':([W.DWORD,W.BOOL,W.DWORD],W.HANDLE), 'CloseHandle':([W.HANDLE],W.BOOL),
      'GetProcessTimes':([W.HANDLE,*([C.POINTER(W.FILETIME)]*4)],W.BOOL),
      'QueryFullProcessImageNameW':([W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)],W.BOOL),
      'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
      'CreateJobObjectW':([C.c_void_p,W.LPCWSTR],W.HANDLE),
      'SetInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
      'QueryInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
      'AssignProcessToJobObject':([W.HANDLE,W.HANDLE],W.BOOL),
      'CreateProcessW':([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(Startup),C.POINTER(Process)],W.BOOL),
      'ResumeThread':([W.HANDLE],W.DWORD), 'TerminateProcess':([W.HANDLE,W.UINT],W.BOOL),
      'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
      'IsProcessInJob':([W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)],W.BOOL),
      'CreateToolhelp32Snapshot':([W.DWORD,W.DWORD],W.HANDLE),
      'Process32FirstW':([W.HANDLE,C.POINTER(Entry)],W.BOOL),
      'Process32NextW':([W.HANDLE,C.POINTER(Entry)],W.BOOL),
    }
    for name,(args,result) in declarations.items(): getattr(k,name).argtypes=args;getattr(k,name).restype=result
    return k


def check(value):
    if not value: raise C.WinError(C.get_last_error())
    return value


def ancestors(pid):
    k=api();h=k.CreateToolhelp32Snapshot(2,0)
    if h==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    check(h);entry=Entry();entry.size=C.sizeof(entry);items={}
    try:
        okay=k.Process32FirstW(h,C.byref(entry))
        while okay:
            items[entry.pid]=dict(pid=int(entry.pid),parent=int(entry.parent),exe=entry.exe)
            okay=k.Process32NextW(h,C.byref(entry))
    finally:k.CloseHandle(h)
    result=[];current=items.get(pid,{}).get('parent')
    while current in items and len(result)<12:
        value=items[current];result.append(value);current=value['parent']
    return result


def process_info(pid):
    k=api();h=k.OpenProcess(0x1000|0x100000,False,pid)
    if not h:return dict(pid=pid,alive=False,winerror=C.get_last_error())
    try:
        created,ended,kernel,user=(W.FILETIME() for _ in range(4));check(k.GetProcessTimes(h,C.byref(created),C.byref(ended),C.byref(kernel),C.byref(user)))
        ticks=(created.dwHighDateTime<<32)|created.dwLowDateTime
        buffer=C.create_unicode_buffer(32768);size=W.DWORD(len(buffer));check(k.QueryFullProcessImageNameW(h,0,buffer,C.byref(size)))
        code=W.DWORD();check(k.GetExitCodeProcess(h,C.byref(code)));in_job=W.BOOL();check(k.IsProcessInJob(h,None,C.byref(in_job)))
        return dict(pid=pid,creation_ticks=ticks,executable=buffer.value,alive=code.value==259,in_job=bool(in_job.value))
    finally:k.CloseHandle(h)


def status(path, probe=process_info):
    q=load_request(path);folder=Path(q['directory']);exit_file=folder/'launcher_exit.json'
    if exit_file.exists():
        final=read(exit_file)
        if final.get('passed') is not True:return final
        try:
            current=validate_result(q,final['child_exit_code'])
            required=(final['request_sha']==sha(path) and final['source_unchanged'] is True and
                read(folder/'claim.json')['request_sha']==sha(path) and
                read(folder/'task_registration.json')['request_sha']==sha(path) and
                read(folder/'launcher_start.json')['independent_service_ancestry'] is True and
                read(folder/'child_identity.json')['assigned_owned_job'] is True and
                current['passed'] and source_hashes()==q['sources'])
            if q['mode']=='business':
                required=required and all(read(folder/(phase+'_preservation/result.json'))['PASS'] is True for phase in ('before','after'))
            if not required:raise ValueError('Terminal evidence incomplete')
            return final
        except (OSError,KeyError,ValueError,ET.ParseError):
            return dict(state='UNKNOWN',passed=False,reason='Terminal PASS evidence incomplete or inconsistent')
    claim=folder/'claim.json'
    if not claim.exists():return dict(state='UNKNOWN' if any((folder/name).exists() for name in ('submission.json','submission_reservation.json')) else 'NOT_STARTED',passed=False)
    saved=read(claim);current=probe(saved['pid'])
    valid=(saved.get('request_sha')==sha(path) and current.get('alive') and current.get('creation_ticks')==saved['creation_ticks'] and Path(current.get('executable','')).resolve()==Path(saved['executable']).resolve())
    return dict(state='RUNNING' if valid else 'UNKNOWN',passed=False,launcher_pid=saved['pid'],identity_valid=bool(valid),reason=None if valid else 'No terminal evidence; stale/missing process identity')


def db_snapshot(url):
    # Lazy imports keep synthetic workload free of DB/config/provider imports.
    sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
    from sqlalchemy.engine import make_url
    import psycopg
    from psycopg import sql
    u=make_url(url)
    with psycopg.connect(host=u.host,port=u.port,dbname=u.database,user=u.username,password=u.password,autocommit=True,connect_timeout=5,options='-cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000') as c:
        def q(s,p=None):return c.execute(s,p).fetchall()
        def inv():return q("SELECT oid,nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' ORDER BY nspname")
        names=inv();result=dict(system_identifier=q('SELECT system_identifier::text FROM pg_control_system()')[0][0],schema_inventory=names,roles=q('SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolcanlogin,rolreplication,rolbypassrls,rolconfig FROM pg_roles ORDER BY 1'),membership=q('SELECT roleid::regrole::text,member::regrole::text,admin_option FROM pg_auth_members ORDER BY 1,2'),defaults=q('SELECT defaclrole::regrole::text,defaclnamespace::regnamespace::text,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY 1,2,3'),schemas={})
        for oid,schema,owner,acl in names:
            with c.transaction():
                c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                tables=q('SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY 1',(schema,))
                data={t:q(sql.SQL("SELECT count(*),md5(COALESCE(string_agg(to_jsonb(t)::text,'' ORDER BY to_jsonb(t)::text),'')) FROM {} t").format(sql.Identifier(schema,t)))[0] for t, in tables}
                result['schemas'][schema]=dict(data=data,
                    objects=q('SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner),c.relacl::text FROM pg_class c WHERE c.relnamespace=%s ORDER BY 1,2',(oid,)),
                    columns=q('SELECT c.relname,a.attname,a.atttypid::regtype::text,a.attacl::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid WHERE c.relnamespace=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2',(oid,)),
                    constraints=q('SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace=%s ORDER BY 1',(oid,)),
                    triggers=q('SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE c.relnamespace=%s AND NOT t.tgisinternal ORDER BY 1,2',(oid,)),
                    functions=q('SELECT proname,pg_get_function_identity_arguments(oid),pg_get_functiondef(oid) FROM pg_proc WHERE pronamespace=%s ORDER BY 1,2',(oid,)))
        if inv()!=names:raise ValueError('Protected namespace drift')
    return json.loads(json.dumps(result,default=str))


def preserve(request, stage):
    manifest=read(request['preservation']);directory=Path(request['directory'])/(stage+'_preservation');directory.mkdir(exist_ok=False)
    sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'));from dotenv import dotenv_values
    for item in manifest['instances']:
        x=json.loads(subprocess.check_output(['docker','inspect',item['container']],text=True,encoding='utf8',timeout=25))[0]
        expected=item['docker']
        if x['Id']!=expected['id'] or x['Image']!=expected['image'] or not x['State']['Running'] or x['State'].get('Health',{}).get('Status')!='healthy': raise ValueError('Protected Docker identity/health mismatch')
        mounts=[dict(type=m['Type'],name=m.get('Name'),source=m['Source'],destination=m['Destination']) for m in x['Mounts']]
        nets={name:v['NetworkID'] for name,v in x['NetworkSettings']['Networks'].items()}
        if mounts!=expected['mounts'] or nets!=expected['networks'] or x['HostConfig']['PortBindings']!=expected['ports']:raise ValueError('Protected mount/network/port mismatch')
        value=db_snapshot(dotenv_values(item['env_file'],interpolate=False)['DATABASE_ADMIN_URL'])
        write(directory/(str(item['port'])+'.json'),value)
        baseline=local(item['baseline'])
        if sha(baseline)!=item['baseline_sha'] or value!=read(baseline):raise ValueError('Protected catalog/ACL/data mismatch')
    if any(not (ROOT/p).is_file() or sha(ROOT/p)!=h for p,h in manifest['files'].items()):raise ValueError('Protected evidence changed')
    write(directory/'result.json',dict(PASS=True,instances=len(manifest['instances']),files=len(manifest['files'])))


def validate_result(request, code):
    folder=Path(request['directory'])
    if request['mode']=='synthetic':
        final=read(folder/'child/final.json')
        return dict(state='COMPLETED',passed=code==0 and final['exit_code']==0,child_exit_code=code)
    run=BASE/('b1b-harness-'+request['label']);end=read(run/'exit.json')
    x=ET.parse(run/'results.xml');tests=x.findall('.//testcase');nodes=read(run/'collected.json')['node_ids']
    expected=read(read(request['isolation'])['collection_file'])['node_ids']
    events=[json.loads(v) for v in (run/'node_events.jsonl').read_text().splitlines()];calls=[v for v in events if v['phase']=='call']
    okay=(code==0 and end['state']=='COMPLETED' and end['passed'] is True and end['test_exit_code']==0 and end['post_checks']=='PASS' and
        len(tests)==len(nodes)==len(calls)==805 and len({v['nodeid'] for v in calls})==805 and
        {v['nodeid'] for v in calls}==set(nodes) and all(v['outcome']=='passed' for v in calls) and
        {canonical(v) for v in nodes}=={canonical(v) for v in expected} and
        not x.findall('.//failure') and not x.findall('.//error') and not x.findall('.//skipped'))
    return dict(state='COMPLETED',passed=okay,child_exit_code=code,runner=end,tests=len(tests),run_directory=str(run))


def run_request(path, request_digest):
    q=load_request(path,request_digest,True);folder=Path(q['directory']);k=api()
    if Path(sys.executable).resolve()!=Path(q['pythonw']).resolve() or Path.cwd().resolve()!=ROOT:raise ValueError('Task action executable/cwd mismatch')
    me=process_info(os.getpid());chain=ancestors(os.getpid())
    actual_user=powershell('[Security.Principal.WindowsIdentity]::GetCurrent().Name | ConvertTo-Json')
    if actual_user.lower()!=q['user'].lower():raise ValueError('Task execution user mismatch')
    live=task_info(q);verify_task(q,live['xml'],live['effective'])
    if any('codex' in x['exe'].lower() for x in chain) or not any(x['exe'].lower() in ('svchost.exe','taskeng.exe','taskhostw.exe') for x in chain):raise ValueError('Service-owned independent ancestry not verified')
    write(folder/'claim.json',dict(**me,ancestors=chain,user=actual_user,command_hash=digest(sys.argv),request_sha=request_digest))
    job=None;pi=Process();assigned=False;sequence=0
    try:
        until=time.monotonic()+15
        while not (folder/'submission.json').exists():
            if time.monotonic()>until:raise TimeoutError('Submission receipt absent')
            time.sleep(.1)
        receipt=read(folder/'submission.json')
        if receipt['request_sha']!=request_digest or receipt['task']!=q['task']:raise ValueError('Submission identity mismatch')
        write(folder/'launcher_start.json',dict(at=datetime.now(timezone.utc).isoformat(),launcher=me,ancestors=chain,submission=receipt,independent_service_ancestry=True))
        if q['mode']=='business':preserve(q,'before')
        C.set_last_error(0)
        job=check(k.CreateJobObjectW(None,'Local\\DoiPinB1b_'+q['id']))
        if C.get_last_error()==183:raise ValueError('Existing job cannot be adopted')
        limits=Limits();limits.basic.flags=0x2000
        check(k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        command=child_command(q,request_digest)
        env=environment(q['mode']);block=C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items(),key=lambda x:x[0].upper()))+'\0\0')
        with (folder/'child_stdout.log').open('xb') as log,open(os.devnull,'rb') as stdin:
            handles=[msvcrt.get_osfhandle(log.fileno()),msvcrt.get_osfhandle(stdin.fileno())]
            for handle in handles:os.set_handle_inheritable(handle,True)
            si=Startup();si.cb=C.sizeof(si);si.flags=0x100;si.stdin=handles[1];si.stdout=si.stderr=handles[0]
            try:check(k.CreateProcessW(q['python'],C.create_unicode_buffer(subprocess.list2cmdline(command)),None,None,True,0x08000000|4|0x400,C.cast(block,C.c_void_p),str(ROOT),C.byref(si),C.byref(pi)))
            finally:
                for handle in handles:os.set_handle_inheritable(handle,False)
            check(k.AssignProcessToJobObject(job,pi.process));assigned=True
            in_job=W.BOOL();check(k.IsProcessInJob(pi.process,job,C.byref(in_job)))
            if not in_job.value:raise ValueError('Child job membership absent')
            write(folder/'child_identity.json',dict(**process_info(pi.pid),command=command,command_hash=digest(command),assigned_owned_job=True,created_suspended=True))
            if k.ResumeThread(pi.thread)==0xffffffff:raise C.WinError(C.get_last_error())
            k.CloseHandle(pi.thread);pi.thread=None
            start=time.monotonic();next_beat=0
            while True:
                now=time.monotonic()
                if now>=next_beat:
                    sequence+=1;account=Accounting();check(k.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
                    write(folder/f'heartbeat_{sequence:05}.json',dict(at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=now-start,launcher_pid=os.getpid(),child_pid=int(pi.pid),job_active_processes=account.active))
                    next_beat=now+10
                result=k.WaitForSingleObject(pi.process,2000)
                if result==0:break
                if result!=258:raise C.WinError(C.get_last_error())
                if now-start>q['seconds']+60:raise TimeoutError('Independent launcher deadline')
            code=W.DWORD();check(k.GetExitCodeProcess(pi.process,C.byref(code)))
        account=Accounting();quiet_deadline=time.monotonic()+5
        while True:
            check(k.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
            if not account.active or time.monotonic()>quiet_deadline:break
            time.sleep(.1)
        if account.active:raise ValueError('Owned descendants still active after runner exit')
        final=validate_result(q,code.value)
        if q['mode']=='business':preserve(q,'after')
        if source_hashes()!=q['sources']:raise ValueError('Source changed during execution')
        final.update(at=datetime.now(timezone.utc).isoformat(),request_sha=request_digest,source_unchanged=True,no_retry=True)
        write(folder/'launcher_exit.json',final)
        return 0 if final['passed'] else 1
    except BaseException as error:
        write(folder/'launcher_exit.json',dict(state='UNKNOWN',passed=False,error_type=type(error).__name__,winerror=getattr(error,'winerror',None),no_retry=True))
        return 1
    finally:
        if pi.process and not assigned:k.TerminateProcess(pi.process,1)
        if job:k.CloseHandle(job)
        if pi.thread:k.CloseHandle(pi.thread)
        if pi.process:k.CloseHandle(pi.process)


def synthetic_child(path, request_digest):
    q=load_request(path,request_digest,True)
    if q['mode']!='synthetic' or any(k in os.environ for k in ('DATABASE_URL','DATABASE_ADMIN_URL','MIGRATION_DATABASE_URL','PAYMENT_SERVICE_KEY')):raise ValueError('Synthetic effects forbidden')
    folder=Path(q['directory'])/'child';folder.mkdir(exist_ok=False)
    write(folder/'identity.json',dict(**process_info(os.getpid()),ancestors=ancestors(os.getpid()),no_database_provider_effects=True))
    start=time.monotonic();number=0
    while time.monotonic()-start<q['seconds']:
        number+=1;write(folder/f'heartbeat_{number:04}.json',dict(at=datetime.now(timezone.utc).isoformat(),pid=os.getpid()));time.sleep(1)
    write(folder/'final.json',dict(exit_code=q['exit_code'],no_database_provider_effects=True))
    return q['exit_code']


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--mode',choices=('synthetic','business'),required=True);p.add_argument('--seconds',type=int,default=30);p.add_argument('--exit-code',type=int,default=0);p.add_argument('--isolation',type=Path);p.add_argument('--preservation',type=Path)
    for name in ('register','submit','status','task-info','run','_synthetic'):
        p=sub.add_parser(name);p.add_argument('request',type=Path);p.add_argument('--digest')
    args=parser.parse_args()
    if args.action=='prepare':print(prepare(args.mode,args.seconds,args.exit_code,args.isolation,args.preservation));return 0
    if args.action=='register':print(json.dumps(register(args.request)));return 0
    if args.action=='submit':print(json.dumps(submit(args.request)));return 0
    if args.action=='status':print(json.dumps(status(args.request)));return 0
    if args.action=='task-info':print(json.dumps(task_info(load_request(args.request))));return 0
    if not args.digest:raise ValueError('Pinned request digest required')
    return run_request(args.request,args.digest) if args.action=='run' else synthetic_child(args.request,args.digest)


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        if sys.stderr:print(json.dumps(dict(error_type=type(error).__name__,winerror=getattr(error,'winerror',None))),file=sys.stderr)
        sys.exit(1)
