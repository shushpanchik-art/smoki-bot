#!/bin/bash
set -euo pipefail
target="$(cd "$(dirname "$0")" && pwd)/../scripts/heartbeat_healthcheck.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export PATH="$tmp:$PATH"
export NOTIFY="$tmp/notify" CASE_DIR="$tmp" ENV_FILE="$tmp/sample.env"
export INV=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
cat > "$tmp/systemctl" <<'MOCK'
#!/bin/bash
[[ "${MODE:-}" != systemctl-error ]] || exit 1
state=active
inv="$INV"
case "$MODE" in
inactive) state=inactive; inv=00000000000000000000000000000000 ;;
bad-id) inv= ;;
restart) if [[ -f "$CASE_DIR/snapshot" ]]; then inv=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb; fi; touch "$CASE_DIR/snapshot" ;;
esac
printf 'LoadState=loaded\nActiveState=%s\nInvocationID=%s\n' "$state" "$inv"
MOCK
cat > "$tmp/journalctl" <<'MOCK'
#!/bin/bash
printf '%s\n' "$@" > "$CASE_DIR/query"
case "$MODE" in
error) echo 'HEARTBEAT ok'; exit 1 ;;
many) printf 'HEARTBEAT ok\n'; awk 'BEGIN { for(i=0;i<100000;i++) print "long log line after marker" }' ;;
old)
    if [[ " $* " != *" _SYSTEMD_INVOCATION_ID=$INV "* ]]; then echo 'HEARTBEAT ok'; fi ;;
matched|restart|notify-error) echo 'HEARTBEAT ok' ;;
esac
exit 0
MOCK
cat > "$tmp/notify" <<'MOCK'
#!/bin/bash
printf '%s' "$1" > "$CASE_DIR/receipt"
[[ "$MODE" != notify-error ]]
MOCK
printf '#!/bin/bash\nexit 0\n' > "$tmp/logger"
chmod +x "$tmp/"{systemctl,journalctl,notify,logger}
one() {
    export MODE="$1"
    rm -f "$tmp/"{receipt,query,snapshot}
    rc=0
    bash "$target" >"$tmp/out" || rc=$?
    got=""
    [[ ! -e "$tmp/receipt" ]] || got="$(cat "$tmp/receipt")"
    [[ "$rc" = "$2" && "$got" = "$3" ]] || { echo "FAIL $MODE status=$rc event=$got"; cat "$tmp/out"; exit 1; }
    printf 'PASS %s\n' "$MODE"
}
# Missing configuration must fall back; old invocation cannot recover the checker.
one matched 0 heartbeat-recovered
grep -Fx '8 hours ago' "$tmp/query"
grep -Fx "_SYSTEMD_INVOCATION_ID=$INV" "$tmp/query"
printf 'HEARTBEAT_MAX_AGE_HOURS="6"\n' > "$ENV_FILE"
one many 0 heartbeat-recovered
grep -Fx '6 hours ago' "$tmp/query"
one old 0 heartbeat-failed
one error 2 ''
one systemctl-error 2 ''
one bad-id 2 ''
one restart 2 ''
one inactive 0 heartbeat-failed
[[ ! -e "$tmp/query" ]]
one notify-error 1 heartbeat-recovered
