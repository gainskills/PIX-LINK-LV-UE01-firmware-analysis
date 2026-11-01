#!/bin/sh
# Resume the native, fully linked history in this repository. Private IDs stay ignored.
set -eu
repeater_root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
repeater_thread=$(python3 - "$repeater_root/.private/session-history/continuation.json" <<'PY'
import json,re,sys
from pathlib import Path
p=Path(sys.argv[1]);j=json.loads(p.read_text());tid=j['continuation_thread_id']
if not re.fullmatch(r'[0-9a-f-]{36}',tid):raise SystemExit('Invalid saved continuation ID')
print(tid)
PY
)
exec "${CODEX_BIN:-codex}" resume "$repeater_thread" --cd "$repeater_root" "$@"
