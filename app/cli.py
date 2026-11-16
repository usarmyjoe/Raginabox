"""Admin CLI (runs inside the container): python cli.py ingest | wipe"""
import sys

import rag

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "ingest":
    print(rag.ingest())
elif cmd == "wipe":
    rag.wipe()
    print("wiped", rag.COLLECTION)
else:
    sys.exit(__doc__)
