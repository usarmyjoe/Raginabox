"""Runs INSIDE the backend network (see `probe` service). Exit 1 if any containment check fails."""
import os
import socket
import sys

import requests

url, key = os.environ["QDRANT_URL"], os.environ["QDRANT_API_KEY"]
failed = False


def check(name, ok):
    global failed
    print(("PASS " if ok else "FAIL ") + name)
    failed |= not ok


# 1. no egress from the backend network
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3).close()
    check("backend network has no egress", False)
except OSError:
    check("backend network has no egress", True)

# 2. Qdrant demands its API key
check("qdrant rejects missing key", requests.get(f"{url}/collections", timeout=5).status_code in (401, 403))
check("qdrant rejects wrong key",
      requests.get(f"{url}/collections", headers={"api-key": "nope"}, timeout=5).status_code in (401, 403))
check("qdrant accepts the real key",
      requests.get(f"{url}/collections", headers={"api-key": key}, timeout=5).status_code == 200)

sys.exit(1 if failed else 0)
