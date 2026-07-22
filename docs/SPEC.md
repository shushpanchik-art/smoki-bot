# SMOKI-bot

## Назначение

Автоведение Telegram-канала @SMOKTOLK (вейпы, кальяны, табак) с AI-генерацией контента, ручной модерацией и автомодерацией комментариев.

## Инфраструктура

- Путь: /opt/SMOKI/bot, venv venv/bin/python
- systemd: smoki-bot (Restart=always), режим polling
- Python 3.11.2, aiogram 3.30.0, aiosqlite 0.22.1, apscheduler 3.11.3, SQLAlchemy 2.0.51 (persistent jobstore), python-dotenv 1.2.2, Pillow 12.3.0, telethon 1.44.0, google-genai 2.13.0, google-cloud-bigquery 3.27.0
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
- Дедлайн-джоба `_job_deadline` запускается ДВАЖДЫ: в PUBLISH_WINDOW_END и в EVENING_DEADLINE_HOUR:EVENING_DEADLINE_MINUTE (деф. 20:30 MSK). Публикует ВСЕ зависшие статьи дня (get_undelivered_today → pending/approved за сегодня), затем шлёт админу сводку опубликованных/неудачных.
- Предпросмотр (U2): за PREVIEW_WARN_MINUTES мин (деф. 15) до каждого дедлайна джоба `_job_preview_warn` (`preview_warn_day`/`preview_warn_evening`) шлёт админу список зависших #id статей, которые скоро уйдут автоматически. Отдельного namespace кнопок нет — управление через существующие ✅ Опубликовать / ⛔ Отмена под самими черновиками. Если зависших статей нет — пропуск.
- Длина настраивается: /setlen morning N (1-3), /setlen evening N (200-500).
- Ручная генерация (админ, ЛС): /generate (обычный), /generate_morning (утро+шутка), /generate_evening (лонг-рид).
- `/story` — вручную сгенерировать один channel-слот сторис и отправить админу на модерацию (переиспользует `generate_channel_slot` + `send_story_for_moderation`).
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
- docs (SPEC.md, TESTING.md, PROJECT_BOOK.txt)

## Локальные проверки перед push (обязательно)

ruff установлен в venv (`ruff==0.15.12`, версия синхронна с CI). mypy тоже в venv.

Перед КАЖДЫМ push прогнать:

venv/bin/ruff check <изменённые_файлы> && venv/bin/python -m mypy <изменённые_файлы>

Автоисправление тривиальных замечаний ruff:

venv/bin/ruff check <файл> --fix

Полный прогон как в CI (джоба Ruff lint):

venv/bin/ruff check . --exclude venv,data,**pycache**

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
3. Bandit security (bandit==1.9.4, -ll, -x venv,data,**pycache**)
4. pip-audit
5. Pytest + coverage (--cov-fail-under=45)
6. codespell
7. mypy (mypy==1.14.1)
8. markdown lint (MD012 и др.)
9. yaml lint
10. gitleaks

Репозиторий публичный (Actions бесплатны). main защищён, только через PR с зелёным CI. .env.example содержит все ключи config.py.

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

- [x] P1 #9 (устранено: хендлеры `cb_adm_gen/_m/_e` зарегистрированы, `callback_data` совпадают, тела вызывают `_do_generate` → `content.generate_article` → `send_for_moderation`; guard проверяет админа; в логах callback-ошибок нет) Кнопки «Обычный/Утро/Вечер» не запускают генерацию (`adm_gen`/`adm_gen_m`/`adm_gen_e`).
- [x] P1 #10 «Обычный» → «Своя тема»: кнопка спрашивает тему (FSM `waiting_custom_topic`), `-` = случайная. Уточнение длины отложено в P2. ✅ feature/spec-10-custom-topic.
- [x] P2 #1 Меню команд бота (set_my_commands scope=admin + set_chat_menu_button MenuButtonCommands). Полный набор команд для админа, пусто для остальных. ✅ PR feat/bot-menu-commands
- [x] P2 #2 Убрать текстовую панель «SMOKI content bot готов… Команды:» и reply-клавиатуру команд под строкой ввода (оставить только inline). ✅ /start теперь показывает только inline-панель.
- [x] P2 #15 Кнопка «Сделать бэкап» в панели: запуск бэкапа + реальный отчёт из journald. ✅ Работает (PR #58/#59).
- [x] P2 #22 Telegram-уведомления об АВТО-бэкапах админу: `scripts/notify_admin.sh` (события backup/offsite/offsite-full — failed/recovered + периодическая сводка backup-ok, анти-дубликаты через state-файлы в /var/lib/smoki-backup). Подключено: systemd `OnFailure=*-alert.service` (провал) и `trap ERR`/`*-recovered` в backup_offsite.sh / backup_full_offsite.sh (успех/восстановление). После успешного offsite backup_offsite.sh явно вызывает `backup-ok` (PR #83) — админу приходит ежедневное «✅ backup OK» (не чаще раза в 20 ч). Проверено на проде: сообщение доходит. Дополнительно (PR #90): systemd timer `smoki-backup-summary` (23:45 MSK) шлёт ежедневную сводку бэкапов; эталоны юнитов в deploy/systemd/.
- [x] P2 #3 Счётчик комментариев исправлен (PR #80): get_stats() возвращает comments_total (все полученные) и comments_new (ждут обработки); панель показывает получено/отвечено/ждут/удалено.
- [x] P2 #5 Кнопка «Назад» в подменю реализована: `_back_kb()`/`_len_kb()` содержат кнопку `adm_back`, обработчик `cb_adm_back` (handlers/admin.py) возвращает в главное меню и сбрасывает FSM. Присутствует в подменю Длина/Нравится/Цензура.
- [x] P2 #6 Редактирование длины постов кнопками (не только /setlen). ✅ Реализовано: `_len_kb`/`cb_adm_len`/`cb_len_adjust` (handlers/admin.py) — inline ±, утро шаг 1 (1-3), вечер шаг 50 (200-500), запись в БД (morning_facts/evening_words).
- [x] P2 #7 Редактирование правил «нравится» через панель. ✅ PR #63 (feature/edit-rules-panel).
- [x] P2 #8 Редактирование правил цензуры через панель. ✅ PR #63 (feature/edit-rules-panel).
- [x] P1 #19 Автопубликация по дедлайну ДОРАБОТАНА (PR #89): вторая дедлайн-джоба `publish_deadline_evening` в 20:30 (EVENING_DEADLINE_HOUR/MINUTE); `_job_deadline` публикует ВСЕ зависшие статьи дня (не одну), сводка админу; тест tests/test_deadline.py. Исходная разведка: бага в коде нет. `_job_deadline` (cron `hour=PUBLISH_WINDOW_END`, `misfire_grace_time=3600`, `coalesce=True`) публикует статьи в статусе draft. Пропуск объяснён простоем службы вне окна публикации. Риск снижается persistent jobstore — см. P2 #21.
- [x] P3 #4 РЕАЛИЗОВАНО (= U1): расход токенов суммируется из ai_logs (input_tokens+output_tokens, ~длина/4) в db.get_stats()->tokens_total; панель показывает «🧮 Токенов израсходовано» (handlers/admin.py cb_adm_stats). Остаток квоты Vertex через SDK недоступен (только Cloud Quotas API + IAM — вне MVP), поэтому показываем именно РАСХОД.

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

- [x] P1 #14 (устранено: единый путь generate_article(make_image=True) для утра/вечера/обычного; логи подтверждают image=True у всех, в т.ч. утренних #37/#38; publisher.send_photo_with_text корректно шлёт фото+caption с явным фолбэком) Утренний пост сгенерировался БЕЗ картинки. Проверить в
      _do_generate/content.generate_article путь генерации изображения для
      fmt="morning" — вероятно image-ветка пропускается или падает молча.
      Ожидание: у всех форматов (обычный/утро/вечер) есть картинка либо явный
      фолбэк, а не тихий пропуск.

## Свежие технические задачи (разведка)

- [x] P2 #10 «Обычный» → своя тема: уточнение ДЛИНЫ через FSM (`waiting_custom_length`) после ввода темы.
      Ввод темы (`waiting_custom_topic`) реализован в P1. ✅ feature/spec-10-custom-length.
- [x] P2 #21 Persistent jobstore (SQLAlchemyJobStore на smoki.db) вместо memory:
      пропущенные при простое джобы (дедлайн, публикация) отрабатывают после старта. ✅ feature/spec-21-persistent-jobstore (смёржен).
- [x] P2 #12 /setlen на inline-кнопки ±1 / ±50 — реализовано вместе с #6 (кнопки `len:m:±`/`len:e:±`, callback `cb_len_adjust`; /setlen остался как дубль для быстрого доступа).
- [x] #17 Модерация/паблик: фото сшивать с ПЕРВОЙ частью текста (caption ≤1024), остаток отдельными сообщениями, кнопки на последнем. ✅ Реализовано в `services/publisher.send_photo_with_text` (`_caption_split` по абзацу ≤1024, `_split` остатка, `reply_markup` на последнем); используется в `publish_article` и `handlers/admin.py`.

## Выученные уроки (операционные)

- **Формат картинки 4:5 (best practice)**: на мобильных постах Telegram картинка 4:5 (портрет) смотрится лучше квадрата/горизонта — занимает больше экрана, выше вовлечённость. Подтверждено тестом владельца на телефоне. Реализация — `ai/gemini._crop_landscape(ratio=4/5)` (дефолт), кроп квадрата 1024x1024 на нашей стороне (SDK не умеет `aspect_ratio`). НЕ откатывать к 3:2/квадрату. См. §U7.

- **Беспарольный рестарт**: настроен sudoers drop-in `/etc/sudoers.d/smoki-bot`
  (по образцу `smoktolk-bot`). Разрешены без пароля: `systemctl restart/start/stop/status smoki-bot`.
  Проверка синтаксиса перед активацией обязательна: `sudo visudo -c`.
  Тест: `sudo -n systemctl restart smoki-bot` (флаг `-n` = не спрашивать пароль).
- **Чистка веток-зомби**: смёрженные локальные ветки удалять `git branch -d <name>`;
  устаревшие remote-tracking refs — `git remote prune origin`.
  После merge PR через UI удалённая ветка на GitHub исчезает, локально остаётся зомби.
- **Кэш байткода**: каталоги `**pycache**` покрыты `.gitignore`, git их не видит; периодически чистить
  `find . -path ./venv -prune -o -name **pycache** -type d -exec rm -rf {} +`.
- **journalctl**: для свежих логов после рестарта надёжнее `--since` по времени,
  чем `-n50` (последнее может захватить хвост старого процесса).

## Эксплуатация: CI troubleshooting

### Репозиторий публичный

`shushpanchik-art/smoki-bot` — публичный. Для публичных репозиториев
GitHub Actions бесплатны без лимита минут. Ранее репозиторий был приватным.

### Симптом: все джобы падают мгновенно (steps=0)

Если `gh run view` с флагом `--json jobs` показывает у ВСЕХ джоб
`conclusion=failure` и `steps=0` (ни один шаг не стартовал), а логи пустые —
это НЕ ошибка кода. GitHub отказывается запускать job из-за биллинга:
исчерпан бесплатный лимит минут Actions на приватном репозитории либо
выставлен spending limit $0.

Диагностика (факты, не догадки):

```bash
gh run view <ID> --json jobs -q '.jobs[] | .name + ": " + .conclusion'
```

- `steps=0` у всех — биллинг/инфраструктура, не код.
- `steps>0` плюс конкретный упавший шаг — реальная ошибка, чинить предметно.

Лечение (по приоритету):

1. Сделать репозиторий публичным — Actions становятся бесплатны (текущее
   решение). ВАЖНО: перед публикацией прогнать `gitleaks detect` по всей
   истории и убедиться, что утечек нет.
2. Либо снять spending limit на странице github.com/settings/billing
   (раздел Budgets and alerts).

Проверено на практике: после перевода репо в public тот же упавший run
через `gh run rerun` завершился со статусом completed/success без изменений
кода.

### Проверка секретов в истории

Перед публикацией репозитория (и периодически) прогонять:

```bash
gitleaks detect --source . --no-banner
```

Паттерны вида регулярного выражения на PRIVATE KEY в коде — это детектор
секретов, а НЕ сам ключ; ложных срабатываний по ним нет. Файл `.env`
в историю никогда не коммитился (он в `.gitignore`).

## Бэклог: надёжность, UX, безопасность (разведка 2024)

Приоритет: P1 — риск потери контента/невидимого сбоя, P2 — заметное улучшение,
P3 — nice-to-have. Разведка перед реализацией обязательна (не по памяти).

### A. Отказоустойчивость / надёжность

- [x] R1 (P1) Watchdog доставки в канал. РЕАЛИЗОВАНО (PR feature/r1-delivery-watchdog): джоба _job_delivery_watchdog в PUBLISH_WINDOW_END+2 ч, get_undelivered_today() (pending/approved за сегодня), алерт админу в ЛС. `Restart=always` перезапускает
  процесс, но не гарантирует, что пост реально ушёл в Telegram. При ошибке/
  таймауте API статья остаётся в `draft`, админ не узнаёт. Если к концу окна
  публикации статья дня НЕ в статусе `published` — алерт админу в ЛС.
  Факт разведки: `bot.send_message(config.ADMIN_CHAT_ID, ...)` уже есть
  в scheduler.py (канал алерта готов); `_job_deadline` публикует draft, но
  успех не проверяет.
- [x] R2 (P1) Health-heartbeat. РЕАЛИЗОВАНО: scheduler.py `_job_heartbeat`
  (IntervalTrigger каждые HEARTBEAT_INTERVAL_HOURS ч (config-дефолт 6, на
  проде .env=4), id="heartbeat",
  next_run_time=now) пишет маркер `HEARTBEAT ok` в journald. Внешний
  systemd-timer smoki-heartbeat + scripts/heartbeat_healthcheck.sh грепает
  journald на свежесть маркера (порог HEARTBEAT_MAX_AGE_HOURS=8) и алертит
  админу, если бот/scheduler завис (процесс жив, но цикл встал — сам себя не
  проверит). config: HEARTBEAT_INTERVAL_HOURS, HEARTBEAT_MAX_AGE_HOURS в
  .env.example. Юниты: deploy/systemd/smoki-heartbeat.service/.timer.
  Тесты: tests/test_heartbeat.py (джоба зарегистрирована, маркер в лог).
- [x] R3 (P2) Ретраи AI с экспоненциальной паузой. РЕАЛИЗОВАНО: в ai/gemini.py
  `_call_with_retry` оборачивает вызовы модели — до `_MAX_ATTEMPTS` попыток с
  экспоненциальным backoff; повтор только на транзиентных ошибках
  (`_is_transient`: ServerError/5xx и ClientError 429), перманентные (400 и пр.)
  пробрасываются сразу. Переключение primary->fallback сохранено. Тесты:
  tests/test_gemini.py (классификация, успех после повтора, исчерпание, без
  повтора на перманентной).
- [x] R4 (P2) Проверка целостности бэкапов (restore-test). РЕАЛИЗОВАНО
  (feature/r4-r5-restore-test-integrity): `scripts/backup_restore_test.sh` раз
  в неделю берёт свежий бэкап из /var/backups/smoki, восстанавливает во
  временный файл, гоняет `PRAGMA integrity_check` и проверяет наличие всех
  таблиц (articles и др.), пишет отчёт в logs/backup-restore-test.log
  (`restore-test ok: integrity=ok, ... articles=N`). Юниты
  smoki-backup-restore-test.service/.timer (Mon 04:17 MSK, Persistent=true,
  After=smoki-backup.service) — эталоны в deploy/systemd/. Алерты админу через
  notify_admin.sh (restore-test-failed/-recovered, анти-дубли state-файлом
  /var/lib/smoki-backup/restore-test-failed). Проверено на проде: status=0,
  integrity=ok, articles=39.
- [x] R5 (P3) `PRAGMA integrity_check` перед бэкапом smoki.db — РЕАЛИЗОВАНО
  (feature/r4-r5-restore-test-integrity): backup.sh после `sqlite3 .backup`
  во временный снимок гоняет `PRAGMA integrity_check` ДО архивации; при
  результате != "ok" — die (бэкап не создаётся, ошибка в лог/алерт). Ловит
  коррупцию БД раньше, чем она уедет в архив.

### B. Пользовательский опыт (админ)

- [x] U1 (P2) РЕАЛИЗОВАНО (= P3 #4): суммирование токенов в ai_logs
  (db.get_stats->tokens_total) и показ «🧮 Токенов израсходовано» в
  панели статистики (handlers/admin.py cb_adm_stats). Админ видит расход.
- [x] U2 (P2) Предпросмотр перед автопубликацией. РЕАЛИЗОВАНО (PR #99,
  fix/scheduler-preview-warning): за PREVIEW_WARN_MINUTES мин (деф. 15,
  config/.env) до каждого дедлайна `_job_preview_warn` шлёт админу список
  зависших #id с предупреждением об авто-публикации. Управление —
  существующими кнопками ✅ Опубликовать / ⛔ Отмена под черновиками
  (новый namespace не вводился осознанно). Хелпер `_minus_minutes` +
  тесты tests/test_minus_minutes.py.
- [x] U3 (P3) Кнопка «💬 Комментарии» в панели. РЕАЛИЗОВАНО:
  db.get_recent_comments(N) + inline-кнопка `adm_comments`
  (handlers/admin.py cb_adm_comments) показывает последние 10 комментов
  с классом ИИ и ответом бота; при пустой таблице — «Комментариев пока нет».
  Прозрачность автомодерации без чтения журналов группы.
- [x] U5 (P2) Image-prompt из ТЕКСТА статьи. РЕАЛИЗОВАНО (feature/u5-image-scene-from-text): в services/content.generate_article после цензуры шаг ИИ (_text(prompts.image_scene_prompt(body))) генерит EN-описание сцены по телу статьи, оно идёт в prompts.image_prompt_from_scene(scene, topic); фолбэк на prompts.image_prompt(topic) при пустом ответе/ошибке. Constraints (NO TEXT, 4:5) сохранены. Тест tests/test_image_scene.py. Историческое описание проблемы: Проблема (прод, скриншоты):
  картинки однотипны — `prompts.image_prompt(topic)` строит сцену
  детерминированно (hash темы -> _IMG_SCENES/_IMG_PALETTES), поэтому
  одинаковая/близкая тема -> одинаковая картинка, тем немного -> повтор.
  Фикс: после цензуры (services/content.py, до блока img_prompt=...) шаг
  ИИ генерит краткое EN-описание сцены по телу статьи `body`
  (новый prompts.image_scene_from_text(body) + gemini.generate_text,
  use_search=False); описание подставляется в image_prompt вместо
  hash-сцены/topic. Жёсткие constraints (NO TEXT, 4:5, fill frame, no logos)
  сохранить. Фолбэк на текущий image_prompt(topic) при пустом ответе ИИ.
  Тест tests/test_image_scene.py. Отдельный PR (код).

- [x] U4 (P2, = #10) Уточнение ДЛИНЫ своей темы через FSM. РЕАЛИЗОВАНО
  (PR test/u4-custom-length): цепочка cb_adm_gen -> waiting_custom_topic
  (fb_custom_topic) -> waiting_custom_length (fb_custom_length) в
  handlers/admin.py. Число 200-500 -> prompts.words_rule -> length_hint
  в _do_generate; `-`/пусто -> стандартная длина. Тесты:
  tests/test_u4_custom_length.py (переход FSM, парсинг числа, дефолт,
  игнор не-админа).

### C. Безопасность / эксплуатация

- [x] S1 (P3) gitleaks в pre-commit локально (не только CI/публикация) — после
  перевода репо в public цена случайного коммита секрета выросла.

## U6 — Авто-Stories @SMOKTOLK + @smoktolk_flood (userbot / Telethon, MTProto)

Отдельный процесс `smoki-userbot.service` (Telethon), НЕ внутри aiogram-бота.
Связь bot <-> userbot через общую БД (таблица `story_jobs`).

Риск: использование MTProto для автоматизации нарушает ToS Telegram,
возможна блокировка аккаунта. Риск принят владельцем проекта.

### U6.1 БД

Таблица `story_jobs`:

- `id`, `target` (`channel` / `flood`)
- `theme` (номер темы 1..5), `prompt_en` (промпт NanoBanana на английском)
- `image_path`, `caption`
- `status` (`pending` / `approved` / `published` / `rejected` / `cancelled`)
- `feedback` (замечания админа при отклонении)
- `created_at`, `publish_at`, `story_msg_id`

### U6.2 Канал @SMOKTOLK (генерация новых сторис)

- [x] Промпты и конфиг РЕАЛИЗОВАНЫ (feature/u6.2a-story-config-prompts): `ai/prompts.STORY_THEMES`, `story_text_prompt`, `story_flood_caption_prompt`, `story_image_prompt` (9:16, 1080x1920, текст на русском разрешён); веса/лимиты/таймаут в `config.py` (`STORY_WEIGHT_*`, `STORY_CHANNEL_MIN/MAX_PER_DAY`, `STORY_FLOOD_MIN/MAX_PER_DAY`, `STORY_APPROVE_TIMEOUT_MIN`). Тест `tests/test_story_prompts.py`. TODO (U6.2b): задачник-планировщик слотов, генерация картинок, запись в `story_jobs`.
- [x] Планировщик слотов РЕАЛИЗОВАН (feature/u6.2b-story-generator): `services/stories.py` (`pick_theme` по весам, `plan_daily_channel/flood`, `generate_channel_slot`/`generate_flood_slot` → `story_jobs` status='pending'); джобы `plan_stories_channel/flood` в scheduler (CronTrigger `STORY_PLAN_HOUR`). Тест `tests/test_stories.py`. TODO (U6.3): публикация approved-слотов.

- 3-7 сторис в день (случайно), слоты пишутся в задачник ежедневно.
- Выбор темы по весам: шутка 15% / новость 25% / новинки 25% /
  факт 30% / пожелание 5%.
- Темы 1-4: сначала `generate_text(use_search=True)` — поиск факта/новости.
- Далее генерируется NanoBanana-промпт на английском + системный блок:
  размер 1080x1920 (9:16, формат сторис), текст на картинке на русском,
  строгая проверка читаемости, без артефактов.

### U6.3 Группа @smoktolk_flood (-1003918721575) — реюз картинок

- 5-12 сторис в день (случайно), слоты в задачник ежедневно.
- Реюз готовых картинок из `story_jobs` со статусом `published`.
- `caption` = интересный факт по теме, 20-50 слов
  (`generate_text(use_search=True)`), лимит длины проверяется (enforce).

### U6.4 Approve-flow (в aiogram-боте, ЛС админу)

- Показ картинки + подписи, inline-кнопки `[Опубликовать] [Отклонить] [Отмена]`.
- Тишина 1 час -> автопубликация (`publish`).
- Отклонить -> бот спрашивает "что не так" -> регенерация с учётом `feedback`.
- Отмена -> слот пропущен (`status=cancelled`).

- [x] Approve-flow РЕАЛИЗОВАН (feature/u6-4-story-approve): `handlers/admin.send_story_for_moderation` (фото+подпись, kb `story:ok/rej/cancel`), callbacks `cb_story_ok/rej/cancel`, FSM `ModerationStates.waiting_story_reject_fb` (отклонить → запрос feedback → регенерация). Джоба `_job_send_pending_stories` в scheduler (`IntervalTrigger` 10 мин) шлёт на модерацию pending-слоты с наступившим `publish_at` через `db.get_due_pending_story_jobs`. Approve → `status=approved` (userbot публикует по `get_due_approved_story_jobs`). Тест `tests/test_story_approve.py`.

### U6.5 Публикация (userbot)

- userbot читает `approved` записи `story_jobs` c `publish_at <= now`.
- `SendStoryRequest(peer, InputMediaUploadedPhoto, period=86400)`.
- Канал должен быть бустнут до уровня доступности Stories
  (без буста метод вернёт ошибку прав — прод-запуск только после буста).

- [x] Публикация userbot РЕАЛИЗОВАНА-КОД (feature/u6-5-userbot-publish): `userbot.py` — отдельный процесс, Telethon импортируется ЛЕНИВО внутри функций (модуль тестируется без установленного telethon). `process_due_stories(client)` читает `db.get_due_approved_story_jobs(now)`, `_publish_story` шлёт `SendStoryRequest(peer, InputMediaUploadedPhoto, period=86400)` (peer = CHANNEL_ID для channel / STORY_FLOOD_CHANNEL для flood), затем `update_story_job(status='published', story_msg_id=...)`; ошибка отдельного слота → `status='error'`, цикл не падает. `main()` — цикл с POLL_INTERVAL_SEC=300. Юнит `deploy/systemd/smoki-userbot.service` (Restart=always). Тест `tests/test_userbot.py` (мок публикации: approved-due→published, пропуск pending, ошибка→error, `_extract_story_id`).

### U6.STORIES-FROZEN — экономика Stories и решение [ЗАМОРОЖЕНО]

**СТАТУС: заморожено — экономически нецелесообразно.** Публикация Stories
от имени канала требует, чтобы канал был «забустен» до нужного уровня.
Бусты — это ПОСТОЯННЫЙ (ежемесячный) расход, не разовая покупка: буст живёт,
пока активна Premium-подписка давшего его пользователя / срок покупки
(обычно 30 дней). Через месяц уровень падает — надо платить снова.

**Правило уровней Stories (факт Telegram 2025):** Level = число Stories в
день.

- Level 1 → 1 story/день
- Level 2 → 2 story/день
- Level 3 → 3 story/день
- … максимум Level 100 → 100 story/день
- Лимит сбрасывается через 24 ч после первой story за день; удаление story
  НЕ освобождает слот.

**Сколько подписчиков → какой уровень (сколько бустов надо):** количество
бустов на уровень НЕ фиксировано, зависит от числа подписчиков.
Формула: `коэффициент = floor(подписчики / 250) + 1`.
Бустов на уровень: уровни 1–8 → `ceil(коэффициент × уровень / 2)`;
уровень 9 → `коэффициент × 7`; уровень 10+ → `коэффициент × уровень`.

Примеры:

- Канал <250 подписчиков (коэффициент 1): Level 1 ≈ 1 буст, Level 2 ≈ 1 буст,
  Level 3 ≈ 2 буста.
- Канал 1000 подписчиков (коэффициент 5): Level 1 = 3 буста, Level 2 = 5,
  Level 9 = 35, Level 10 = 50 бустов.
- Грубое правило: ~4 буста на каждую 1000 подписчиков за уровень.

**Откуда бусты:** легально их дают только Premium-подписчики (покупка
Premium = 4 буста, подарок Premium = 3 буста дарителю, полученный в подарок
Premium = 1 буст). Напрямую за Telegram Stars буст НЕ покупается. Через
сторонние сервисы ~$17.5/мес за 10 бустов на 30 дней (РИСК: накрутку могут
снять, не легально).

**Стоимость для владельца:** ежемесячный расход, растёт с числом
подписчиков. Для мелкого канала стартовый порог низкий (1 буст = 1 story/
день), но всё равно постоянные траты.

**Условие разморозки:** органический рост подписчиков до бесплатных бустов
от аудитории ИЛИ решение владельца платить помесячно. Код публикатора
(U6.5, userbot.py) уже готов — при разморозке остаётся ручной шаг U6.5b.

- [ ] U6.5b РУЧНОЙ ПРОД-ШАГ (ждёт API от владельца): реальные `TG_API_ID`/`TG_API_HASH`/`TG_USERBOT_PHONE` в `.env`; интерактивная авторизация сессии (SMS-код, первый запуск в TTY); буст канала @SMOKTOLK до уровня Stories; `pip install telethon==1.44.0` в venv; `systemctl enable --now smoki-userbot`. БЕЗ буста SendStoryRequest вернёт ошибку прав — прод-запуск только после буста.

### U6.7 Наложение текста на картинку (Pillow)

- [x] РЕАЛИЗОВАНО (feature/u6-7-story-render): `services/story_render.py` — `render_story_caption(image_bytes, caption)` кропает/масштабирует картинку под 1080x1920 (9:16, `Image.Resampling.LANCZOS`), рисует подпись внизу белым жирным шрифтом на полупрозрачной тёмной подложке (перенос по словам, русский текст). Константы: `_FONT_SIZE`, `_MAX_CHARS`, `_BOTTOM_MARGIN`, `_SIDE_MARGIN`. Используется в pipeline перед публикацией сторис. Тест `tests/test_story_render.py`.

### U6.6 Конфиг и зависимости

- `.env`: `TG_API_ID`, `TG_API_HASH`, `TG_USERBOT_PHONE`.
- `.env.example`: те же ключи с плейсхолдерами
  (иначе `test_env_example` в CI упадёт, если config их читает).
- Файл сессии `*.session` -> в `.gitignore`; путь сессии -> в `bandit -x`. (DONE: `.gitignore`)
- requirements: `telethon`. (DONE: `telethon==1.44.0`)
- `.env`/`.env.example` дополнены (U6.2a): `STORY_WEIGHT_JOKE`, `STORY_WEIGHT_NEWS`, `STORY_WEIGHT_NEW_PRODUCTS`, `STORY_WEIGHT_FACT`, `STORY_WEIGHT_WISH`, `STORY_CHANNEL_MIN_PER_DAY`, `STORY_CHANNEL_MAX_PER_DAY`, `STORY_FLOOD_MIN_PER_DAY`, `STORY_FLOOD_MAX_PER_DAY`, `STORY_APPROVE_TIMEOUT_MIN` (значения = дефолты config).

### U7 — Формат картинки поста (РЕШЕНО: 4:5)

- РЕШЕНИЕ ВЛАДЕЛЬЦА (подтверждено тестом на телефоне): формат картинки
  постов — портрет **4:5**. На мобильных статьи с 4:5 смотрятся лучше всего
  (картинка занимает больше экрана, выше вовлечённость). Откат к квадрату/3:2
  НЕ делаем.
- Реализация: `ai/gemini._crop_landscape(ratio=4/5)` (дефолт) центрально
  кропает квадрат 1024x1024 от NanoBanana в 4:5. SDK не умеет `aspect_ratio`,
  поэтому кроп на нашей стороне — это штатный и одобренный путь.
- Промпты картинки (`image_prompt`, `image_prompt_from_scene`) соотношение
  сторон НЕ задают (модель всё равно отдаёт квадрат) — важно лишь требование
  «fill frame edge to edge, no bars», чтобы после кропа не было полос.
- Тест-инвариант: `tests/test_image_crop.py` фиксирует дефолт `ratio=4/5`.

## U8 — Единая панель управления расписаниями (админ, inline) [P2, НОВАЯ]

Задача владельца: дать админу ОДНО место, где видно и настраивается ВСЁ
расписание бота — посты (утро/вечер, дедлайны, предпросмотр), сторис
(планирование channel/flood, окно approve), бэкапы (локальный/offsite/
full/summary/restore-test), heartbeat, комментарии.

Scope (разведка обязательна перед реализацией — не по памяти):

- [x] U8.1 ✅ Экран «🗓 Расписания» (`adm_schedule`): читает
      живые джобы APScheduler (`scheduler.get_jobs()` / `job.next_run_time`)
      и показывает для каждой: имя, тип триггера, следующий запуск (MSK).
      Плюс отдельным блоком — systemd-таймеры бэкапов (не APScheduler):
      парсить `systemctl list-timers 'smoki-*' --no-pager` или показывать
      статику из config/эталонов deploy/systemd.
- [x] U8.2 ✅ (реализовано частично: час утро/вечер) Редактирование через кнопки (аналогично
      «Длина постов»): окна PUBLISH/GEN, часы дедлайнов, STORY_PLAN_HOUR,
      COMMENTS_INTERVAL_HOURS, лимиты сторис в день. Хранить override в
      таблице `settings` (как morning_facts/evening_words), scheduler
      читает settings при старте/reschedule. НЕ править .env из бота.
- [x] U8.3 ✅ Кнопка «Пауза/Возобновить» отдельной джобы
      (`scheduler.pause_job/resume_job` по id) — например временно
      остановить сторис, не трогая посты.
- [x] U8.4 ✅ Тесты (test_schedule_time.py и др.): текст экрана,
      применение override из settings, пауза/резюм.

Разведка (факты, которые нужно собрать ДО кода):

- перечень всех `add_job(... id=...)` в scheduler.py и их триггеры;
- какие параметры реально управляют временем (config.py);
- умеет ли текущий scheduler reschedule на лету или нужен рестарт;
- где брать next_run_time (объект scheduler хранится в `_bot`? модульный?).

Открытый вопрос: часть расписаний — systemd-таймеры (бэкапы), часть —
APScheduler (контент/сторис). Панель должна показывать оба, но
РЕДАКТИРОВАТЬ из бота можно только APScheduler-джобы; таймеры бэкапов —
только просмотр (правка через deploy/systemd + rsync на сервер).

## U8.2 — управление расписанием из админ-панели

### Состояние (обновляется по мере работы)

- **U8.1** ✅ — экран `adm_schedule`: показ джоб и `next_run_time`
  (`services/schedule_view.build_schedule_text`).
- **U8.2a** ✅ — пауза/возобновление контентных задач
  (`services/schedule_control.py`). Персист в `settings["paused_jobs"]`
  (CSV). Тумблеры `sched:toggle:<job_id>` в экране расписаний.
  Восстановление при старте: `apply_persisted_pauses()` из `bot.main`
  после `scheduler.start`. Белый список `PAUSABLE_JOBS` — сторожа
  `heartbeat`/`delivery_watchdog` не паузятся. Коммит `c6c24f9`.
- **U8.2b** 🔄 — изменение часа утренней/вечерней публикации.
  `TIME_EDITABLE = {daily_morning: MORNING_START, daily_evening:
  EVENING_START}`. Override в `settings["time_<job>"]` (час 0-23).
  `effective_hour` = override → иначе config-дефолт. Экран `sched:times`,
  кнопки `sched:time:<job>:<±1>` двигают час, `set_hour` пишет в settings
  - `reschedule_job` (минута случайная). Применяется при старте внутри
  `apply_persisted_pauses`. Тесты `tests/test_schedule_time.py`.
- **U8 статус ✅ на проде** — /start → 🗓 Расписания показывает: джобы
  APScheduler c next_run (MSK), отдельный блок системных таймеров бэкапов
  (только просмотр), тумблеры Вкл/Выкл (сторис на паузе), под Утренним/
  Вечерним ряд ➖ 🕑 HH:00 ➕. Переживает рестарт (paused_jobs, time_* из
  settings). Проверено скриншотом владельца 15.07.
- **U8.2c** 🎨 — кнопки времени встроены в главный экран расписаний.
  Отдельный экран `sched:times` и `_build_times_ui` удалены. В `_build_schedule_ui` под тумблером каждой джобы из `TIME_EDITABLE` ряд `➖ / 🕑 HH:00 / ➕` (`sched:time:<job>:<±1>`). Хендлер `cb_sched_time_adjust` перерисовывает главный экран.

### Дальнейшие шаги (если прервёмся)

U8.1/U8.2a/U8.2b/U8.2c — реализованы и смёржены в main, работают на проде.
Стандартный цикл при новых пунктах: ветка → pytest/ruff/mypy → push → PR →
зелёный CI → merge UI → main pull → branch -d → prune → рестарт+проверка панели.

### Возможные будущие пункты U8

- U8.3 — редактирование интервалов (`COMMENTS_INTERVAL_HOURS` и т.п.).
- U8.4 — ручной «запустить сейчас» для контентной джобы (run_job).

## U9 — Оценка стоимости AI и прогноз бюджета [БЭКЛОГ, вернёмся позже]

Факт разведки: `est_cost_usd` в ai_logs записывается всегда 0 (никто не
считает); панель показывает только сырое число токенов (tokens_total).
Реального «баланса токенов» у Vertex AI НЕТ (pay-as-you-go, лимиты = квоты
RPM/TPM, не «остаток»). AI Studio free-tier остаток тоже не отдаёт по API.

- [x] U9a (P2) РЕАЛИЗОВАНО (PR #143): РАСХОД В $ + ПРОГНОЗ ПО БЮДЖЕТУ. config: PRICE_TEXT_IN/OUT_USD_PER_1M, PRICE_IMAGE_USD, MONTHLY_BUDGET_USD (+ в .env.example). db.get_stats считает cost_total_usd (in/out токены + картинки по прайсу), budget_usd, avg_cost_per_post, posts_left_est. Панель статистики (handlers/admin.py cb_adm_stats) показывает «💵 Расход AI $X из $BUDGET» и «📦 Осталось постов в бюджете ≈ N». Тест tests/test_stats.py. Историческое ТЗ:
      прайс Gemini 2.5 Flash ($/1M токенов text-in/out + image) в config
      (напр. PRICE_TEXT_IN_USD_PER_1M и т.д.); при каждом log_ai считать
      est_cost_usd = токены×прайс (сейчас 0). В get_stats: cost_total_usd,
      avg_cost_per_post. Новый .env MONTHLY_BUDGET_USD → панель:
      «истрачено $X из $BUDGET, осталось ≈ N постов при средней цене $Y».
      Это и есть «остаток лимита ÷ стоимость генерации» в реалистичном виде.
      Ограничение: прайс — константа в config, обновлять вручную при смене
      тарифов Google. Тест: расчёт cost по фикстурным ai_logs.
- [x] U9b РЕАЛИЗОВАНО (PR #149/#150): фактические расходы Google Cloud через BigQuery billing-экспорт. services/billing.py get_cloud_costs() (никогда не бросает исключений; BigQuery-клиент в to_thread). config: BILLING_DATASET, BILLING_TABLE_PREFIX, CLOUD_PROJECT. Панель статистики (cb_adm_stats) показывает «☁️ Факт Cloud» (или «Google ещё не наполнил данные» пока export пуст). Историческое ТЗ: РЕАЛЬНЫЙ БАЛАНС Google Cloud через Cloud Billing
      API: отдельный SDK google-cloud-billing, доп. IAM-роль сервисному
      аккаунту (billing.viewer), не через текущий ADC. Даёт фактические
      траты/бюджет проекта, а не оценку. Риск/объём подтвердить у владельца
      перед стартом. Пока считаем достаточным U9a.

## U10 — Onboarding: подписчик бота → приглашение в канал @SMOKTOLK [РЕАЛИЗОВАНО в smoktolk_bot]

Идея владельца: кто в будущем нажмёт /start у бота-подписки (проект-сосед
smoktolk_bot, /opt/smoktolk/bot) — автоматически «цепляется» к каналу.

ВАЖНОЕ ограничение Telegram (факт, не память): бот НЕ может насильно
подписать человека на канал. Легальный флоу — прислать при /start кнопку
с invite-ссылкой (createChatInviteLink, бот должен быть админом канала с
правом invite), человек подписывается сам в один тап. Массовое добавление
из списка = бан (см. отклонённую ранее задачу) — здесь НЕ применяем.

- [x] U10a РЕАЛИЗОВАНО (разведка smoktolk_bot): БД users — /opt/smoktolk/bot/db.py (таблица users, `get_user`/`create_user`). /start — handlers/start.py (`_start_common`). Канал @SMOKTOLK привязан через CHANNEL_URL. Всё уже на месте.
- [x] U10b РЕАЛИЗОВАНО в smoktolk_bot (handlers/start.py `_start_common`): при первом /start `get_user` → `create_user` (сохранение user в БД); повторный /start только `update_user_meta` — НЕ спамит (идемпотентно). Приветствие: welcome-баннер + дисклеймер. Inline-кнопка «📢 Наш канал @SMOKTOLK» (url=CHANNEL_URL) в keyboards.py. Проверка членства (getChatMember) не делалась — не требовалась.
- [x] U10c РЕАЛИЗОВАНО (частично): метрика заходов — `db.bump_daily('start_clicks')` на каждый /start + `bump_daily('new_users')` для новых (колонка `start_clicks` в `daily_stats`, миграция db.py). Видно в админ-панели adm_stats. Число реально подписавшихся на канал через бота Telegram не отдаёт (нет getChatMember-опроса) — метрика заходов признана достаточной.

Открытый вопрос владельцу: ЭТО ДРУГОЙ ПРОЕКТ (smoktolk_bot). Реализовывать
там, а не в SMOKI. SMOKI ведёт КАНАЛ, smoktolk_bot работает с подписчиками.
