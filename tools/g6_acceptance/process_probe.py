"""Deliberate early-exit telemetry probe, only when explicitly executed."""
import os
def main():
    assert os.environ.get("G6_GUARD_READY")=="1"
    return 7
if __name__=="__main__":raise SystemExit(main())
