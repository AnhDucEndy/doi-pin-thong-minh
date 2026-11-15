"""Verification-only real process exit after durable PREPARED, before effect."""
import os
from tools import phase8a_manual_operator as operator
from simulators.device import recovery_handover

if not os.environ['DATABASE_SCHEMA'].startswith('phase5_test_'):
    raise RuntimeError('Isolated fixture required')
original=recovery_handover.perform

def interrupted(sim,task,**kwargs):
    try:
        return original(sim,task,**kwargs,crash_after_prepared=True)
    except RuntimeError as error:
        if str(error)!='SIMULATED_SERVICE_CRASH_AFTER_PREPARED':
            raise
        os._exit(86)

recovery_handover.perform=interrupted
operator.main()
