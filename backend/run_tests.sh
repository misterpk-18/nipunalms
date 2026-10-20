#!/usr/bin/env bash
# Run the backend tests and keep a record of the run.
#   ./run_tests.sh                      whole suite
#   ./run_tests.sh tests/test_content.py -k release   any pytest arguments
# Starting a run deletes the previous runs' log files, then writes backend/test-logs/<date>_<time>[_label].log (follow it with
# `tail -f`) and points test-logs/latest.log at it. test-logs/index.log is never cleared: one line per run (when, what ran,
# result, how long), so the history stays trackable. The folder is git-ignored.
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p test-logs
find test-logs -maxdepth 1 \( -name '*.log' -o -type l \) ! -name index.log -delete
stamp=$(date +%Y-%m-%d_%H%M%S)
label=""
[ $# -gt 0 ] && label="_$(echo "$*" | tr -c 'A-Za-z0-9' '_' | cut -c1-40)"
log="test-logs/${stamp}${label}.log"
ln -sf "$(basename "$log")" test-logs/latest.log
echo "Logging to $(pwd)/$log"
start=$(date +%s)
PYTHONUNBUFFERED=1 ../venv/bin/python -m pytest "${@:-tests}" -v -rfE 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
summary=$(grep -E "^=+ .*(passed|failed|error|no tests).* in " "$log" | tail -1 | tr -d '=' | sed 's/^ *//')
printf '%s | exit %s | %s | %ss | pytest %s | %s\n' "$stamp" "$status" "${summary:-no summary}" "$(( $(date +%s) - start ))" "${*:-tests}" "$log" >> test-logs/index.log
exit "$status"
