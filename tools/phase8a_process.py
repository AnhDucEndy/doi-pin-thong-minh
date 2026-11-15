"""Test-only delivery loss. Never imported by production.

Physical events remain in the durable outbox with their original timestamps.
Only their delivery is withheld; ACK, snapshot and telemetry use real HTTP.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'services/backend')]
from simulators.device.main import Simulator, main

original = Simulator.flush

def flush(self):
    receipts = []
    for row in self.conn.execute('SELECT * FROM events WHERE sent=0 ORDER BY rowid').fetchall():
        body = json.loads(row['body'])
        if body['kind'] in ('DOOR', 'PRESENCE') and body.get('command_id'):
            command = self.conn.execute('SELECT body FROM commands WHERE id=?', (body['command_id'],)).fetchone()
            if command and json.loads(command['body'])['kind'] == 'OPEN_SUPPLY':
                continue
        response = self.http.post('/v1/device/events', json=body)
        response.raise_for_status()
        assert response.status_code == 202
        self.conn.execute('UPDATE events SET sent=1,receipt=? WHERE id=?',
            (json.dumps(response.json()), row['id']))
        self.conn.commit()
        receipts.append(response.json())
    return receipts

Simulator.flush = flush
# Explicit test-operator signal, read only by this test wrapper on the simulator
# main thread. Production polling never requests an activated handover.
if os.environ.get('P8_TEST_ACTION_SIGNAL'):
    original_cycle = Simulator.cycle
    active_test_sim = None
    def invoke_action(self):
        signal = Path(os.environ['P8_TEST_ACTION_SIGNAL']).resolve()
        if not signal.is_relative_to(ROOT/'.cache'):
            raise ValueError('Test action signal must stay in isolated runtime')
        if signal.exists() and not getattr(self, '_test_action_invoked', False):
            identity = signal.read_text(encoding='utf-8').strip()
            tasks = self.http.get('/v1/device/recovery-tasks'); tasks.raise_for_status()
            task = next((x for x in tasks.json()['items'] if x['operation_id']==identity and x.get('task_kind')=='ACTION'), None)
            if task:
                from simulators.device.service import perform, flush as service_flush
                perform(self, task, technician_token=os.environ['SERVICE_TECHNICIAN_TOKEN'])
                self._test_action_invoked = True
                self.flush()
                service_flush(self)
    def action_cycle(self):
        global active_test_sim
        active_test_sim = self
        if os.environ.get('P8_TEST_HOLD_POST_RECEIPT')=='1' and not getattr(self,'_test_hold_installed',False):
            import httpx
            original_post=self.http.post
            def delayed_post(url, **kwargs):
                if url=='/v1/device/recovery-observations' and kwargs.get('json',{}).get('stage')=='POST_ACTION_RECEIPT':
                    return httpx.Response(503,json={'code':'TEST_RECEIPT_DELIVERY_LOSS'})
                return original_post(url,**kwargs)
            self.http.post=delayed_post
            self._test_hold_installed=True
        result = original_cycle(self)
        invoke_action(self)
        return result
    Simulator.cycle = action_cycle
    # An operator need not wait for the next telemetry cycle to make an explicit
    # call. Keep the real telemetry interval and clock; poll only the test signal
    # during that idle time, on the same SQLite-owning simulator thread.
    import importlib
    device_main = importlib.import_module('simulators.device.main')
    real_time = device_main.time
    class OperatorClock:
        monotonic = staticmethod(real_time.monotonic)
        @staticmethod
        def sleep(seconds):
            deadline = real_time.monotonic()+seconds
            while real_time.monotonic()<deadline:
                if seconds>=1 and active_test_sim is not None:
                    invoke_action(active_test_sim)
                real_time.sleep(min(.1,max(0,deadline-real_time.monotonic())))
    device_main.time = OperatorClock
if os.environ.get('P8_TEST_CRASH_SERVICE') == '1':
    from simulators.device import service
    perform = service.perform
    def crash(sim, task, **kwargs):
        try:
            return perform(sim, task, crash_after_prepared=True, **kwargs)
        except RuntimeError as exc:
            if str(exc) != 'SIMULATED_SERVICE_CRASH_AFTER_PREPARED':
                raise
            # Simulate actual process loss, not the production loop's transient
            # RuntimeError handler. UNKNOWN was committed before this point.
            os._exit(86)
    service.perform = crash
if __name__ == '__main__':
    if os.environ.get('P8_TEST_HOLD_CLOSURE'):
        import httpx
        original_post=httpx.Client.post
        def hold_closure(self,url,**kwargs):
            if url=='/v1/device/recovery-observations' and kwargs.get('json',{}).get('message_kind')=='NO_EFFECT_CLOSURE':
                return httpx.Response(503,json={'code':'TEST_RECEIPT_DELIVERY_LOSS'})
            return original_post(self,url,**kwargs)
        httpx.Client.post=hold_closure
    main()
