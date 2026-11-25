#!/bin/bash
# External watchdog for the current SMOKI scheduler invocation.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/SMOKI/bot/.env}"
NOTIFY="${NOTIFY:-/opt/SMOKI/bot/scripts/notify_admin.sh}"
UNIT="${UNIT:-smoki-bot}"
LOG_TAG="smoki_heartbeat_check"

log() { logger -t "$LOG_TAG" -- "$*" 2>/dev/null || true; echo "[$LOG_TAG] $*"; }
unknown() { log "UNKNOWN: $*"; exit 2; }

# A missing key or file is a supported default, not a fatal pipeline failure.
MAX_AGE_H="$(sed -n '/^HEARTBEAT_MAX_AGE_HOURS=/{s/^[^=]*=//;s/["'\''[:space:]]//g;p;q;}' "$ENV_FILE" 2>/dev/null || true)"
case "$MAX_AGE_H" in ''|*[!0-9]*) MAX_AGE_H=8 ;; esac
SINCE="${MAX_AGE_H} hours ago"

snapshot() {
    systemctl show --property=LoadState,ActiveState,InvocationID -- "$UNIT"
}

before="$(snapshot 2>/dev/null)" || unknown "systemctl could not read $UNIT"
load_state=""
active_state=""
invocation=""
while IFS='=' read -r key value; do
    case "$key" in
        LoadState) load_state="$value" ;;
        ActiveState) active_state="$value" ;;
        InvocationID) invocation="$value" ;;
    esac
done <<< "$before"
[[ "$load_state" == "loaded" ]] || unknown "unit is not loaded: $UNIT"

if [[ "$active_state" == "active" ]]; then
    [[ "$invocation" =~ ^[[:xdigit:]]{32}$ && "$invocation" != 00000000000000000000000000000000 ]] ||
        unknown "no valid invocation ID for active unit $UNIT"

    # awk consumes the entire stream: no grep -q/SIGPIPE false failure.
    # pipefail sees a failed journal read even if partial output includes a marker.
    fresh="$(journalctl --unit "$UNIT" --since "$SINCE" --no-pager --output=cat \
        "_SYSTEMD_INVOCATION_ID=$invocation" 2>/dev/null |
        awk 'index($0, "HEARTBEAT ok") { found=1 } END { print found+0 }')" ||
        unknown "journal could not be read for $UNIT"
elif [[ "$active_state" == "failed" || "$active_state" == "inactive" ]]; then
    fresh=0
else
    unknown "unit is transitioning or its state is unavailable: ${active_state:-unknown}"
fi

after="$(snapshot 2>/dev/null)" || unknown "systemctl could not recheck $UNIT"
[[ "$before" == "$after" ]] || unknown "unit changed during check: $UNIT"

if [[ "$fresh" == "1" ]]; then
    log "OK: fresh heartbeat for the current invocation (window ${MAX_AGE_H}h)"
    "$NOTIFY" heartbeat-recovered
else
    log "FAIL: no heartbeat for active invocation (window ${MAX_AGE_H}h); unit state: $active_state"
    "$NOTIFY" heartbeat-failed
fi
