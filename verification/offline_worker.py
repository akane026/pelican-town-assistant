"""Fresh-process entry point enforcing no networking for every offline stage."""
import os
import runpy
import sys
from pathlib import Path
from .common import dump, now


def main():
    module=sys.argv[1];result_path=Path(sys.argv[2]);attempts=[]
    def deny(event,args):
        if event in {'socket.connect','socket.getaddrinfo','socket.sendto'}:
            attempts.append(event);raise RuntimeError('OFFLINE_NETWORK_DENIED')
    sys.addaudithook(deny);sys.argv=[module];code=0
    try:runpy.run_module(module,run_name='__main__')
    except SystemExit as e:code=e.code if isinstance(e.code,int) else 1
    except Exception as e:
        import traceback
        traceback.print_exc();code=3
    dump(result_path,{'module':module,'pid':os.getpid(),'at':now(),'exit_code':code,'network_attempts':attempts})
    return code if not attempts else 1

if __name__=='__main__':raise SystemExit(main())
