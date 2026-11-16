"""Admin CLI (runs inside the container, no HTTP):
  python cli.py ingest | wipe | hashpw"""
import getpass
import sys

import auth
import rag

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "ingest":
    print(rag.ingest())
elif cmd == "wipe":
    rag.wipe()
    print("wiped", rag.COLLECTION)
elif cmd == "hashpw":
    print(auth.hash_pw(getpass.getpass("password: ")))
else:
    sys.exit(__doc__)
