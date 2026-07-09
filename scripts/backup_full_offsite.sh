#!/usr/bin/env bash
# ============================================================================
# backup_full_offsite.sh — полный tar.gz ВСЕГО /opt/SMOKI/ на Я.Диск (native API).
# Дополняет backup_offsite.sh (только БД): сюда попадает АБСОЛЮТНО ВСЁ без
# исключений — .env, requirements, handlers, ai, services, media/, images/,
# venv/, .git/, кэши и прочее. Полный снимок для disaster recovery.
#   - история: smoki-full_YYYYMMDD_HHMMSS.tar.gz (retention по дате)
#   - latest:  smoki-full-latest.tar.gz (server-side copy, без перезаливки)
# Запускается smoki-backup-full-offsite.timer. Лог: logs/backup-full-offsite.log.
# ============================================================================
set -euo pipefail

BOT_DIR="${BOT_DIR:-/opt/SMOKI/bot}"
SOURCE_DIR="${SOURCE_DIR:-/opt/SMOKI}"
STAGING_DIR="${STAGING_DIR:-/var/backups/smoki-full-offsite/staging}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/var/lib/smoki-rclone/rclone.conf}"
RCLONE_REMOTE="${RCLONE_REMOTE:-yandex_native:smoki-backup-full}"
FULL_RETENTION_DAYS="${FULL_RETENTION_DAYS:-30}"
NOTIFY_SCRIPT="${NOTIFY_SCRIPT:-$BOT_DIR/scripts/notify_admin.sh}"
LOCK_FILE="${LOCK_FILE:-$STAGING_DIR/.full-offsite.lock}"
TAR_EXTRA_FLAGS="${TAR_EXTRA_FLAGS:-}"

LATEST_NAME="smoki-full-latest.tar.gz"
ARCHIVE_GLOB='smoki-full_*.tar.gz'

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
    log "ERROR: full-offsite-backup завершился с кодом $rc, отправляю алерт"
    if [ -x "$NOTIFY_SCRIPT" ]; then
        "$NOTIFY_SCRIPT" offsite-full-failed || log "WARN: notify_admin.sh offsite-full-failed сам упал (rc=$?)"
    else
        log "WARN: $NOTIFY_SCRIPT не исполняем или отсутствует"
    fi
}

notify_failure() { local rc=$?; notify_failure_explicit "$rc"; exit "$rc"; }
trap notify_failure ERR

command -v rclone >/dev/null || die "rclone не установлен"
command -v tar    >/dev/null || die "tar не установлен"
command -v gzip   >/dev/null || die "gzip не установлен"
command -v sha256sum >/dev/null || die "sha256sum не установлен"
[ -r "$RCLONE_CONFIG" ] || die "не могу прочитать $RCLONE_CONFIG"
[ -d "$SOURCE_DIR" ]    || die "SOURCE_DIR не существует: $SOURCE_DIR"

mkdir -p "$STAGING_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "WARN: предыдущий запуск full-offsite ещё работает (lock=$LOCK_FILE), выхожу"; exit 0
fi

TS="$(date -u '+%Y%m%d_%H%M%S')"
ARCHIVE_NAME="smoki-full_${TS}.tar.gz"
STAGED_TGZ="$STAGING_DIR/$ARCHIVE_NAME"
log "source: $SOURCE_DIR (полный, без исключений)"
log "target: $RCLONE_REMOTE/$ARCHIVE_NAME (+ $LATEST_NAME via server-side copy)"

cleanup_staging() { rm -f "$STAGED_TGZ" "$STAGED_TGZ.tmp"; }
trap cleanup_staging EXIT

SRC_PARENT="$(dirname "$SOURCE_DIR")"
SRC_NAME="$(basename "$SOURCE_DIR")"

# Архивируем АБСОЛЮТНО ВСЁ содержимое /opt/SMOKI/ без --exclude.
# --exclude только для собственного staging-каталога бэкапа, чтобы архив
# не пытался рекурсивно включить сам себя (он в /var/backups, вне SOURCE_DIR,
# так что фактически исключать нечего — оставлено для явности при ENV-override).
set +e
# shellcheck disable=SC2086
tar \
    --warning=no-file-changed \
    --warning=no-file-removed \
    ${TAR_EXTRA_FLAGS:-} \
    -C "$SRC_PARENT" \
    -cf - "$SRC_NAME" 2>"$STAGED_TGZ.tar.stderr" \
    | gzip -1 > "$STAGED_TGZ.tmp"
PIPE_RCS=( "${PIPESTATUS[@]}" )
set -e
TAR_RC="${PIPE_RCS[0]:-0}"
GZIP_RC="${PIPE_RCS[1]:-0}"

if [ "$TAR_RC" -gt 1 ]; then
    log "ERROR tar stderr: $(cat "$STAGED_TGZ.tar.stderr" 2>/dev/null | tr '\n' ' ')"
    die "tar упал (rc=$TAR_RC)"
fi
if [ "$GZIP_RC" -ne 0 ]; then
    die "gzip упал (rc=$GZIP_RC)"
fi
rm -f "$STAGED_TGZ.tar.stderr"
mv "$STAGED_TGZ.tmp" "$STAGED_TGZ"

TGZ_SIZE="$(stat -c %s "$STAGED_TGZ")"
TGZ_SHA="$(sha256sum "$STAGED_TGZ" | awk '{print $1}')"
log "staged: $ARCHIVE_NAME ($TGZ_SIZE bytes, sha256=${TGZ_SHA:0:12}, tar_rc=$TAR_RC)"

if [ "$TGZ_SIZE" -lt 1024 ]; then
    die "архив слишком мал: $TGZ_SIZE байт — возможно, $SOURCE_DIR пуст"
fi

log "загружаю историю через native Yandex API..."
UPLOAD_START="$(date +%s)"
rclone "${RCLONE_FLAGS[@]}" copyto "$STAGED_TGZ" "$RCLONE_REMOTE/$ARCHIVE_NAME" || die "rclone copyto (history) упал"
UPLOAD_END="$(date +%s)"
log "uploaded history: $RCLONE_REMOTE/$ARCHIVE_NAME (took $((UPLOAD_END - UPLOAD_START))s)"

log "server-side copy: $ARCHIVE_NAME -> $LATEST_NAME (без передачи по сети)"
SS_START="$(date +%s)"
rclone "${RCLONE_FLAGS[@]}" copyto "$RCLONE_REMOTE/$ARCHIVE_NAME" "$RCLONE_REMOTE/$LATEST_NAME" || die "rclone copyto (latest, server-side) упал"
SS_END="$(date +%s)"
log "uploaded latest:  $RCLONE_REMOTE/$LATEST_NAME (server-side, took $((SS_END - SS_START))s)"

REMOTE_HASH="$(rclone "${RCLONE_FLAGS[@]}" hashsum sha256 "$RCLONE_REMOTE/$ARCHIVE_NAME" 2>/dev/null | awk '{print $1}' || true)"
if [ -n "$REMOTE_HASH" ] && [ "$REMOTE_HASH" != "UNSUPPORTED" ]; then
    if [ "$REMOTE_HASH" = "$TGZ_SHA" ]; then
        log "integrity: remote sha256 совпадает с локальным"
    else
        die "integrity FAIL: local=$TGZ_SHA remote=$REMOTE_HASH"
    fi
else
    log "integrity: remote hash не предоставлен — сверка пропущена (OK для Я.Диска)"
fi

DELETE_OUTPUT="$(rclone "${RCLONE_FLAGS[@]}" delete --include "$ARCHIVE_GLOB" --min-age "${FULL_RETENTION_DAYS}d" "$RCLONE_REMOTE" 2>&1 || true)"
log "retention output: ${DELETE_OUTPUT:-(ничего не удалено)}"

REMOTE_FILES="$(rclone "${RCLONE_FLAGS[@]}" lsf --include "$ARCHIVE_GLOB" "$RCLONE_REMOTE" 2>/dev/null | wc -l || echo 0)"
log "stats: remote history files = $REMOTE_FILES (retention=${FULL_RETENTION_DAYS}d)"

trap - ERR
if [ -x "$NOTIFY_SCRIPT" ]; then
    "$NOTIFY_SCRIPT" offsite-full-recovered || log "WARN: notify_admin.sh offsite-full-recovered упал (rc=$?)"
fi
log "OK: full-offsite backup complete ($TGZ_SIZE bytes)"
exit 0
