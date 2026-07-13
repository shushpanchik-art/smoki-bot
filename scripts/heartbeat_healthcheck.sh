#!/bin/bash
# heartbeat_healthcheck.sh — внешняя проверка живости SMOKI-планировщика.
#
# Логика: джоба _job_heartbeat пишет "HEARTBEAT ok" в journald каждые
# HEARTBEAT_INTERVAL_HOURS часов. Этот скрипт грепает journald за окно
# HEARTBEAT_MAX_AGE_HOURS. Нет свежего маркера → бот завис → алерт.
# Есть свежий → снимаем алерт (recovered).
#
# Запускается systemd-таймером smoki-heartbeat.timer.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/SMOKI/bot/.env}"
NOTIFY="${NOTIFY:-/opt/SMOKI/bot/scripts/notify_admin.sh}"
UNIT="${UNIT:-smoki-bot}"
LOG_TAG="smoki_heartbeat_check"

log() { logger -t "$LOG_TAG" -- "$*" 2>/dev/null || true; echo "[$LOG_TAG] $*"; }

# max-age из .env (fallback 8ч)
MAX_AGE_H="$(grep -E '^HEARTBEAT_MAX_AGE_HOURS=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'\' | tr -d ' ')"
case "$MAX_AGE_H" in ''|*[!0-9]*) MAX_AGE_H=8 ;; esac

SINCE="${MAX_AGE_H} hours ago"

if journalctl -u "$UNIT" --since "$SINCE" 2>/dev/null | grep -q "HEARTBEAT ok"; then
    log "OK: свежий HEARTBEAT найден за окно ${MAX_AGE_H}ч"
    "$NOTIFY" heartbeat-recovered || true
else
    log "FAIL: нет HEARTBEAT за ${MAX_AGE_H}ч — планировщик мог зависнуть"
    "$NOTIFY" heartbeat-failed || true
fi
exit 0
