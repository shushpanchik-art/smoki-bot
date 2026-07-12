# SMOKI-bot

## Назначение

Автоведение Telegram-канала @SMOKTOLK (вейпы, кальяны, табак) с AI-генерацией контента, ручной модерацией и автомодерацией комментариев.

## Инфраструктура

- Путь: /opt/SMOKI/bot, venv venv/bin/python
- systemd: smoki-bot (Restart=always), режим polling
- Python 3.11.2, aiogram 3.29.1, aiosqlite, apscheduler, dotenv
- БД smoki.db: published_topics, articles, comments, ai_logs, settings
- Управление: systemctl restart smoki-bot; journalctl -u smoki-bot -n50

## AI

- google-genai через Vertex AI (USE_VERTEXAI=true, ADC service account)
- Резерв AI Studio по ключу GEMINI_API_KEY_FALLBACK
- Модели: gemini-2.5-flash (текст), gemini-2.5-flash-image (картинки)

## Контент-план (Europe/Moscow)

- Утро (8-10): 1-3 факта плюс авторских комментариев, до 120 слов, картинка.
- Вечер (19-20): лонг-рид 200-500 слов (деф. 350), картинка.
- Оба поста проходят автоцензуру и ручную модерацию (опубликовать / регенерировать / отклонить). При простое автопубликация по дедлайну.
- Длина настраивается: /setlen morning N (1-3), /setlen evening N (200-500).
- Ручная генерация (админ, ЛС): /generate (обычный), /generate_morning (утро+шутка), /generate_evening (лонг-рид).
- Время суток в промпт передаётся по фактическому времени генерации (daytime_label по локальному часу сервера), а не по жёстко зашитым окнам.
- Утренний пост ОБЯЗАТЕЛЬНО завершается короткой остроумной шуткой по теме.
- Grounding: тело статьи генерируется с Google Search (use_search=True в generate_text) — модель опирается на свежие материалы из интернета. Темы, цензура, картинки — без поиска.

## Комментарии

- Автомодерация в DISCUSSION_GROUP_ID каждые COMMENTS_INTERVAL_HOURS.
- Классы: reklama / toxic / question / neutral / positive.
- Ответы на question/neutral/positive; удаление reklama/toxic.

## Автоцензура

Нет призыва к покупке и курению; нет медсоветов; не утверждать пользу курения. Разрешено нейтральное упоминание брендов.

## Структура

- bot.py, config.py, scheduler.py
- db (schema.sql, database.py)
- ai (gemini.py, prompts.py)
- services (content.py, publisher.py, comments.py)
- handlers (admin.py, group.py, ROUTERS)
- scripts/ai_healthcheck.py

## Локальные проверки перед push (обязательно)

ruff установлен в venv (`ruff==0.15.12`, версия синхронна с CI). mypy тоже в venv.

Перед КАЖДЫМ push прогнать:

venv/bin/ruff check <изменённые_файлы> && venv/bin/python -m mypy <изменённые_файлы>

Автоисправление тривиальных замечаний ruff:

venv/bin/ruff check <файл> --fix

Полный прогон как в CI (джоба Ruff lint):

venv/bin/ruff check . --exclude venv,data,__pycache__

Это ловит ошибки (F541, неиспользуемые импорты и т.п.) до GitHub Actions и экономит запуски CI. Версии ruff/mypy в venv обязаны совпадать с CI: ruff==0.15.12, mypy==1.14.1.

## Smoke-тесты vs pytest

Ручной smoke (`python -c "asyncio.run(...)"`) — разовая проверка при разработке,
ловит баги до PR и экономит запуски CI. В CI НЕ входит.

Правило: ценную smoke-проверку оформлять постоянным pytest-тестом
(изоляция БД через фикстуру `tmp_db` из tests/conftest.py + `await db.init_db()`).
Пример: tests/test_stats.py.

## Админ-панель (inline)

/start у админа показывает inline-меню (callback namespace `adm_*`):
генерация обычный/утро/вечер, статистика (db.get_stats), длина постов,
правила «нравится»/цензуры, кнопка «Сделать бэкап» (adm_backup → отчёт
из journald: строки `backup ok`/`stats:`). Хелпер `_cb_msg` сужает
Message|InaccessibleMessage. При /start отправляется ReplyKeyboardRemove,
чтобы убрать старую reply-клавиатуру команд под полем ввода.

## CI: 10 джоб (обязательны все зелёные для merge)

1. Python syntax check (компиляция)
2. Ruff lint (ruff==0.15.12)
3. Bandit security (bandit==1.9.4, -ll, -x venv,data,__pycache__)
4. pip-audit
5. Pytest + coverage (--cov-fail-under=45)
6. codespell
7. mypy (mypy==1.14.1)
8. markdown lint (MD012 и др.)
9. yaml lint
10. gitleaks

main защищён, только через PR с зелёным CI. .env.example содержит все ключи config.py.

### Перед push .md-файлов

- НЕ допускать множественных пустых строк подряд (MD012 — максимум одна).
- Убирать хвостовые пробелы в строках.
- Файл обязан заканчиваться одним переводом строки.
- Локальная проверка (если установлен node):
  `npx markdownlint-cli2 "**/*.md"`
- Быстрый фикс MD012 без node:
  `python3 -c "import re,sys;p=sys.argv[1];s=open(p).read();open(p,'w').write(re.sub(r'\n{3,}','\n\n',s).rstrip(chr(10))+chr(10))" FILE.md`

## Бэклог админ-панели (по ручному smoke на проде)

Приоритет P1 — ломает UX, P2 — улучшение, P3 — nice-to-have.

- [ ] P1 #9 Кнопки «Обычный/Утро/Вечер» не запускают генерацию (adm_gen/adm_gen_m/adm_gen_e).
- [ ] P1 #10 «Обычный» → «Своя тема»: админ вводит тему текстом, бот отдельно уточняет длину (FSM), учитывает при генерации.
- [x] P2 #1 Меню команд бота (set_my_commands scope=admin + set_chat_menu_button MenuButtonCommands). Полный набор команд для админа, пусто для остальных. ✅ PR feat/bot-menu-commands
- [x] P2 #2 Убрать текстовую панель «SMOKI content bot готов… Команды:» и reply-клавиатуру команд под строкой ввода (оставить только inline). ✅ /start теперь показывает только inline-панель.
- [x] P2 #15 Кнопка «Сделать бэкап» в панели: запуск бэкапа + реальный отчёт из journald. ✅ Работает (PR #58/#59).
- [ ] P2 #3 Некорректный счётчик «Комментариев: 8» — уточнить логику get_stats (считать реальные комментарии, не все строки таблицы).
- [ ] P2 #5 Кнопка «Назад» в подменю (Длина/Цензура/Нравится → главное меню).
- [ ] P2 #6 Редактирование длины постов кнопками (не только /setlen).
- [x] P2 #7 Редактирование правил «нравится» через панель. ✅ PR #63 (feature/edit-rules-panel).
- [x] P2 #8 Редактирование правил цензуры через панель. ✅ PR #63 (feature/edit-rules-panel).
- [ ] P3 #4 Остаток квоты Vertex через SDK НЕДОСТУПЕН (только Cloud Quotas API + IAM — вне MVP). Вместо этого: суммировать РАСХОД токенов из resp.usage_metadata.total_token_count в ai_logs → показ «Токенов израсходовано» в статистике. Отложено, настроим последним.

## Синхронизация по коду (сверка тел функций handlers/admin.py)

> Реализовано и работает: генерация из кнопок (adm_gen/adm_gen_m/adm_gen_e →
> \_do_generate), FSM модерации (pub/pubfb/regen/rej/cancel + 3 waiting_*fb),
> команды /generate /generate_morning /generate_evening /setlen /id /start.
> Инлайн-панель \_admin_kb: Обычный/Утро/Вечер/Статистика/Длина/Нравится/Цензура.

- [x] #9 Кнопки «Обычный/Утро/Вечер» ЗАПУСКАЮТ генерацию (cb_adm_gen*). Работает.

## КРИТИЧНЫЕ БАГИ автоведения (найдено на проде, скриншот группы)

- [x] P0 #13 (устранено, код соответствует SPEC: group.py фильтрует is_bot/sender_chat/автопересылку, comments.py отвечает только на реальные из БД, при 0 новых ничего не постит) Бот ГЕНЕРИТ фейковые комментарии («Ежик в тумане» пишет сам
      себе десятки сообщений), вместо ОТВЕТОВ на реальные комментарии.
      ПРАВИЛЬНАЯ логика:
        1) раз в COMMENTS_INTERVAL_HOURS бот выгружает РЕАЛЬНЫЕ комментарии
           к посту из DISCUSSION_GROUP_ID;
        2) отдаёт их ИИ; ИИ САМА выбирает, на какой(ие) ответить, и возвращает
           пары (comment_id → текст ответа);
        3) бот постит ответ РЕПЛАЕМ на выбранный комментарий.
      ЗАПРЕТ: если новых комментариев НЕТ — НИЧЕГО не генерировать и не постить.
      Проверить: services/*.py и handlers/group.py — где триггерится генерация
      комментов, убрать «самокомментирование».

- [ ] P1 #14 Утренний пост сгенерировался БЕЗ картинки. Проверить в
      _do_generate/content.generate_article путь генерации изображения для
      fmt="morning" — вероятно image-ветка пропускается или падает молча.
      Ожидание: у всех форматов (обычный/утро/вечер) есть картинка либо явный
      фолбэк, а не тихий пропуск.

## Свежие технические задачи (разведка)

- [ ] P2 #10 «Обычный» → своя тема: FSM waiting_topic + waiting_length
      (_do_generate(fmt="") сейчас берёт случайную тему).
- [ ] P2 #12 /setlen перевести на inline-кнопки ±1 / ±50 (связано с P2 #6).
- [~] #16 Картинки поста в формате 3:2 (широкие). Через промпт (SDK 1.5.0 не умеет ImageConfig/aspect_ratio). В работе: fix/image-3-2. Если модель мажет — добавить Pillow-кроп по центру.
- [ ] #17 Модерация/паблик: фото сшивать с ПЕРВОЙ частью текста (caption ≤1024), остаток отдельными сообщениями, кнопки на последнем.
