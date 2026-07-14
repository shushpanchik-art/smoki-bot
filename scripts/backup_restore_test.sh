#!/usr/bin/env bash
# ============================================================================
# backup_restore_test.sh (R4) — еженедельная проверка восстановимости бэкапа.
# Берёт последний smoki_*.db из BACKUP_DIR, разворачивает в temp-копию,
# гоняет PRAGMA integrity_check + проверяет что ключевые таблицы на месте.
# Запускается smoki-backup-restore-test.timer.
# Логи: /opt/SMOKI/bot/logs/backup-restore-test.log
# Алерты: notify_admin.sh restore-test-failed / restore-test-recovered.
# ============================================================================
set -euo pipefail

BOT_DIR="${BOT_DIR:-/opt/SMOKI/bot}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/smoki}"
NOTIFY_SCRIPT="${NOTIFY_SCRIPT:-$BOT_DIR/scripts/notify_admin.sh}"
BACKUP_GLOB="smoki_*.db"
EXPECTED_TABLES="published_topics articles comments ai_logs settings"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"; }

notify_failure() {
    local rc=$?
    set +e
    log "ERROR: restore-test завершился с кодом $rc, отправляю алерт"
    if [ -x "$NOTIFY_SCRIPT" ]; then
        "$NOTIFY_SCRIPT" restore-test-failed \
            || log "WARN: notify_admin.sh restore-test-failed сам упал (rc=$?)"
    else
        log "WARN: $NOTIFY_SCRIPT не исполняем — алерт не отправлен"
    fi
    exit "$rc"
}
trap notify_failure ERR

die() { log "ERROR: $*"; exit 1; }

command -v sqlite3 >/dev/null || die "sqlite3 не установлен"
[ -d "$BACKUP_DIR" ] || die "каталог бэкапов не найден: $BACKUP_DIR"

LATEST="$(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f \
    -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | awk '{print $2}')"
[ -n "$LATEST" ] || die "нет ни одного бэкапа ($BACKUP_GLOB) в $BACKUP_DIR"

log "проверяю восстановление из: $LATEST"

TMP_RESTORE="$(mktemp --suffix=.db)"
cleanup() { rm -f "$TMP_RESTORE" "$TMP_RESTORE-journal" "$TMP_RESTORE-wal" "$TMP_RESTORE-shm"; }
trap 'cleanup' EXIT

# Разворачиваем через .restore — эмулируем реальное восстановление, а не cp.
sqlite3 "$TMP_RESTORE" ".restore '$LATEST'" || die ".restore упал для $LATEST"
[ -s "$TMP_RESTORE" ] || die "восстановленная копия пустая"

INTEGRITY="$(sqlite3 "$TMP_RESTORE" 'PRAGMA integrity_check;' 2>&1 | head -1)"
[ "$INTEGRITY" = "ok" ] || die "integrity_check восстановленной БД провален: $INTEGRITY"

FOUND_TABLES="$(sqlite3 "$TMP_RESTORE" \
    "SELECT name FROM sqlite_master WHERE type='table';" 2>&1)"
MISSING=""
for t in $EXPECTED_TABLES; do
    echo "$FOUND_TABLES" | grep -qx "$t" || MISSING="$MISSING $t"
done
[ -z "$MISSING" ] || die "в восстановленной БД нет таблиц:$MISSING"

ROW_ARTICLES="$(sqlite3 "$TMP_RESTORE" 'SELECT COUNT(*) FROM articles;' 2>&1)"
log "restore-test ok: integrity=ok, все таблицы на месте, articles=$ROW_ARTICLES"

trap - ERR
if [ -x "$NOTIFY_SCRIPT" ]; then
    "$NOTIFY_SCRIPT" restore-test-recovered \
        || log "WARN: notify_admin.sh restore-test-recovered упал (rc=$?), но тест успешен"
fi
exit 0
