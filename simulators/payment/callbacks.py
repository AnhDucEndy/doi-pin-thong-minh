"""Optional private callback delivery; retry identity is durable across restarts."""
import argparse
from contextlib import closing
import os
import time
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx
from app.api.payments import secret
from app.config import ROOT, ConfigNotReady
from simulators.payment.main import Ledger


def deliver(ledger, url, client=None):
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.password:
        raise ConfigNotReady('CONFIG_NOT_READY')
    if parsed.path!='/v1/payment-events' or parsed.query or parsed.fragment:
        raise ConfigNotReady('CONFIG_NOT_READY')
    owned=client is None
    client=client or httpx.Client(timeout=5,trust_env=False,follow_redirects=False)
    count=0
    try:
        with closing(ledger.connect()) as connection:
            rows=connection.execute('SELECT * FROM charges').fetchall()
        for row in rows:
            result=ledger.query(row['provider_key'])
            if result['result'] not in ('SUCCEEDED','FAILED'):
                continue
            event_id=str(uuid5(NAMESPACE_URL,'mock-payment:'+row['provider_key']+':'+result['result']))
            with closing(ledger.connect()) as connection:
                if connection.execute('SELECT 1 FROM callback_deliveries WHERE event_id=?',(event_id,)).fetchone():
                    continue
            payload={'provider_event_id':event_id,'payment_id':row['payment_id'],**result}
            try:
                response=client.post(url,headers={'X-Payment-Key':secret('PAYMENT_CALLBACK_KEY')},json=payload)
                response.raise_for_status()
                if response.status_code!=202 or response.json().get('accepted') is not True:
                    continue
            except (httpx.HTTPError,ValueError):
                continue  # Next run resends the exact event; no new charge and no new event ID.
            with closing(ledger.connect()) as connection:
                connection.execute('INSERT OR IGNORE INTO callback_deliveries VALUES (?,?)',(event_id,time.time()))
            count+=1
    finally:
        if owned:client.close()
    return count


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    ledger=Ledger(os.getenv('PAYMENT_LEDGER_PATH',ROOT/'.local/payment/ledger.sqlite3'))
    url=os.getenv('PAYMENT_CALLBACK_URL','http://127.0.0.1:8000/v1/payment-events')
    while True:
        deliver(ledger,url)
        if args.once:break
        time.sleep(1)


if __name__=='__main__':main()
