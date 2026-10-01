#!/usr/bin/env bash
# Headless regression: scripts compile, a full 8-kart race finishes with sane lap times,
# and the character's animation states drive the skeleton.
set -euo pipefail
cd "$(dirname "$0")/../.."
GODOT=${GODOT:-godot}
$GODOT --headless --path . --import > /dev/null 2>&1 || true
LOG=$(mktemp)
$GODOT --headless --path . res://tools/tests/sim.tscn -- --t=240 --every=60 < /dev/null > "$LOG" 2>&1 || true
if grep -q "SCRIPT ERROR" "$LOG"; then grep -A2 "SCRIPT ERROR" "$LOG" | head -20; echo "FAIL: script errors"; exit 1; fi
finished=$(grep -A9 "FINISH ORDER" "$LOG" | grep -c ":[0-9][0-9]\." || true)
grep -A10 "FINISH ORDER" "$LOG" || true
if [ "$finished" -lt 8 ]; then echo "FAIL: only $finished/8 karts finished"; exit 1; fi
$GODOT --headless --path . res://tools/tests/anim_probe.tscn < /dev/null 2>&1 | grep -E "head=" | tee "$LOG"
python3 - "$LOG" <<'PY'
import re, sys
t = open(sys.argv[1]).read()
race = float(re.search(r"race head=\([^,]+, ([-\d.]+)", t).group(1))
vic = float(re.search(r"victory head=\([^,]+, ([-\d.]+)", t).group(1))
assert vic - race > 0.15, f"victory should stand up (race {race}, victory {vic})"
print("OK: victory stands up", round(vic - race, 3), "m")
PY
echo "ALL TESTS PASSED"
