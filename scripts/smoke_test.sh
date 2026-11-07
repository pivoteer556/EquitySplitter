#!/usr/bin/env bash
# Post-deploy smoke test: succeeds only if GET <base-url><path> answers HTTP 200.
#
# Usage:  bash scripts/smoke_test.sh <base-url>
#   e.g.  bash scripts/smoke_test.sh https://equitysplitter-api.example.azurecontainerapps.io
#
# Environment:
#   SMOKE_TIMEOUT_SECONDS  total retry budget in seconds (default 120). The app scales to
#                          zero and a cold start has taken >30 s, so the first attempts may fail.
#   SMOKE_PATH             path to probe (default /health); mainly useful to prove the
#                          script fails on a non-200 answer.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <base-url>" >&2
  exit 2
fi

base_url="${1%/}"
path="${SMOKE_PATH:-/health}"
budget="${SMOKE_TIMEOUT_SECONDS:-120}"
url="${base_url}${path}"

attempt=0
code="000"
SECONDS=0
while true; do
  attempt=$((attempt + 1))
  # curl exits non-zero on connect/timeout failures; keep going and report 000.
  code="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 15 "$url" || true)"
  code="${code:-000}"
  if [ "$code" = "200" ]; then
    echo "OK: GET ${url} returned 200 (attempt ${attempt}, ${SECONDS}s)"
    exit 0
  fi
  echo "attempt ${attempt}: GET ${url} returned ${code} (${SECONDS}s of ${budget}s)"
  if [ "$SECONDS" -ge "$budget" ]; then
    break
  fi
  sleep 5
done

echo "FAIL: GET ${url} did not return 200 within ${budget}s (last HTTP code: ${code})" >&2
exit 1
