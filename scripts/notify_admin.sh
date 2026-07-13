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
#   notify_admin.sh heartbeat-failed        # планировщик завис
#   notify_admin.sh heartbeat-recovered     # планировщик ожил
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
HEARTBEAT_STATE_FILE="${BACKUP_STATE_DIR}/heartbeat-failed"

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
    heartbeat-failed)
        ensure_backup_state_dir
        if [ -e "$HEARTBEAT_STATE_FILE" ]; then
            log "INFO: heartbeat state-файл уже есть — пропускаю"; exit 0
        fi
        read_credentials
        touch "$HEARTBEAT_STATE_FILE"; chown "$BACKUP_OWNER" "$HEARTBEAT_STATE_FILE" 2>/dev/null || true
        TEXT="🚨 *SMOKI heartbeat FAILED*
Планировщик не подавал признаков жизни дольше нормы.
Возможно, бот завис или упал.
Проверь: \`systemctl status smoki-bot\`
Логи: \`journalctl -u smoki-bot -n 50\`"
        send_telegram "$TEXT" || exit $?
        ;;
    heartbeat-recovered)
        if [ ! -e "$HEARTBEAT_STATE_FILE" ]; then
            log "INFO: heartbeat state-файл отсутствует — RECOVERED не нужен"; exit 0
        fi
        read_credentials
        TEXT="✅ *SMOKI heartbeat восстановлен*
Планировщик снова подаёт признаки жизни."
        if send_telegram "$TEXT"; then rm -f "$HEARTBEAT_STATE_FILE"; log "OK: heartbeat state-файл удалён"; else exit $?; fi
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
    daily-summary)
        read_credentials
        TODAY="$(date '+%Y-%m-%d')"
        TODAY_HUMAN="$(date '+%d.%m.%Y')"
        LOCAL_DB_DIR="${LOCAL_DB_DIR:-/var/backups/smoki}"
        OFFSITE_LOG="${OFFSITE_LOG:-/opt/SMOKI/bot/logs/backup-offsite.log}"
        FULL_LOG="${FULL_LOG:-/opt/SMOKI/bot/logs/backup-full-offsite.log}"

        human_size() {
            local b="$1"
            if [ -z "$b" ] || [ "$b" -lt 1024 ] 2>/dev/null; then echo "${b:-0} Б"; return; fi
            awk -v b="$b" 'BEGIN{
                split("Б КБ МБ ГБ ТБ",u," ");
                i=1; while(b>=1024 && i<5){b/=1024; i++}
                printf "%.1f %s", b, u[i]
            }'
        }

        # 1) Локальный smoki.db — свежайший файл за сегодня
        LOCAL_FILE="$(find "$LOCAL_DB_DIR" -maxdepth 1 -name 'smoki_*.db' -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | awk '{print $2}')"
        if [ -n "$LOCAL_FILE" ] && [ "$(date -r "$LOCAL_FILE" '+%Y-%m-%d')" = "$TODAY" ]; then
            LSIZE="$(human_size "$(stat -c %s "$LOCAL_FILE")")"
            LTIME="$(date -r "$LOCAL_FILE" '+%H:%M %d.%m')"
            LOCAL_LINE="✅ ok, ${LSIZE}, ${LTIME}"
            LOCAL_OK=1
        else
            LOCAL_LINE="❌ сегодня не выполнялся"
            LOCAL_OK=0
        fi

        # 2) Offsite smoki.db — строка OK за сегодня
        OFF_MATCH="$(grep -E "^\[$TODAY .*OK: offsite backup complete" "$OFFSITE_LOG" 2>/dev/null | tail -1)"
        if [ -n "$OFF_MATCH" ]; then
            OTIME="$(echo "$OFF_MATCH" | sed -E 's/^\[[0-9-]+ ([0-9:]+).*/\1/')"
            OFF_LINE="✅ ok, ${OTIME} ${TODAY_HUMAN}"
            OFF_OK=1
        else
            OFF_LINE="❌ сегодня не выполнялся"
            OFF_OK=0
        fi

        # 3) Full offsite — строка OK (N bytes) за сегодня
        FULL_MATCH="$(grep -E "^\[$TODAY .*OK: full-offsite backup complete" "$FULL_LOG" 2>/dev/null | tail -1)"
        if [ -n "$FULL_MATCH" ]; then
            FTIME="$(echo "$FULL_MATCH" | sed -E 's/^\[[0-9-]+ ([0-9:]+).*/\1/')"
            FBYTES="$(echo "$FULL_MATCH" | sed -E 's/.*\(([0-9]+) bytes\).*/\1/')"
            FSIZE="$(human_size "$FBYTES")"
            FULL_LINE="✅ ok, ${FSIZE}, ${FTIME} ${TODAY_HUMAN}"
            FULL_OK=1
        else
            FULL_LINE="❌ сегодня не выполнялся"
            FULL_OK=0
        fi

        if [ "$LOCAL_OK" = 1 ] && [ "$OFF_OK" = 1 ] && [ "$FULL_OK" = 1 ]; then
            HEADER="📦 *Бэкапы за сутки (${TODAY_HUMAN})*"
        else
            HEADER="⚠️ *Бэкапы за сутки (${TODAY_HUMAN}) — есть проблемы*"
        fi
        TEXT="${HEADER}
• Локальный smoki.db (на сервере): ${LOCAL_LINE}
• Offsite smoki.db (Я.Диск): ${OFF_LINE}
• Offsite полный (Я.Диск): ${FULL_LINE}"
        send_telegram "$TEXT" || exit $?
        ;;
    *)
        log "ERROR: неизвестное событие: '$EVENT'. Допустимо: backup-failed, backup-recovered, backup-ok, offsite-failed, offsite-recovered, offsite-full-failed, offsite-full-recovered, heartbeat-failed, heartbeat-recovered, daily-summary"
        exit 2
        ;;
esac
exit 0
