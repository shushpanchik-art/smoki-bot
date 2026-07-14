# SMOKI — systemd-юниты бэкапов

Копии установленных в системе юнитов (`/etc/systemd/system/`).
Хранятся в репо для версионирования и воспроизводимого развёртывания.

## Состав

- `smoki-backup.service/.timer` — локальный бэкап SQLite в 03:30, скрипт `backup.sh`
- `smoki-backup-offsite.service/.timer` — отправка БД на Я.Диск, `scripts/backup_offsite.sh`
- `smoki-backup-offsite-alert.service` — алерт при падении offsite (OnFailure)
- `smoki-backup-full-offsite.service/.timer` — полный offsite-бэкап, `scripts/backup_full_offsite.sh`
- `smoki-backup-full-offsite-alert.service` — алерт при падении full offsite (OnFailure)
- `smoki-heartbeat.service/.timer` — ежечасная проверка живости планировщика, `scripts/heartbeat_healthcheck.sh`
- `smoki-backup-summary.service/.timer` — ежедневная сводка по бэкапам в 23:45, `scripts/backup_summary.sh`
- `smoki-backup-restore-test.service/.timer` — еженедельный restore-test (Пн 04:17): восстановление бэкапа + `PRAGMA integrity_check` + проверка таблиц, `scripts/backup_restore_test.sh`

Алерты шлёт `scripts/notify_admin.sh` в Telegram.

## Установка

    sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now smoki-backup.timer smoki-backup-offsite.timer smoki-backup-full-offsite.timer smoki-heartbeat.timer smoki-backup-summary.timer smoki-backup-restore-test.timer

## Проверка

    systemctl list-timers 'smoki-backup*'
    systemctl status smoki-backup-offsite
    journalctl -u smoki-backup-offsite -n 50

## Ручной прогон

    sudo systemctl start smoki-backup-offsite.service
    tail -f /opt/SMOKI/bot/logs/backup-offsite.log
