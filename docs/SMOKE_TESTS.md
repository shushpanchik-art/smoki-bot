# Smoke-тестирование SMOKI Bot

## Описание

Smoke-тесты проверяют работоспособность основных компонентов бота без запуска полного тестового suite.

## Что проверяется

1. **Конфигурация** — наличие всех обязательных переменных окружения
2. **База данных** — подключение и структура таблиц
3. **Gemini AI** — работоспособность генерации текста
4. **Serper API** — доступность новостного поиска (опционально)
5. **Telegram API** — подключение к боту
6. **Systemd** — статус служб на сервере

## Запуск

### Локально (с полной конфигурацией)

```bash
cd /path/to/SMOKI-git
python3 tests/smoke_test.py
```

### На сервере

```bash
cd /opt/SMOKI/bot
source venv/bin/activate
python3 tests/smoke_test.py
```

### Через systemd timer (периодическая проверка)

```bash
# Копирование юнитов
sudo cp deploy/systemd/smoki-smoke-test.service /etc/systemd/system/
sudo cp deploy/systemd/smoki-smoke-test.timer /etc/systemd/system/

# Активация
sudo systemctl daemon-reload
sudo systemctl enable smoki-smoke-test.timer
sudo systemctl start smoki-smoke-test.timer

# Проверка статуса
sudo systemctl status smoki-smoke-test.timer
sudo journalctl -u smoki-smoke-test.service -n 50
```

## Интерпретация результатов

### Exit codes
- `0` — все тесты прошли
- `1` — один или более тестов провалились

### Статусы
- ✅ — тест пройден
- ❌ — критическая ошибка (требует внимания)
- ⚠️ — предупреждение (не критично)
- ⊘ — тест пропущен (не применим)

## Примеры вывода

### Успешный запуск
```
======================================================================
SMOKE-ТЕСТИРОВАНИЕ SMOKI BOT
======================================================================

[1/6] Проверка конфигурации...
  ✅ BOT_TOKEN
  ✅ CHANNEL_ID
  ✅ GEMINI_API_KEY or Vertex
  ✅ DB_PATH
  ✅ IMAGE_DIR
  ✅ SERPER_API_KEY (optional)

[2/6] Проверка базы данных...
  ✅ Подключение к БД (найдено 142 использованных тем)
  ✅ Таблица settings (12 записей)

[3/6] Проверка Gemini AI...
  ✅ Gemini ответил: 'тест'

[4/6] Проверка Serper API...
  ✅ Serper вернул 8 новостей

[5/6] Проверка Telegram API...
  ✅ Бот подключен: @smoki_content_bot (ID: 7947562246)

[6/6] Проверка systemd служб...
  ✅ smoki-bot.service: active

======================================================================
РЕЗУЛЬТАТЫ SMOKE-ТЕСТОВ
======================================================================
  ✅ config
  ✅ database
  ✅ gemini
  ✅ serper
  ✅ telegram
  ✅ systemd

Пройдено: 6/6

🎉 Все smoke-тесты прошли успешно!
```

### Локальный запуск (без полной конфигурации)
```
Пройдено: 2/6
⚠️ Некоторые тесты провалились. Проверьте конфигурацию.
```
Это нормально для локального окружения без `.env` файла.

## Автоматизация

Рекомендуется запускать smoke-тесты:
- После каждого деплоя на сервер
- Периодически (через systemd timer, например раз в час)
- В CI/CD pipeline (с мок-конфигурацией)

## Troubleshooting

### Ошибка: "no such table: published_topics"
База данных не инициализирована. Запустите бота один раз для создания структуры.

### Ошибка: "No API key was provided"
Не установлен `GEMINI_API_KEY` или `GOOGLE_GENAI_USE_VERTEXAI=true`. Проверьте `.env`.

### Ошибка: "Serper API недоступен"
Не критично — бот использует Google Search grounding как fallback.

### Ошибка: "BOT_TOKEN не задан"
Критично — бот не сможет подключиться к Telegram. Проверьте `.env`.
