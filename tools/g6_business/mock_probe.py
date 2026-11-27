"""No network/database/business imports; explicit process-identity control only."""
import json
import os

if __name__ == '__main__':
    print(json.dumps(dict(pid=os.getpid(), parent_pid=os.getppid(), kind='mock-only')))
