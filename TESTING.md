
## Какие тесты запускать после правки файла

| Изменён файл | Тесты |
| --- | --- |
| db/database.py, db/schema.sql | test_db, test_schema, test_integrity, test_sql_valid |
| config.py, .env.example | test_config, test_env_example, test_secrets |
| ai/gemini.py | test_gemini |
| ai/prompts.py | test_prompts, test_image_scene, test_story_prompts |
| saga (prompts/service) | test_saga_prompt, test_saga_service |
| services/content.py | test_content, test_admin_custom_length, test_u4_custom_length |
| services/publisher.py | test_publisher, test_delivery_watchdog |
| services/comments.py | test_comments |
| services/stories.py, story_render.py | test_stories, test_story_*, test_image_crop |
| scheduler.py | test_scheduler, test_deadline, test_generation_alert, test_heartbeat |
| services/schedule_*.py | test_schedule_*, test_minus_minutes |
| handlers/admin.py | test_admin, test_admin_custom_length, test_stats |
| handlers/*.py | test_routers, test_import |
| userbot.py | test_userbot |
| scripts/backup_full_offsite.sh | test_backup_full_offsite |
| docs/SPEC.md и любые несколько модулей | полный прогон: ~/bin/smoki-check.sh |

Запуск одного файла тестов:
    ~/.smoki-check-venv/bin/python -m pytest tests/ИМЯ.py -q

Регрессии полного бэкапа (Linux, без зависимостей бота и сетевых вызовов):
    python -m unittest tests.test_backup_full_offsite -v

Тесты запускают настоящий скрипт с временными файлами и локальными заглушками
`rclone` и уведомлений. Они проверяют коды tar/gzip, обе копии, ошибки загрузки,
контрольную сумму и очистку staging; production и секреты не используются.

Полный прогон (перед push):
    ~/bin/smoki-check.sh
