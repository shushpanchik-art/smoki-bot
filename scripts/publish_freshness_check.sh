#!/bin/bash
# publish_freshness_check.sh — внешний сторож по факту публикации.
# Пингует HC_PING_URL (healthchecks.io) ТОЛЬКО если последняя публикация
# свежее PUBLISH_MAX_AGE_HOURS. Молчание = healthchecks сам шлёт алерт.
set -uo pipefail

ENV_FILE="${ENV_FILE:-/opt/SMOKI/bot/.env}"
DB="${DB:-/opt/SMOKI/bot/smoki.db}"
LOG_TAG="smoki_publish_check"
log() { logger -t "$LOG_TAG" -- "$*" 2>/dev/null || true; echo "[$LOG_TAG] $*"; }

HC_PING_URL="${HC_PING_URL:-}"
if [ -z "$HC_PING_URL" ] && [ -r "$ENV_FILE" ]; then
    HC_PING_URL="$(grep -E '^HC_PING_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi
MAX_AGE_H="${PUBLISH_MAX_AGE_HOURS:-26}"
if [ -r "$ENV_FILE" ]; then
    v="$(grep -E '^PUBLISH_MAX_AGE_HOURS=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d ' ')"
    [ -n "$v" ] && MAX_AGE_H="$v"
fi
case "$MAX_AGE_H" in ''|*[!0-9]*) MAX_AGE_H=26 ;; esac

if [ -z "$HC_PING_URL" ]; then
    log "SKIP: HC_PING_URL не задан в .env, пинг не отправлен"
    exit 0
fi

AGE_H="$(python3 - "$DB" <<'PY'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
row = c.execute("""SELECT (julianday('now','localtime') - julianday(MAX(published_at))) * 24
                   FROM articles WHERE status = 'published'""").fetchone()
print("NONE" if row is None or row[0] is None else f"{row[0]:.2f}")
PY
)" || { log "ERROR: не удалось прочитать БД $DB"; exit 0; }

if [ "$AGE_H" = "NONE" ]; then
    log "FAIL: нет ни одной опубликованной статьи, пинг не отправлен"
    exit 0
fi

if awk -v a="$AGE_H" -v m="$MAX_AGE_H" 'BEGIN{exit !(a+0 <= m+0)}'; then
    if curl -fsS -m 10 --retry 2 -o /dev/null "$HC_PING_URL"; then
        log "OK: последняя публикация ${AGE_H}ч назад (порог ${MAX_AGE_H}ч), пинг отправлен"
    else
        log "ERROR: пинг healthchecks не дошёл (публикация свежая: ${AGE_H}ч)"
    fi
else
    log "FAIL: последняя публикация ${AGE_H}ч назад (порог ${MAX_AGE_H}ч), пинг НЕ отправлен"
fi
exit 0
