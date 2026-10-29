"""Test-only process controls, never imported by production."""
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'services/backend')]
role=sys.argv.pop(1)
if role=='worker':
    from sqlalchemy import select
    from app.application import swaps
    from app.workers.device import main
    original=swaps.tick
    def boundary(db):
        with db.sessions() as session:
            t=db.table('swap_transactions')
            found=session.scalar(select(t.c.id).where(t.c.state=='RETURN_ACCEPTED'))
        if found:
            Path(os.environ['P7_BOUNDARY']).write_text(str(found),encoding='utf-8')
            # This is after the return transaction has committed, before next step.
            while True: time.sleep(.1)
        return original(db)
    swaps.tick=boundary
    main()
else:
    from simulators.device.main import Simulator,main
    original=Simulator.handle
    def handle(self,command):
        previous=self.scenario
        if command['kind']=='OPEN_SUPPLY':self.scenario='ack-only'
        try:return original(self,command)
        finally:self.scenario=previous
    Simulator.handle=handle
    main()
