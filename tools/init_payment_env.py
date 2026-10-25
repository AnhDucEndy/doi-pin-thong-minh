"""Append missing private mock configuration only; never replace an existing secret."""
from pathlib import Path
import secrets


def main():
    path=Path(__file__).resolve().parents[1]/'.env'
    if not path.exists():
        raise ValueError('Prepare the existing project .env first; this tool never replaces it')
    text=path.read_text(encoding='utf-8-sig')
    existing={line.split('=',1)[0].strip() for line in text.splitlines() if '=' in line and not line.lstrip().startswith('#')}
    values={'PAYMENT_SERVICE_KEY':secrets.token_urlsafe(48),'PAYMENT_CALLBACK_KEY':secrets.token_urlsafe(48),
            'PAYMENT_MOCK_URL':'http://127.0.0.1:8001','PAYMENT_LEDGER_PATH':'.local/payment/ledger.sqlite3',
            'PAYMENT_MOCK_SCENARIO':'success'}
    missing=[k+'='+v for k,v in values.items() if k not in existing]
    if missing:
        with path.open('a',encoding='utf-8',newline='\n') as stream:
            stream.write('\n# Phase6 private payment simulation\n'+'\n'.join(missing)+'\n')
    print(f'Payment configuration ready: {len(missing)} missing fields appended; existing values preserved; secrets omitted')


if __name__=='__main__':main()
