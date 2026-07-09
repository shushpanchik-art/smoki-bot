#!/bin/bash
# notify_admin.sh — отправка алертов админу SMOKI-бота через Telegram.
#
# Использование:
#   notify_admin.sh backup-failed          # бэкап БД упал
#   notify_admin.sh backup-recovered       # бэкап БД восстановлен
#   notify_admin.sh backup-ok              # ежедневная сводка OK
#   notify_admin.sh offsite-failed         # offsite-бэкап БД упал
#   notify_admin.sh offsite-recovered      # offsite-бэкап БД восстановлен
#   notify_admin.sh offsite-full-failed    # full-offsite упал
#   notify_admin.sh offsite-full-recovered # full-offsite восстановлен
#
# Анти-дубликат через state-файлы в /var/lib/smoki-backup.
set -euo pipefail

EVENT="${1:-}"
ENV_FILE="${ENV_FILE:-/opt/SMOKI/bot/.env}"
LOG_TAG="smoki_notify_admin"
BACKUP_OWNER="${BACKUP_OWNER:-shushpanchik_art:shushpanchik_art}"

BACKUP_STATE_DIR="${BACKUP_STATE_DIR:-/var/lib/smoki-backup}"
BACKUP_STATE_FILE="${BACKUP_STATE_DIR}/failed"
OFFSITE_STATE_FILE="${BACKUP_STATE_DIR}/offsite-failed"
OFFSITE_FULL_STATE_FILE="${BACKUP_STATE_DIR}/offsite-full-failed"

log() { logger -t "$LOG_TAG" -- "$*" 2>/dev/null || true; echo "[$LOG_TAG] $*"; }

read_credentials() {
    if [ ! -r "$ENV_FILE" ]; then
        log "ERROR: не могу прочитать $ENV_FILE"; exit 3
    fi
    BOT_TOKEN="$(grep -E '^BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
    ADMIN_ID="$(grep -E '^ADMIN_CHAT_ID=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
    if [ -z "$BOT_TOKEN" ] || [ -z "$ADMIN_ID" ]; then
        log "ERROR: BOT_TOKEN или ADMIN_CHAT_ID пустые в .env"; exit 4
    fi
}

send_telegram() {
    local text="$1"
    local resp_file="/tmp/smoki_notify_resp.$$"
    local http_code
    http_code="$(curl -s -o "$resp_file" -w '%{http_code}' \
        -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${ADMIN_ID}" \
        -d parse_mode=Markdown \
        --data-urlencode "text=${text}" || echo "000")"
    if [ "$http_code" = "200" ]; then
        log "OK: алерт '$EVENT' отправлен (HTTP 200)"; rm -f "$resp_file"; return 0
    else
        local body; body="$(cat "$resp_file" 2>/dev/null || echo '')"
        log "ERROR: алерт '$EVENT' не отправлен (HTTP $http_code): $body"; rm -f "$resp_file"; return 5
    fi
}

ensure_backup_state_dir() {
    if [ ! -d "$BACKUP_STATE_DIR" ]; then
        mkdir -p "$BACKUP_STATE_DIR"
        chown "$BACKUP_OWNER" "$BACKUP_STATE_DIR" 2>/dev/null || true
        chmod 0775 "$BACKUP_STATE_DIR"
    fi
}

case "$EVENT" in
    backup-failed)
        ensure_backup_state_dir
        if [ -e "$BACKUP_STATE_FILE" ]; then
            log "INFO: backup state-файл уже есть — пропускаю"; exit 0
        fi
        read_credentials
        touch "$BACKUP_STATE_FILE"; chown "$BACKUP_OWNER" "$BACKUP_STATE_FILE" 2>/dev/null || true
        TEXT="🚨 *SMOKI backup FAILED*
Бэкап БД упал. Лог: \`/opt/SMOKI/bot/logs/backup.log\`
Проверь: \`systemctl status smoki-backup\`"
        send_telegram "$TEXT" || exit $?
        ;;
    backup-recovered)
        if [ ! -e "$BACKUP_STATE_FILE" ]; then
            log "INFO: backup state-файл отсутствует — RECOVERED не нужен"; exit 0
        fi
        read_credentials
        TEXT="✅ *SMOKI backup восстановлен*
Очередной бэкап прошёл успешно."
        if send_telegram "$TEXT"; then rm -f "$BACKUP_STATE_FILE"; log "OK: backup state-файл удалён"; else exit $?; fi
        ;;
    offsite-failed)
        ensure_backup_state_dir
        if [ -e "$OFFSITE_STATE_FILE" ]; then
            log "INFO: offsite state-файл уже есть — пропускаю"; exit 0
        fi
        read_credentials
        touch "$OFFSITE_STATE_FILE"; chown "$BACKUP_OWNER" "$OFFSITE_STATE_FILE" 2>/dev/null || true
        TEXT="🚨 *SMOKI offsite backup FAILED*
Отправка БД на Я.Диск упала.
Лог: \`/opt/SMOKI/bot/logs/backup-offsite.log\`
Проверь: \`systemctl status smoki-backup-offsite\`"
        send_telegram "$TEXT" || exit $?
        ;;
    offsite-recovered)
        if [ ! -e "$OFFSITE_STATE_FILE" ]; then
            log "INFO: offsite state-файл отсутствует — RECOVERED не нужен"; exit 0
        fi
        read_credentials
        TEXT="✅ *SMOKI offsite backup восстановлен*
Очередная отправка на Я.Диск прошла успешно."
        if send_telegram "$TEXT"; then rm -f "$OFFSITE_STATE_FILE"; log "OK: offsite state-файл удалён"; else exit $?; fi
        ;;
    offsite-full-failed)
        ensure_backup_state_dir
        if [ -e "$OFFSITE_FULL_STATE_FILE" ]; then
            log "INFO: offsite-full state-файл уже есть — пропускаю"; exit 0
        fi
        read_credentials
        touch "$OFFSITE_FULL_STATE_FILE"; chown "$BACKUP_OWNER" "$OFFSITE_FULL_STATE_FILE" 2>/dev/null || true
        TEXT="🚨 *SMOKI full-offsite backup FAILED*
Полный архив /opt/SMOKI/ не загружен на Я.Диск.
Лог: \`/opt/SMOKI/bot/logs/backup-full-offsite.log\`
Проверь: \`systemctl status smoki-backup-full-offsite\`"
        send_telegram "$TEXT" || exit $?
        ;;
    offsite-full-recovered)
        if [ ! -e "$OFFSITE_FULL_STATE_FILE" ]; then
            log "INFO: offsite-full state-файл отсутствует — RECOVERED не нужен"; exit 0
        fi
        read_credentials
        TEXT="✅ *SMOKI full-offsite backup восстановлен*
Очередная отправка полного архива на Я.Диск прошла успешно."
        if send_telegram "$TEXT"; then rm -f "$OFFSITE_FULL_STATE_FILE"; log "OK: offsite-full state-файл удалён"; else exit $?; fi
        ;;
    backup-ok)
        ensure_backup_state_dir
        OK_STATE_FILE="${BACKUP_STATE_DIR}/last-ok-notify"
        MIN_INTERVAL_SEC=72000
        now="$(date +%s)"
        if [ -f "$OK_STATE_FILE" ]; then
            last="$(cat "$OK_STATE_FILE" 2>/dev/null || echo 0)"
            case "$last" in ''|*[!0-9]*) last=0 ;; esac
            if [ $(( now - last )) -lt "$MIN_INTERVAL_SEC" ]; then
                log "INFO: backup-ok уже отправляли менее 20ч назад — пропускаю"; exit 0
            fi
        fi
        read_credentials
        DATE_STR="$(date '+%d.%m.%Y')"
        TEXT="✅ *SMOKI backup OK*
Бэкап БД свежий и на месте. Проверка от ${DATE_STR}."
        if send_telegram "$TEXT"; then
            echo "$now" > "$OK_STATE_FILE"; chown "$BACKUP_OWNER" "$OK_STATE_FILE" 2>/dev/null || true
            log "OK: backup-ok отправлен"
        else exit $?; fi
        ;;
    *)
        log "ERROR: неизвестное событие: '$EVENT'. Допустимо: backup-failed, backup-recovered, backup-ok, offsite-failed, offsite-recovered, offsite-full-failed, offsite-full-recovered"
        exit 2
        ;;
esac
exit 0
