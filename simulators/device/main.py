"""HTTP simulator, two demo controllers, durable SQLite outbox/command/physical ledger."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from app.config import ROOT,approved_policy
from app.seed import demo_id


def now():return datetime.now(timezone.utc).isoformat()


class Simulator:
    def __init__(self,code,key,base_url='http://127.0.0.1:8000',ledger=None,scenario='normal',transport=None):
        if code not in ('S01','S02'):raise ValueError('Only the two approved demo stations are supported')
        if urlsplit(base_url).hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Simulation is loopback-only')
        if not key or len(key)<24:raise ValueError('Device key is required through environment')
        path=Path(ledger) if ledger else ROOT/'.local/device'/f'{code}.sqlite3'
        path=path.resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Keep simulator ledger inside workspace')
        path.parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(path);self.conn.row_factory=sqlite3.Row
        self.conn.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS slots(id TEXT PRIMARY KEY,body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,hash TEXT NOT NULL,status TEXT NOT NULL,effects INTEGER NOT NULL,body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,body TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,receipt TEXT);')
        self.code,self.scenario=code,scenario;self.boot=str(uuid4());self.seq=0;self.policy=approved_policy()
        self.http=httpx.Client(base_url=base_url,headers={'X-Device-Key':key},timeout=10,transport=transport,trust_env=False)
        for slot in range(1,7):
            body={'compartment_id':str(demo_id(f'{code}:slot:{slot}')),'door_state':'CLOSED','present':slot>1,
                'observed_serial':f'{code}-B{slot:03}' if slot>1 else None,
                'battery_id':str(demo_id(f'{code}:battery:{slot}')) if slot>1 else None,'lock_released':False}
            self.conn.execute('INSERT OR IGNORE INTO slots VALUES (?,?)',(body['compartment_id'],json.dumps(body)))
        self.conn.commit()

    def close(self):self.http.close();self.conn.close()
    def slots(self):return [json.loads(r['body']) for r in self.conn.execute('SELECT body FROM slots ORDER BY id')]
    def save_slot(self,slot):
        self.conn.execute('UPDATE slots SET body=? WHERE id=?',(json.dumps(slot),slot['compartment_id']));self.conn.commit()
    def emit(self,kind,payload,**references):
        body={'event_id':str(uuid4()),'boot_id':self.boot,'seq':self.seq,'kind':kind,'observed_at':now(),'payload':payload,**references}
        self.seq+=1
        self.conn.execute('INSERT INTO events(id,body) VALUES (?,?)',(body['event_id'],json.dumps(body)));self.conn.commit()
        return body
    def snapshot(self):
        slots=[{k:v for k,v in s.items() if k in ('compartment_id','door_state','present','observed_serial')} for s in self.slots()]
        ledger=[{'command_id':r['id'],'status':r['status']} for r in self.conn.execute('SELECT id,status FROM commands')]
        return self.emit('SNAPSHOT',{'slots':slots,'command_ledger':ledger})
    def flush(self):
        receipts=[]
        for row in self.conn.execute('SELECT * FROM events WHERE sent=0 ORDER BY rowid').fetchall():
            response=self.http.post('/v1/device/events',json=json.loads(row['body']))
            if response.status_code!=202:
                # Retain the failed event; never print headers, keys or full requests.
                raise RuntimeError(f'Device event refused: HTTP {response.status_code}, {response.json().get("code","ERROR")}')
            self.conn.execute('UPDATE events SET sent=1,receipt=? WHERE id=?',(json.dumps(response.json()),row['id']));self.conn.commit()
            receipts.append(response.json())
        return receipts
    def acknowledge(self,command,result,reason):
        self.emit('COMMAND_ACK',{'result':result,'reason':reason},compartment_id=command['compartment_id'],
            swap_id=command['swap_id'],command_id=command['id'])
    def settle(self,receipts,min_seq=0):
        """Wait for durable processing receipts before polling control; 202 alone is not readiness."""
        pending={r['event_id'] for r in receipts};deadline=time.monotonic()+10
        while pending:
            for identity in list(pending):
                raw=self.conn.execute('SELECT body FROM events WHERE id=?',(identity,)).fetchone()
                response=self.http.post('/v1/device/events',json=json.loads(raw['body']))
                if response.status_code!=202:raise RuntimeError(f'Receipt refused: HTTP {response.status_code}')
                result=response.json()
                self.conn.execute('UPDATE events SET receipt=? WHERE id=?',(json.dumps(result),identity));self.conn.commit()
                if result['processing_state']=='REJECTED':
                    event=json.loads(raw['body'])
                    if event['boot_id']!=self.boot or event['seq']<min_seq:
                        pending.remove(identity);continue  # Historical inbox evidence retained, never replayed as fresh.
                    raise RuntimeError('DEVICE_EVENT_REJECTED_BY_WORKER')
                if result['processing_state']=='PROCESSED':pending.remove(identity)
            if pending:
                if time.monotonic()>deadline:raise RuntimeError('WORKER_PROCESSING_TIMEOUT: start the inbox worker')
                time.sleep(.1)
    def handle(self,command):
        body={k:command[k] for k in ('id','device_id','swap_id','compartment_id','kind','expires_at','payload')}
        hashed=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        existing=self.conn.execute('SELECT * FROM commands WHERE id=?',(command['id'],)).fetchone()
        if existing:
            cached=json.loads(existing['body']).get('ack',{'result':'ACCEPTED' if existing['status']=='EXECUTED' else 'REJECTED','reason':'DURABLE_REPLAY_NO_EFFECT'})
            if existing['hash']!=hashed or existing['status']=='UNKNOWN':cached={'result':'UNKNOWN','reason':'DURABLE_RESULT_UNKNOWN'}
            self.acknowledge(command,cached['result'],cached['reason']);return cached['result']
        # Persist UNKNOWN before any actuator effect. A restart cannot execute this ID again.
        self.conn.execute('INSERT INTO commands VALUES (?,?,?,?,?)',(command['id'],hashed,'UNKNOWN',0,json.dumps(body)));self.conn.commit()
        if self.scenario=='crash-after-ledger':raise RuntimeError('SIMULATED_CRASH_AFTER_DURABLE_LEDGER')
        slot=next((s for s in self.slots() if s['compartment_id']==command['compartment_id']),None)
        valid=(command['device_id']==str(demo_id('device:'+self.code)) and command['kind'] in ('OPEN_RETURN','OPEN_SUPPLY')
            and datetime.fromisoformat(command['expires_at'].replace('Z','+00:00'))>datetime.now(timezone.utc)
            and slot and slot['door_state']=='CLOSED' and command['payload'].get('simulation_only') is True
            and command['payload'].get('expected_serial'))
        if valid:
            valid=slot['present'] is False if command['kind']=='OPEN_RETURN' else slot['present'] is True and slot['observed_serial']==command['payload']['expected_serial']
        if not valid or self.scenario=='nack':
            body['ack']={'result':'REJECTED','reason':'INTERLOCK_OR_DEMO_NACK'}
            self.conn.execute('UPDATE commands SET status=?,body=? WHERE id=?',('NOT_EXECUTED',json.dumps(body),command['id']));self.conn.commit()
            self.acknowledge(command,'REJECTED','INTERLOCK_OR_DEMO_NACK');return 'REJECTED'
        self.acknowledge(command,'ACCEPTED','RECEIVED_NOT_PHYSICAL_PROOF')
        if self.scenario in ('normal','ack-only'):
            body['ack']={'result':'ACCEPTED','reason':'RECEIVED_NOT_PHYSICAL_PROOF'}
            self.conn.execute('UPDATE commands SET status=?,body=? WHERE id=?',('NOT_EXECUTED',json.dumps(body),command['id']));self.conn.commit();return 'ACK_ONLY'
        slot['lock_released']=True;slot['door_state']='OPEN';self.save_slot(slot)
        refs={'compartment_id':slot['compartment_id'],'swap_id':command['swap_id'],'command_id':command['id']}
        observation=lambda:{k:slot[k] for k in ('door_state','present','observed_serial')}
        self.emit('DOOR',observation(),**refs)
        slot['present']=command['kind']=='OPEN_RETURN'
        slot['observed_serial']=command['payload']['expected_serial'] if slot['present'] else None
        slot['battery_id']=command['payload'].get('expected_battery_id') if slot['present'] else None
        self.save_slot(slot);self.emit('PRESENCE',observation(),**refs)
        slot['door_state']='CLOSED';slot['lock_released']=False;self.save_slot(slot);self.emit('DOOR',observation(),**refs)
        body['ack']={'result':'ACCEPTED','reason':'RECEIVED_NOT_PHYSICAL_PROOF'}
        self.conn.execute('UPDATE commands SET status=?,body=?,effects=effects+1 WHERE id=?',('EXECUTED',json.dumps(body),command['id']));self.conn.commit()
        return 'EXECUTED'
    def cycle(self):
        if self.scenario=='offline':return []
        bootstrap=self.snapshot();self.emit('HEARTBEAT',{'health':'OK'})
        for slot in self.slots():
            if not slot['battery_id']:continue
            payload={'battery_id':slot['battery_id'],'soc':90,'soh':95,'temperature_c':25,'fault_codes':[]}
            if self.scenario=='low-soc':payload['soc']=self.policy['soc_min_pct']-1
            if self.scenario=='low-soh':payload['soh']=self.policy['soh_min_pct']-1
            if self.scenario=='hot':payload['temperature_c']=self.policy['temperature_max_c']+1
            if self.scenario=='missing-bms':payload['soh']=None
            if self.scenario=='fault':payload['fault_codes']=['SIMULATED_BMS_FAULT']
            self.emit('TELEMETRY',payload,compartment_id=slot['compartment_id'])
        receipts=self.flush()
        self.settle(receipts,bootstrap['seq'])
        response=self.http.get('/v1/device/commands',params={'limit':100})
        if response.status_code!=200:raise RuntimeError(f'Command poll refused: HTTP {response.status_code}')
        for command in response.json()['items']:self.handle(command)
        effects=self.flush();self.settle(effects,bootstrap['seq']);receipts.extend(effects);return receipts


def main():
    parser=argparse.ArgumentParser(description='Simulation only; durable state stays in workspace')
    parser.add_argument('--station',choices=['S01','S02','both'],default='both')
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--ledger-dir',default=str(ROOT/'.local/device'))
    parser.add_argument('--scenario',choices=['normal','low-soc','low-soh','hot','missing-bms','fault','ack-only','nack','physical','crash-after-ledger','offline'],default='normal')
    parser.add_argument('--cycles',type=int,default=0,help='0 means run until Ctrl+C')
    parser.add_argument('--inspect',action='store_true',help='Read local physical/command ledger without sending events')
    args=parser.parse_args();codes=['S01','S02'] if args.station=='both' else [args.station]
    if args.inspect:
        for code in codes:
            path=(Path(args.ledger_dir)/(code+'.sqlite3')).resolve()
            if not path.is_relative_to(ROOT):raise ValueError('Keep ledger inside workspace')
            if not path.exists():print(f'{code}: no ledger');continue
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as connection:
                print(json.dumps({'station':code,'simulation_only':True,'slots':[json.loads(r[0]) for r in connection.execute('SELECT body FROM slots')],
                    'commands':[{'id':r[0],'status':r[1],'effects':r[2]} for r in connection.execute('SELECT id,status,effects FROM commands')]},indent=2))
        return
    sims=[Simulator(code,os.getenv('DEMO_DEVICE_KEY_'+code),args.url,Path(args.ledger_dir)/(code+'.sqlite3'),args.scenario) for code in codes]
    try:
        index=0
        while True:
            for sim in sims:
                try:
                    receipts=sim.cycle();print(f'{sim.code}: cycle {index+1}, inbox receipts={len(receipts)}, simulation_only=True',flush=True)
                except (httpx.HTTPError,RuntimeError) as error:
                    if args.cycles:raise
                    print(f'{sim.code}: {type(error).__name__}; durable outbox retained; retry next cycle',flush=True)
            index+=1
            if args.cycles and index>=args.cycles:break
            time.sleep(approved_policy()['telemetry_interval_seconds'])
    finally:
        for sim in sims:sim.close()


if __name__=='__main__':main()
