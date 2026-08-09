#!/usr/bin/env bash
# Start both DeepSeek proxies detached from the calling shell.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

nohup "$ROOT/.venv/bin/python" -m deepseekweb serve >"$ROOT/logs/deepseekweb.log" 2>&1 </dev/null & disown
nohup "$ROOT/.venv/bin/python" -m deepseekchat serve >"$ROOT/logs/deepseekchat.log" 2>&1 </dev/null & disown

echo "deepseekweb  -> http://0.0.0.0:1997  (logs: logs/deepseekweb.log)"
echo "deepseekchat -> http://0.0.0.0:1996  (logs: logs/deepseekchat.log)"