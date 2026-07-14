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
- Дедлайн-джоба `_job_deadline` запускается ДВАЖДЫ: в PUBLISH_WINDOW_END и в EVENING_DEADLINE_HOUR:EVENING_DEADLINE_MINUTE (деф. 20:30 MSK). Публикует ВСЕ зависшие статьи дня (get_undelivered_today → pending/approved за сегодня), затем шлёт админу сводку опубликованных/неудачных.
- Предпросмотр (U2): за PREVIEW_WARN_MINUTES мин (деф. 15) до каждого дедлайна джоба `_job_preview_warn` (`preview_warn_day`/`preview_warn_evening`) шлёт админу список зависших #id статей, которые скоро уйдут автоматически. Отдельного namespace кнопок нет — управление через существующие ✅ Опубликовать / ⛔ Отмена под самими черновиками. Если зависших статей нет — пропуск.
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
- docs (SPEC.md, TESTING.md, PROJECT_BOOK.txt)

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

- __Беспарольный рестарт__: настроен sudoers drop-in `/etc/sudoers.d/smoki-bot`
  (по образцу `smoktolk-bot`). Разрешены без пароля: `systemctl restart/start/stop/status smoki-bot`.
  Проверка синтаксиса перед активацией обязательна: `sudo visudo -c`.
  Тест: `sudo -n systemctl restart smoki-bot` (флаг `-n` = не спрашивать пароль).
- __Чистка веток-зомби__: смёрженные локальные ветки удалять `git branch -d <name>`;
  устаревшие remote-tracking refs — `git remote prune origin`.
  После merge PR через UI удалённая ветка на GitHub исчезает, локально остаётся зомби.
- __Кэш байткода__: каталоги `__pycache__` покрыты `.gitignore`, git их не видит; периодически чистить
  `find . -path ./venv -prune -o -name __pycache__ -type d -exec rm -rf {} +`.
- __journalctl__: для свежих логов после рестарта надёжнее `--since` по времени,
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
  (IntervalTrigger каждые HEARTBEAT_INTERVAL_HOURS=6 ч, id="heartbeat",
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
- [x] U5 (P2) Image-prompt из ТЕКСТА статьи. РЕАЛИЗОВАНО (feature/u5-image-scene-from-text): в services/content.generate_article после цензуры шаг ИИ (_text(prompts.image_scene_prompt(body))) генерит EN-описание сцены по телу статьи, оно идёт в prompts.image_prompt_from_scene(scene, topic); фолбэк на prompts.image_prompt(topic) при пустом ответе/ошибке. Constraints (NO TEXT, 3:2) сохранены. Тест tests/test_image_scene.py. Историческое описание проблемы: Проблема (прод, скриншоты):
  картинки однотипны — `prompts.image_prompt(topic)` строит сцену
  детерминированно (hash темы -> _IMG_SCENES/_IMG_PALETTES), поэтому
  одинаковая/близкая тема -> одинаковая картинка, тем немного -> повтор.
  Фикс: после цензуры (services/content.py, до блока img_prompt=...) шаг
  ИИ генерит краткое EN-описание сцены по телу статьи `body`
  (новый prompts.image_scene_from_text(body) + gemini.generate_text,
  use_search=False); описание подставляется в image_prompt вместо
  hash-сцены/topic. Жёсткие constraints (NO TEXT, 3:2, fill frame, no logos)
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
