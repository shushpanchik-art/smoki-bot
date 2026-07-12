#!/usr/bin/env bash
# ============================================================================
# backup_offsite.sh — отправка свежего локального бэкапа БД SMOKI на Я.Диск.
# Берёт последний smoki_*.db из /var/backups/smoki, gzip-ит, грузит 2 копии:
#   - история: smoki_YYYYMMDD_HHMMSS.db.gz (retention по дате)
#   - latest:  smoki-latest.db.gz (для быстрого recovery)
# Запускается smoki-backup-offsite.timer. Лог: logs/backup-offsite.log.
# ============================================================================
set -euo pipefail

BOT_DIR="${BOT_DIR:-/opt/SMOKI/bot}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/smoki}"
STAGING_DIR="${STAGING_DIR:-/var/backups/smoki-offsite/staging}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/var/lib/smoki-rclone/rclone.conf}"
RCLONE_REMOTE="${RCLONE_REMOTE:-yandex_native:smoki-backup}"
OFFSITE_RETENTION_DAYS="${OFFSITE_RETENTION_DAYS:-30}"
NOTIFY_SCRIPT="${NOTIFY_SCRIPT:-$BOT_DIR/scripts/notify_admin.sh}"
LOCK_FILE="${LOCK_FILE:-$STAGING_DIR/.offsite.lock}"

BACKUP_GLOB='smoki_*.db'
LATEST_NAME="smoki-latest.db.gz"

RCLONE_FLAGS=(
    --config "$RCLONE_CONFIG"
    --timeout 2h
    --contimeout 30s
    --low-level-retries 20
    --retries 3
    --stats 0
)

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"; }

die() { log "ERROR: $*"; notify_failure_explicit 1; exit 1; }

_NOTIFY_SENT=0
notify_failure_explicit() {
    [ "$_NOTIFY_SENT" = "1" ] && return 0
    _NOTIFY_SENT=1
    local rc="${1:-1}"; set +e
    log "ERROR: offsite-backup завершился с кодом $rc, отправляю алерт"
    if [ -x "$NOTIFY_SCRIPT" ]; then
        "$NOTIFY_SCRIPT" offsite-failed || log "WARN: notify_admin.sh offsite-failed сам упал (rc=$?)"
    else
        log "WARN: $NOTIFY_SCRIPT не исполняем или отсутствует"
    fi
}

notify_failure() { local rc=$?; notify_failure_explicit "$rc"; exit "$rc"; }
trap notify_failure ERR

command -v rclone >/dev/null || die "rclone не установлен"
command -v gzip   >/dev/null || die "gzip не установлен"
command -v sha256sum >/dev/null || die "sha256sum не установлен"
[ -r "$RCLONE_CONFIG" ] || die "не могу прочитать $RCLONE_CONFIG"
[ -d "$BACKUP_DIR" ]    || die "BACKUP_DIR не существует: $BACKUP_DIR"

mkdir -p "$STAGING_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "WARN: предыдущий запуск offsite ещё работает (lock=$LOCK_FILE), выхожу"; exit 0
fi

LATEST_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | awk '{print $2}')"
[ -n "$LATEST_BACKUP" ] || die "в $BACKUP_DIR нет файлов $BACKUP_GLOB"
[ -s "$LATEST_BACKUP" ] || die "последний бэкап пустой: $LATEST_BACKUP"

BACKUP_NAME="$(basename "$LATEST_BACKUP")"
GZ_NAME="${BACKUP_NAME}.gz"
STAGED_GZ="$STAGING_DIR/$GZ_NAME"
log "source: $LATEST_BACKUP ($(stat -c %s "$LATEST_BACKUP") bytes)"

cleanup_staging() { rm -f "$STAGED_GZ" "$STAGED_GZ.tmp"; }
trap cleanup_staging EXIT

gzip -c -9 "$LATEST_BACKUP" > "$STAGED_GZ.tmp" || die "gzip упал"
mv "$STAGED_GZ.tmp" "$STAGED_GZ"

GZ_SIZE="$(stat -c %s "$STAGED_GZ")"
GZ_SHA="$(sha256sum "$STAGED_GZ" | awk '{print $1}')"
log "staged: $GZ_NAME ($GZ_SIZE bytes, sha256=${GZ_SHA:0:12})"

rclone "${RCLONE_FLAGS[@]}" copyto "$STAGED_GZ" "$RCLONE_REMOTE/$GZ_NAME" || die "rclone copyto (history) упал"
log "uploaded history: $RCLONE_REMOTE/$GZ_NAME"

rclone "${RCLONE_FLAGS[@]}" copyto "$STAGED_GZ" "$RCLONE_REMOTE/$LATEST_NAME" || die "rclone copyto (latest) упал"
log "uploaded latest:  $RCLONE_REMOTE/$LATEST_NAME"

REMOTE_HASH="$(rclone "${RCLONE_FLAGS[@]}" hashsum sha256 "$RCLONE_REMOTE/$GZ_NAME" 2>/dev/null | awk '{print $1}' || true)"
if [ -n "$REMOTE_HASH" ] && [ "$REMOTE_HASH" != "UNSUPPORTED" ]; then
    if [ "$REMOTE_HASH" = "$GZ_SHA" ]; then
        log "integrity: remote sha256 совпадает с локальным"
    else
        die "integrity FAIL: local=$GZ_SHA remote=$REMOTE_HASH"
    fi
else
    log "integrity: remote hash не предоставлен — сверка пропущена (OK для Я.Диска)"
fi

DELETE_OUTPUT="$(rclone "${RCLONE_FLAGS[@]}" delete --include 'smoki_*.db.gz' --min-age "${OFFSITE_RETENTION_DAYS}d" "$RCLONE_REMOTE" 2>&1 || true)"
log "retention output: ${DELETE_OUTPUT:-(ничего не удалено)}"

REMOTE_FILES="$(rclone "${RCLONE_FLAGS[@]}" lsf --include 'smoki_*.db.gz' "$RCLONE_REMOTE" 2>/dev/null | wc -l || echo 0)"
log "stats: remote history files = $REMOTE_FILES (retention=${OFFSITE_RETENTION_DAYS}d)"

trap - ERR
if [ -x "$NOTIFY_SCRIPT" ]; then
    "$NOTIFY_SCRIPT" offsite-recovered || log "WARN: notify_admin.sh offsite-recovered упал (rc=$?)"
    # Ежедневное подтверждение успеха (анти-дубликат в notify_admin.sh: не чаще 1 раза в 20ч)
    "$NOTIFY_SCRIPT" backup-ok || log "WARN: notify_admin.sh backup-ok упал (rc=$?)"
fi
log "OK: offsite backup complete"
exit 0
