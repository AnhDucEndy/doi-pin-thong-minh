"""Trusted Python-stack controls, NOT an OS/native-code sandbox.

Install before importing Backend/SQLAlchemy/simulators. Direct hostile ctypes or
unreviewed libpq entrypoints are outside this boundary; business launch stays locked.
"""
import contextvars
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from urllib.parse import urlsplit

from .adapter import require


def database_parameters(config, password, conninfo, kwargs):
    from psycopg.conninfo import conninfo_to_dict
    driver_keys={'autocommit','row_factory','context','prepare_threshold','cursor_factory'}
    data=conninfo_to_dict(conninfo, **{k:v for k,v in kwargs.items() if k not in driver_keys})
    require(set(data) <= {'host','hostaddr','port','dbname','user','password','options','connect_timeout','application_name'}, 'DB_PARAMETERS')
    require((data.get('host'),int(data.get('port',0)),data.get('dbname'),data.get('user'),data.get('password')) ==
            ('127.0.0.1',config.target[0],config.database,config.role,password),'NATIVE_DB_BINDING')
    require(data.get('hostaddr','127.0.0.1')=='127.0.0.1','DB_HOSTADDR')
    # Ignore caller options: no search_path or writable fallback during integration.
    data.update(hostaddr='127.0.0.1',options='-csearch_path='+config.schema+',pg_catalog -cdefault_transaction_read_only=on -cstatement_timeout=15000 -clock_timeout=5000',connect_timeout='5')
    return data, {k:v for k,v in kwargs.items() if k in driver_keys}


def install(config, password, output, record):
    """One-shot bootstrap. HTTP routes here are integration-only, never S1 routes."""
    config.validate(); output=Path(output).resolve()
    require(not any(k in os.environ for k in ('DATABASE_ADMIN_URL','MIGRATION_DATABASE_URL','PGSERVICE','PGPASSFILE')), 'CHILD_AUTHORITY_ENV')
    import dotenv
    dotenv.load_dotenv=lambda *a,**k: False
    import psycopg
    native_db=psycopg.Connection.connect

    def connect(conninfo='', **kwargs):
        data, extra=database_parameters(config,password,conninfo,kwargs)
        c=native_db(**data,**extra)
        require((c.info.host,c.info.port,c.info.dbname,c.info.user)==('127.0.0.1',config.target[0],config.database,config.role),'NATIVE_CONNECTED_BINDING')
        record(dict(event='native_db_connected',backend_pid=c.info.backend_pid,role=c.info.user,port=c.info.port,schema=config.schema))
        return c

    psycopg.connect=connect
    psycopg.Connection.connect=classmethod(lambda cls,conninfo='',**kwargs:connect(conninfo,**kwargs))
    async def no_async(*a,**k):
        require(False,'UNAPPROVED_ASYNC_DB')
    psycopg.AsyncConnection.connect=classmethod(no_async)

    scope=contextvars.ContextVar('integration_http',default=None)
    pair_scope=contextvars.ContextVar('integration_socketpair',default=False)
    native_pair=socket.socketpair
    require(native_pair is socket._fallback_socketpair,'UNREVIEWED_SOCKETPAIR')
    code=native_pair.__code__
    native_connect=socket.socket.connect;native_ex=socket.socket.connect_ex

    def pair_ok(s,address,frame):
        if not pair_scope.get() or frame.f_code is not code or frame.f_locals.get('csock') is not s:return False
        listener=frame.f_locals.get('lsock')
        if not isinstance(listener,socket.socket) or listener.family!=socket.AF_INET or s.family!=socket.AF_INET:return False
        return (listener.type==s.type==socket.SOCK_STREAM and listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
                and tuple(address)==tuple(listener.getsockname())==(frame.f_locals.get('addr'),frame.f_locals.get('port'))
                and address[0]=='127.0.0.1' and address[1] not in range(5432,5450))

    def endpoint(address):
        require(isinstance(address,tuple) and len(address)==2 and address[0]=='127.0.0.1'
                and scope.get()==address and address[1] in config.ports,'RAW_SOCKET_DENIED')

    def sock_connect(s,address):
        if not pair_ok(s,address,sys._getframe(1)):endpoint(address)
        return native_connect(s,address)
    def sock_ex(s,address):
        endpoint(address);return native_ex(s,address)
    def pair(*a,**k):
        token=pair_scope.set(True)
        try:
            left,right=native_pair(*a,**k)
            require(left.getpeername()==right.getsockname() and right.getpeername()==left.getsockname(),'SOCKETPAIR_PEERS')
            record(dict(event='stdlib_socketpair',family=int(left.family)))
            return left,right
        finally:pair_scope.reset(token)
    socket.socket.connect=sock_connect;socket.socket.connect_ex=sock_ex;socket.socketpair=pair
    native_dns=socket.getaddrinfo
    def dns(host,port,*a,**k):
        endpoint((host,int(port)))
        return native_dns(host,port,*a,**k)
    socket.getaddrinfo=dns
    def denied(*a,**k):require(False,'UNAPPROVED_TRANSPORT_OR_PROCESS')
    socket.socket.sendto=denied
    socket.gethostbyname=denied;socket.gethostbyname_ex=denied;socket.gethostbyaddr=denied
    subprocess.Popen=denied;os.system=denied
    import httpx
    native_http=httpx.HTTPTransport.handle_request
    def http(transport,request):
        u=request.url
        require(u.scheme=='http' and u.host=='127.0.0.1' and not u.userinfo and not u.query,'HTTP_URL')
        require((u.port,request.method,u.path) in config.routes and u.raw_path.decode('ascii')==u.path,'HTTP_ROUTE')
        require(not u.path.startswith('/mock/v1/refunds'),'REFUND_DISPATCH')
        token=scope.set(('127.0.0.1',u.port))
        try:response=native_http(transport,request)
        finally:scope.reset(token)
        require(not 300<=response.status_code<400,'HTTP_REDIRECT')
        record(dict(event='http',port=u.port,method=request.method,path=u.path,status=response.status_code))
        return response
    httpx.HTTPTransport.handle_request=http
    httpx.AsyncHTTPTransport.handle_async_request=no_async
    # Trust_env=False on actual application clients; also neutralize proxy input.
    require(not any(k.lower().endswith('_proxy') for k in os.environ),'PROXY_ENV')
    native_sqlite=sqlite3.connect
    def sqlite(path,*a,**k):
        require(not str(path).startswith('file:') and Path(path).resolve().is_relative_to(output),'SQLITE_SCOPE')
        return native_sqlite(path,*a,**k)
    sqlite3.connect=sqlite
    record(dict(event='guard_installed',kind='integration_only',native_db='psycopg.Connection.connect',business_launch=False))
