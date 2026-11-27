"""One fail-fast focused guard batch; no API factory or database connection."""
import os,sys,json,time,socket,threading,asyncio,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from xml.etree.ElementTree import Element,SubElement,ElementTree
import isolation as guard
import httpx,uvicorn
OUT=Path(os.environ['G6_SCENARIO_OUTPUT']);ROOT=Path(__file__).resolve().parent
facts=[]
def fact(name,**data):facts.append(dict(name=name,**data))
class Controls(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.getenv('G6_GUARD_READY'),'1')
        self.prior_socket_timeout=socket.getdefaulttimeout();socket.setdefaulttimeout(3)
    def tearDown(self):socket.setdefaulttimeout(self.prior_socket_timeout)
    def blocked(self,callback):
        with patch.object(guard,'native_socket') as native,patch.object(guard,'native_connect_ex') as ex:
            with self.assertRaises(guard.GuardDenied):callback()
            self.assertEqual(native.call_count,0);self.assertEqual(ex.call_count,0)
    def test_A_actual_socketpair(self):
        a,b=socket.socketpair()
        try:
            a.settimeout(2);b.settimeout(2)
            a.sendall(b'controller-to-loop');self.assertEqual(b.recv(64),b'controller-to-loop')
            b.sendall(b'loop-to-controller');self.assertEqual(a.recv(64),b'loop-to-controller')
            self.assertEqual(a.family,socket.AF_INET)
            self.assertEqual(a.getsockname(),b.getpeername());self.assertEqual(b.getsockname(),a.getpeername())
            fact('A',family=int(a.family),family_name=a.family.name,left=a.getsockname(),right=b.getsockname(),duplex=True)
        finally:a.close();b.close()
        self.assertIsNone(guard.pair_scope.get())
    def test_B_actual_uvicorn_proactor_loop(self):
        factory=uvicorn.Config('app.main:create_app',factory=True,loop='asyncio',log_level='critical').get_loop_factory()
        loop=factory();self.assertIsInstance(loop,asyncio.ProactorEventLoop)
        try:
            future=loop.create_future()
            thread=threading.Thread(target=lambda:loop.call_soon_threadsafe(future.set_result,'REAL_THREAD_ACK'))
            thread.start()
            self.assertEqual(loop.run_until_complete(asyncio.wait_for(future,2)),'REAL_THREAD_ACK')
            thread.join(2);self.assertFalse(thread.is_alive())
            fact('B',loop=type(loop).__name__,uvicorn=uvicorn.__version__,cross_thread_ACK=True)
        finally:loop.close()
        self.assertIsNone(guard.pair_scope.get())
    def test_D_controller_to_owned_mock(self):
        port=int(os.environ['G6_PING_PORT'])
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path!='/ping':self.send_error(404);return
                assert os.getenv('G6_GUARD_READY')=='1'
                body=json.dumps(dict(ping='ok',pid=os.getpid(),guard=True)).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            response=httpx.get('http://127.0.0.1:'+str(port)+'/ping',trust_env=False,timeout=3)
            self.assertEqual(response.status_code,200);self.assertEqual(response.json(),dict(ping='ok',pid=os.getpid(),guard=True))
            fact('D',mock_port=port,status=200,guard_enabled_in_controller_and_handler=True,API_dependency='Not an app.main API readiness result')
        finally:server.shutdown();server.server_close();thread.join(2)
    def test_E_external_connect_and_connect_ex(self):
        for method in ('connect','connect_ex'):
            with self.subTest(method=method):
                with socket.socket() as s:self.blocked(lambda:getattr(s,method)(('203.0.113.9',443)))
        fact('E',blocked=True,transport_calls=0,targets='TEST-NET, mocked before native connect')
    def test_F_unowned_loopback(self):
        for family,address in [(socket.AF_INET,('127.0.0.1',60001)),(socket.AF_INET6,('::1',60002))]:
            with socket.socket(family) as s:self.blocked(lambda:s.connect(address))
        fact('F',blocked=True,transport_calls=0)
    def test_G_protected_database_ports(self):
        for port in sorted(guard.PROTECTED_PORTS):
            for method in ('connect','connect_ex'):
                with self.subTest(port=port,method=method):
                    with socket.socket() as s:self.blocked(lambda:getattr(s,method)(('127.0.0.1',port)))
        # A forged allowlist marker cannot authorize a protected DB socket.
        protected=min(guard.PROTECTED_PORTS)
        marker=OUT/('owned-port-'+str(protected))
        with marker.open('x') as f:f.write('synthetic negative-control marker; retained')
        with socket.socket() as s:self.blocked(lambda:s.connect(('127.0.0.1',protected)))
        fact('G',ports=sorted(guard.PROTECTED_PORTS),methods=['connect','connect_ex'],forged_marker_rejected=True,actual_DB_attempts=0)
    def test_H_provider_hardware_and_datagram(self):
        with patch.object(guard,'sync') as transport:
            with self.assertRaises(guard.GuardDenied):
                httpx.post('http://127.0.0.1:'+os.environ['G6_PING_PORT']+'/mock/v1/refunds',json={},trust_env=False)
            self.assertEqual(transport.call_count,0)
        with socket.socket() as s:self.blocked(lambda:s.connect(('192.0.2.99',8080)))
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            with self.assertRaises(guard.GuardDenied):s.sendto(b'never sent',('192.0.2.99',8080))
        fact('H',provider_HTTP_transport_calls=0,hardware_TCP_calls=0,UDP_send_blocked=True)
    def test_I_scope_alone_cannot_authorize(self):
        token=guard.pair_scope.set('negative-control-not-real-socketpair')
        try:
            with socket.socket() as s:self.blocked(lambda:s.connect(('127.0.0.1',60003)))
        finally:guard.pair_scope.reset(token)
        self.assertIsNone(guard.pair_scope.get());fact('I',ordinary_connect_during_active_scope_blocked=True)
    def test_J_early_child_exit_is_recorded(self):
        child=subprocess.Popen([sys._base_executable,'-B',str(ROOT/'process_probe.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+8
            while child.poll() is None:
                self.assertLess(time.monotonic(),deadline,'Probe exit deadline');time.sleep(.01)
            self.assertEqual(child.returncode,7);self.assertEqual(child.wait(timeout=2),7)
            stdout,stderr=child.communicate(timeout=2);self.assertEqual(stderr,b'')
            matches=[json.loads(p.read_text()) for p in OUT.glob('child-exit-*.json') if json.loads(p.read_text())['pid']==child.pid]
            self.assertEqual(len(matches),1);self.assertEqual(matches[0]['exit'],7)
            self.assertEqual(matches[0]['observed_by'],'poll')
            fact('J',pid=child.pid,expected_deliberate_exit=7,observed=matches[0],wait_exit=7)
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=3)
def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    names=[t.id() for t in suite]
    with (OUT/'run.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2,failfast=True).run(suite)
    failures={t.id():message for t,message in result.failures};errors={t.id():message for t,message in result.errors}
    xml=Element('testsuite',name='G6 socket guard focused controls',tests=str(result.testsRun),failures=str(len(failures)),errors=str(len(errors)),skipped='0')
    for name in names[:result.testsRun]:
        node=SubElement(xml,'testcase',name=name)
        if name in failures:SubElement(node,'failure').text=failures[name]
        if name in errors:SubElement(node,'error').text=errors[name]
    ElementTree(xml).write(OUT/'results.xml',encoding='UTF-8',xml_declaration=True)
    summary=dict(PASS=result.wasSuccessful() and result.testsRun==9,planned=9,executed=result.testsRun,passed=result.testsRun-len(failures)-len(errors),failed=len(failures),errors=len(errors),facts=facts,guard_enabled=os.getenv('G6_GUARD_READY')=='1',database_connections=len(list(OUT.glob('DB_READONLY_CONNECT-*.json'))),API_startup='NOT RUN: controls never launch an API',business_workflows=0)
    with (OUT/'result.json').open('x',encoding='utf-8') as f:json.dump(summary,f,indent=2)
    print(json.dumps(summary),flush=True)
    return 0 if summary['PASS'] else 1
if __name__=='__main__':raise SystemExit(main())
