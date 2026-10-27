import sys
from iwh import *
for t in sys.argv[1:]:
    setup(t)
    import importlib, interwhen_sop.sopdata as sd; sd.load.cache_clear()
    print("=====", t)
    show(run("completion", []))
