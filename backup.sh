#!/usr/bin/env bash
# ============================================================================
# backup.sh — ежедневный локальный бэкап SQLite-базы SMOKI-бота.
# Запускается systemd-таймером smoki-backup.timer.
# Логи: /opt/SMOKI/bot/logs/backup.log
# Алерты: notify_admin.sh backup-failed / backup-recovered.
# ============================================================================
set -euo pipefail

BOT_DIR="${BOT_DIR:-/opt/SMOKI/bot}"
DB_PATH="${DB_PATH:-$BOT_DIR/smoki.db}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/smoki}"
RETENTION_DAYS="${RETENTION_DAYS:-150}"
MAX_TOTAL_BYTES="${MAX_TOTAL_BYTES:-5368709120}"
SAFETY_NET_DAYS="${SAFETY_NET_DAYS:-7}"
LOCK_FILE="${LOCK_FILE:-$BACKUP_DIR/.backup.lock}"
NOTIFY_SCRIPT="${NOTIFY_SCRIPT:-$BOT_DIR/scripts/notify_admin.sh}"

HASH_FILE="$BACKUP_DIR/.last_dump.sha256"
DATE="$(date +%Y%m%d_%H%M%S)"
BACKUP_PREFIX="smoki_"
BACKUP_GLOB="${BACKUP_PREFIX}*.db"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"; }

notify_failure() {
    local rc=$?
    set +e
    log "ERROR: backup завершился с кодом $rc, отправляю алерт"
    if [ -x "$NOTIFY_SCRIPT" ]; then
        "$NOTIFY_SCRIPT" backup-failed || log "WARN: notify_admin.sh backup-failed сам упал (rc=$?)"
    else
        log "WARN: $NOTIFY_SCRIPT не исполняем или отсутствует — алерт не отправлен"
    fi
    exit "$rc"
}
trap notify_failure ERR

die() { log "ERROR: $*"; exit 1; }
file_mtime() { [ -f "$1" ] && stat -c %Y "$1" || echo 0; }
total_size() {
    find "$1" -maxdepth 1 -name "$2" -type f -printf '%s\n' 2>/dev/null \
        | awk '{s+=$1} END {print s+0}'
}

[ -f "$DB_PATH" ] || die "БД не найдена: $DB_PATH"
command -v sqlite3 >/dev/null || die "sqlite3 не установлен"
command -v sha256sum >/dev/null || die "sha256sum не установлен"

mkdir -p "$BACKUP_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "WARN: предыдущий запуск ещё работает (lock=$LOCK_FILE), выхожу"
    exit 0
fi

TMP_SNAPSHOT="$BACKUP_DIR/.tmp_snapshot_$$.db"
cleanup() { rm -f "$TMP_SNAPSHOT" "$TMP_SNAPSHOT-journal" "$TMP_SNAPSHOT-wal" "$TMP_SNAPSHOT-shm"; }
trap cleanup EXIT

sqlite3 "$DB_PATH" ".backup '$TMP_SNAPSHOT'" || die "sqlite3 .backup упал"
[ -s "$TMP_SNAPSHOT" ] || die "временный снимок пустой"

NEW_HASH="$(sqlite3 "$TMP_SNAPSHOT" .dump | sha256sum | awk '{print $1}')"
[ -n "$NEW_HASH" ] || die "не удалось посчитать хеш дампа"

SHOULD_BACKUP=1
SKIP_REASON=""
LAST_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | awk '{print $2}')"

if [ -n "$LAST_BACKUP" ] && [ -f "$HASH_FILE" ]; then
    OLD_HASH="$(cat "$HASH_FILE" 2>/dev/null || true)"
    if [ "$NEW_HASH" = "$OLD_HASH" ]; then
        LAST_MTIME="$(file_mtime "$LAST_BACKUP")"
        NOW="$(date +%s)"
        AGE_DAYS=$(( (NOW - LAST_MTIME) / 86400 ))
        if [ "$AGE_DAYS" -lt "$SAFETY_NET_DAYS" ]; then
            SHOULD_BACKUP=0
            SKIP_REASON="no data changes (last backup ${AGE_DAYS}d ago, safety-net=${SAFETY_NET_DAYS}d)"
        else
            log "INFO: данные не менялись ${AGE_DAYS} дней — делаем safety-net бэкап"
        fi
    fi
fi

if [ "$SHOULD_BACKUP" -eq 0 ]; then
    log "skipped: $SKIP_REASON"
else
    FINAL_PATH="$BACKUP_DIR/${BACKUP_PREFIX}${DATE}.db"
    mv "$TMP_SNAPSHOT" "$FINAL_PATH"
    echo "$NEW_HASH" > "$HASH_FILE"
    sync "$FINAL_PATH" "$HASH_FILE" "$BACKUP_DIR" || log "WARN: sync failed (rc=$?), backup may not be durable"
    SIZE="$(stat -c %s "$FINAL_PATH")"
    log "backup ok: ${BACKUP_PREFIX}${DATE}.db (${SIZE} bytes, sha256=${NEW_HASH:0:12}, fsynced)"
fi

DELETED_AGE=0
while IFS= read -r -d '' old; do
    rm -f "$old"; DELETED_AGE=$((DELETED_AGE + 1))
done < <(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f -mtime "+$RETENTION_DAYS" -print0)
[ "$DELETED_AGE" -gt 0 ] && log "retention: удалено по возрасту (>${RETENTION_DAYS} дн.): $DELETED_AGE шт."

DELETED_SIZE=0
CURRENT_SIZE="$(total_size "$BACKUP_DIR" "$BACKUP_GLOB")"
if [ "$CURRENT_SIZE" -gt "$MAX_TOTAL_BYTES" ]; then
    while [ "$CURRENT_SIZE" -gt "$MAX_TOTAL_BYTES" ]; do
        OLDEST="$(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | head -1 | awk '{print $2}')"
        [ -z "$OLDEST" ] && break
        REMAINING="$(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f | wc -l)"
        if [ "$REMAINING" -le 1 ]; then
            log "WARN: оставшийся бэкап ($OLDEST) больше лимита, но не удаляю — это последний"; break
        fi
        rm -f "$OLDEST"; DELETED_SIZE=$((DELETED_SIZE + 1))
        CURRENT_SIZE="$(total_size "$BACKUP_DIR" "$BACKUP_GLOB")"
    done
    log "retention: удалено по лимиту размера (>${MAX_TOTAL_BYTES} B): $DELETED_SIZE шт., итого: ${CURRENT_SIZE} B"
fi

if [ "$DELETED_AGE" -gt 0 ] || [ "$DELETED_SIZE" -gt 0 ]; then
    sync "$BACKUP_DIR" || log "WARN: sync after retention failed (rc=$?)"
fi

TOTAL_FILES="$(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f | wc -l)"
TOTAL_BYTES="$(total_size "$BACKUP_DIR" "$BACKUP_GLOB")"
log "stats: files=$TOTAL_FILES, total_size=${TOTAL_BYTES}B"

trap - ERR
if [ -x "$NOTIFY_SCRIPT" ]; then
    "$NOTIFY_SCRIPT" backup-recovered || log "WARN: notify_admin.sh backup-recovered упал (rc=$?), но бэкап успешен"
fi
exit 0
