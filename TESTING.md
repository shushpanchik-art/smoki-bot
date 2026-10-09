
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
| docs/SPEC.md и любые несколько модулей | полный прогон: ~/bin/smoki-check.sh |

Запуск одного файла тестов:
    ~/.smoki-check-venv/bin/python -m pytest tests/ИМЯ.py -q

Полный прогон (перед push):
    ~/bin/smoki-check.sh
