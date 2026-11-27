import os
if os.environ.get('G6_ISOLATION_PORT'):
    try:
        import isolation
        os.environ['G6_GUARD_READY']='1'
    except BaseException:
        os._exit(78)
