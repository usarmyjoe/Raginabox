#!/bin/sh
# Live checks against the running stack. Run after `docker compose up -d`.
rc=0
docker compose --profile verify run --rm probe || rc=1

code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/whoami)
[ "$code" = "401" ] && echo "PASS api rejects unauthenticated ($code)" || { echo "FAIL api unauthenticated returned $code"; rc=1; }

# the backend services must not be reachable from the host
for port in 6333 11434; do
  if (exec 3<>/dev/tcp/127.0.0.1/$port) 2>/dev/null; then echo "FAIL host can reach :$port"; rc=1
  else echo "PASS :$port not exposed on host"; fi
done
exit $rc
