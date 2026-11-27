"""Portable startup guard; endpoint/credential/output isolation, no business patches."""
import os,json,sys,re,uuid,socket,subprocess,sqlite3,contextvars
from pathlib import Path
from urllib.parse import urlsplit,unquote
ROOT=Path(os.environ['G6_WORKSPACE']).resolve();OUT=Path(os.environ['G6_OUTPUT']).resolve()
SCENARIO=Path(os.environ['G6_SCENARIO_OUTPUT']).resolve();PORT=int(os.environ['G6_ISOLATION_PORT'])
DATABASE=os.environ['G6_DATABASE'];GUARD=Path(__file__).parent
def record(name,value):
    with (SCENARIO/(name+'-'+uuid.uuid4().hex+'.json')).open('x',encoding='utf-8') as f:json.dump(value,f,default=str)
class GuardDenied(RuntimeError):pass
def refuse(kind,**facts):
    record('ISOLATION_REFUSAL',dict(pid=os.getpid(),kind=kind,**facts))
    raise GuardDenied('G6 isolation refused: '+kind)
fixture=json.loads((OUT/'authorized_fixture.json').read_text())
if (not isinstance(fixture.get('protected_ports'),list) or not fixture['protected_ports']
        or not all(type(p) is int and 1<=p<=65535 for p in fixture['protected_ports'])):refuse('invalid protected port inventory')
PROTECTED_PORTS=frozenset(fixture['protected_ports'])|{PORT}
if PORT!=fixture['port'] or DATABASE!=fixture['database']:refuse('unauthorized test database configuration')
expected={}
for key in ('DATABASE_ADMIN_URL','MIGRATION_DATABASE_URL','DATABASE_URL'):
    u=urlsplit(os.environ[key].replace('postgresql+psycopg://','postgresql://'))
    if u.hostname!='127.0.0.1' or u.port!=PORT or u.path!='/'+DATABASE or u.query:refuse('database environment')
    expected[unquote(u.username)]=unquote(u.password)
if os.environ.get('PYTHON_DOTENV_DISABLED')!='1':refuse('dotenv enabled')
import dotenv
def disabled_dotenv(*args,**kwargs):return False
dotenv.load_dotenv=disabled_dotenv
import psycopg
from psycopg.conninfo import conninfo_to_dict
native_connect=psycopg.connect
def connect(conninfo='',**kwargs):
    data=conninfo_to_dict(conninfo,**{k:v for k,v in kwargs.items() if k not in ('autocommit','row_factory','context','prepare_threshold','cursor_factory')})
    if data.get('host')!='127.0.0.1' or int(data.get('port',0))!=PORT or data.get('dbname')!=DATABASE or data.get('password')!=expected.get(data.get('user')):refuse('database connection')
    # This recovery invocation is read-only startup, never G6 execution.
    schema=fixture['schema']
    if not re.fullmatch(r'phase5_test_[a-f0-9]{12}',schema):refuse('startup fixture schema')
    kwargs['options']='-csearch_path='+schema+',pg_catalog -cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000'
    record('DB_READONLY_CONNECT',dict(pid=os.getpid(),port=PORT,database=DATABASE,schema=schema,user=data.get('user')))
    return native_connect(conninfo,**kwargs)
psycopg.connect=connect
native_mkdir=Path.mkdir
def mkdir(path,*args,**kwargs):
    p=path.resolve()
    if p.parent==ROOT/'.cache' and re.fullmatch('b1b_real_[0-9a-f]{32}',p.name):
        if p.exists() or (SCENARIO/'runtime_identity.json').exists():refuse('runtime adoption or second runtime')
        result=native_mkdir(path,*args,**kwargs)
        with (SCENARIO/'runtime_identity.json').open('x',encoding='utf-8') as f:json.dump(dict(path=str(p),pid=os.getpid()),f)
        return result
    return native_mkdir(path,*args,**kwargs)
Path.mkdir=mkdir
def owned_runtime():
    p=Path(json.loads((SCENARIO/'runtime_identity.json').read_text())['path']).resolve()
    if p.parent!=ROOT/'.cache' or not p.is_dir():refuse('runtime identity')
    return p
native_sqlite=sqlite3.connect
def sqlite_connect(database,*args,**kwargs):
    raw=str(database)
    if raw.startswith('file:'):
        raw=unquote(urlsplit(raw).path)
        if re.match(r'^/[A-Za-z]:',raw):raw=raw[1:]
    path=Path(raw.split('?')[0]).resolve()
    if not path.is_relative_to(owned_runtime()):refuse('foreign SQLite')
    return native_sqlite(database,*args,**kwargs)
sqlite3.connect=sqlite_connect
native_write=Path.write_text
def write_text(path,data,*args,**kwargs):
    if path.resolve().is_relative_to(ROOT/'docs'):
        if path.name!='PHASE5_TEST_ENVIRONMENT.json':refuse('unexpected source report write')
        target=SCENARIO/'reports'/path.name
        with target.open('x',encoding='utf-8') as f:return f.write(data)
    return native_write(path,data,*args,**kwargs)
Path.write_text=write_text
native_popen=subprocess.Popen
class Popen(native_popen):
    def __init__(self,args,*a,**kw):
        if not isinstance(args,(list,tuple)) or kw.get('shell'):refuse('shell subprocess')
        command=[str(x) for x in args];joined=' '.join(command)
        allowed={str((GUARD/'process_probe.py').resolve()),str((GUARD/'api_smoke.py').resolve())}
        if not any(str(Path(x).resolve()) in allowed for x in command[1:] if x.endswith('.py')):refuse('unexpected startup child command')
        env=dict(kw.get('env') or os.environ)
        for key in ('DATABASE_ADMIN_URL','MIGRATION_DATABASE_URL','DATABASE_URL'):
            if env.get(key)!=os.environ[key]:refuse('child database override')
        env['PYTHONPATH']=os.pathsep.join([str(GUARD),str(ROOT/'.venv/Lib/site-packages'),env.get('PYTHONPATH','')])
        env['PYTHON_DOTENV_DISABLED']='1';env['PYTHONDONTWRITEBYTECODE']='1'
        kw['env']=env
        for flag in ('--port',):
            if flag in command:
                port=int(command[command.index(flag)+1]);p=SCENARIO/('owned-port-'+str(port))
                if p.exists():refuse('duplicate listener port')
                with p.open('x') as f:f.write('owned uvicorn/payment listener')
        super().__init__(args,*a,**kw)
        self._g6_exit_recorded=False
        record('child-start',dict(pid=self.pid,parent=os.getpid(),command=command))
    def _record_exit(self,code,method):
        if code is not None and not getattr(self,'_g6_exit_recorded',False):
            self._g6_exit_recorded=True
            record('child-exit',dict(pid=self.pid,exit=code,observed_by=method))
    def poll(self):
        code=super().poll();self._record_exit(code,'poll');return code
    def wait(self,*a,**kw):
        code=super().wait(*a,**kw);self._record_exit(code,'wait');return code
    def kill(self):record('child-kill',dict(pid=self.pid,actor=os.getpid()));return super().kill()
    def terminate(self):record('child-stop',dict(pid=self.pid,actor=os.getpid()));return super().terminate()
subprocess.Popen=Popen
def endpoint(host,port):
    if int(port) in PROTECTED_PORTS:refuse('protected database raw socket',host=host,port=port)
    if host not in ('127.0.0.1','localhost','::1') or not (SCENARIO/('owned-port-'+str(port))).exists():refuse('external or unowned socket',host=host,port=port)
native_socket=socket.socket.connect
native_connect_ex=socket.socket.connect_ex
native_pair=socket.socketpair
if native_pair is not socket._fallback_socketpair:refuse('unreviewed socketpair implementation')
fallback_code=native_pair.__code__
pair_scope=contextvars.ContextVar('g6_internal_pair',default=None)
def internal_pair(self,address,caller):
    # Context alone grants no permission. Require the exact trusted stdlib code
    # and the exact connector/listener allocated by that active invocation.
    if pair_scope.get() is None or caller.f_code is not fallback_code:return None
    frame=caller.f_locals
    if frame.get('csock') is not self:return None
    listener=frame.get('lsock')
    if not isinstance(listener,socket.socket) or self.family!=socket.AF_INET or listener.family!=socket.AF_INET:return None
    if self.type!=socket.SOCK_STREAM or listener.type!=socket.SOCK_STREAM:return None
    bound=listener.getsockname()
    if tuple(address)!=tuple(bound) or bound[0]!='127.0.0.1' or bound[1] in PROTECTED_PORTS:return None
    if listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)!=1:return None
    if tuple(address)!=(frame.get('addr'),frame.get('port')):return None
    return dict(pair_id=pair_scope.get(),family=int(self.family),family_name=self.family.name,
        listener=list(bound),caller_file=caller.f_code.co_filename,
        caller_line=caller.f_lineno,provenance='exact stdlib code + exact sockets + listening peer + scoped call')
def socket_connect(self,address):
    facts=internal_pair(self,address,sys._getframe(1))
    if facts:
        record('PAIR_INTERNAL_CONNECT',dict(pid=os.getpid(),**facts))
        try:
            result=native_socket(self,address)
        except OSError as error:
            record('PAIR_CONNECT_OUTCOME',dict(pid=os.getpid(),pair_id=facts['pair_id'],exception_type=type(error).__name__,errno=error.errno,winerror=getattr(error,'winerror',None)))
            raise
        record('PAIR_CONNECT_OUTCOME',dict(pid=os.getpid(),pair_id=facts['pair_id'],returned=True))
        return result
    if isinstance(address,tuple):endpoint(address[0],address[1])
    else:refuse('non-IP socket')
    return native_socket(self,address)
socket.socket.connect=socket_connect
def socket_connect_ex(self,address):
    if isinstance(address,tuple):endpoint(address[0],address[1])
    else:refuse('non-IP socket')
    return native_connect_ex(self,address)
socket.socket.connect_ex=socket_connect_ex
def socketpair(*args,**kwargs):
    identity=uuid.uuid4().hex;token=pair_scope.set(identity)
    try:
        left,right=native_pair(*args,**kwargs)
        if left.family!=socket.AF_INET or right.family!=socket.AF_INET:
            left.close();right.close();refuse('unverified socketpair family')
        record('PAIR_CONNECTED',dict(pid=os.getpid(),pair_id=identity,family=int(left.family),family_name=left.family.name,
            left_local=list(left.getsockname()),left_peer=list(left.getpeername()),right_local=list(right.getsockname()),right_peer=list(right.getpeername())))
        return left,right
    finally:pair_scope.reset(token)
socket.socketpair=socketpair
def no_datagrams(self,*args,**kwargs):refuse('datagram send forbidden')
socket.socket.sendto=no_datagrams
import httpx
sync=httpx.HTTPTransport.handle_request;async_native=httpx.AsyncHTTPTransport.handle_async_request
def check_http(request):
    if '/mock/v1/refunds' in request.url.path:refuse('provider Refund call')
    if request.url.scheme!='http' or request.url.port==PORT:refuse('HTTP scheme or database port')
    endpoint(request.url.host,request.url.port)
    if request.method!='GET' or request.url.path not in ('/health','/ping'):refuse('startup-only HTTP route')
def handle(self,request):check_http(request);return sync(self,request)
async def ahandle(self,request):check_http(request);return await async_native(self,request)
httpx.HTTPTransport.handle_request=handle;httpx.AsyncHTTPTransport.handle_async_request=ahandle
record('guard-ready',dict(pid=os.getpid(),source=str(__file__),database_port=PORT,database=DATABASE,dotenv_disabled=True))
