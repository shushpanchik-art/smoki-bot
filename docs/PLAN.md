# Implementation Plan (PLAN)
## SMOKI-bot — План внедрения и развития

**Версия:** 1.0  
**Дата:** 13 октября 2026  
**Статус:** Production (MVP complete)  
**Связанные документы:** [PRD.md](PRD.md), [TRD.md](TRD.md), [DESIGN.md](DESIGN.md)

---

## 1. История проекта

### 1.1. Timeline (хронология)

| Дата | Milestone | Статус |
|------|-----------|--------|
| **2024-Q2** | Концепция и прототип | ✅ Complete |
| **2024-Q3** | MVP (генерация + модерация) | ✅ Complete |
| **2024-Q4** | Автоцензура + публикация | ✅ Complete |
| **2025-Q1** | Модерация комментариев | ✅ Complete |
| **2025-Q2** | Stories (beta) | ✅ Complete |
| **2025-Q3** | Saga (экспериментально) | ✅ Complete |
| **2025-Q4** | Рефакторинг + тесты | ✅ Complete |
| **2026-Q1** | Production stability | ✅ Complete |
| **2026-Q2** | Heartbeat monitoring | ✅ Complete |
| **2026-Q3** | Serper API integration | ✅ Complete (13 окт.) |
| **2026-Q4** | **Текущий этап** | 🔄 In Progress |

---

### 1.2. Ключевые вехи

#### MVP (2024-Q3)
**Цель:** Автоматическая генерация 2 постов/день с модерацией.

**Функции:**
- ✅ Генерация темы + текст (Gemini)
- ✅ Генерация картинки (Imagen)
- ✅ Модерация черновиков (5 кнопок)
- ✅ Публикация в канал
- ✅ Scheduler (утро/вечер)

**Результат:** Время администратора сокращено с 2-3 часов до 30 минут/день.

---

#### Автоцензура (2024-Q4)
**Цель:** Гарантия отсутствия нарушений в публикуемом контенте.

**Функции:**
- ✅ AI-проверка текста перед публикацией
- ✅ Автоматическая регенерация при нарушении
- ✅ Накопление правил цензуры
- ✅ Логирование всех проверок

**Результат:** 0 нарушений правил Telegram за 2 года работы.

---

#### Модерация комментариев (2025-Q1)
**Цель:** Автоматическая обработка комментариев в группе-обсуждении.

**Функции:**
- ✅ Классификация комментариев (5 классов)
- ✅ Удаление спама/токсичности
- ✅ AI-ответы на вопросы
- ✅ Scheduler (каждые 6 часов)

**Результат:** 100% спама удаляется автоматически, 0 жалоб на модерацию.

---

#### Serper API Integration (2026-Q3)
**Цель:** Улучшенный поиск новостей с метаданными и картинками.

**Функции:**
- ✅ Hybrid search (Serper для новостей, grounding для остального)
- ✅ Извлечение imageUrl из новостей
- ✅ Fallback на Google grounding
- ✅ Tests + documentation

**Результат:** Актуальные новости с источниками, картинки из новостных источников.

---

## 2. Текущее состояние (Q4 2026)

### 2.1. Production Metrics

| Метрика | Значение | Статус |
|---------|----------|--------|
| **Uptime** | 99.5% | ✅ Excellent |
| **Публикации/день** | 2.0 | ✅ Target met |
| **Время администратора** | 15-30 мин | ✅ Target met |
| **Успешность автоцензуры** | ~97% | ✅ Above target (>95%) |
| **Качество контента** | 0 нарушений | ✅ Perfect |
| **Генерация статьи** | 4.6 сек | ✅ Fast (<10 сек) |
| **AI budget** | $1.75/мес (прогноз) | ✅ Under budget ($10) |

---

### 2.2. Known Issues

**ISSUE-001: Длинные новостные посты без imageUrl**  
- Частота: <5% случаев  
- Workaround: AI-генерация картинки  
- Приоритет: Low  
- Статус: Won't fix (редко, не критично)

**ISSUE-002: Saga теряет контекст между эпизодами**  
- Частота: ~10% эпизодов  
- Workaround: Ручная корректировка `saga_state.recap`  
- Приоритет: Low  
- Статус: Known limitation (LLM context window)

---

## 3. Roadmap (будущее развитие)

### 3.1. Q4 2026 (Oct-Dec)

#### P1: A/B тест Serper vs Google grounding
**Цель:** Измерить качество новостей через Serper API vs встроенный grounding.

**Задачи:**
- [ ] Добавить метрику качества в `ai_logs` (rating 1-5)
- [ ] 2 недели A (только Serper) + 2 недели B (только grounding)
- [ ] Сравнить: актуальность, источники, качество текста
- [ ] Решение: оставить Serper или вернуться к grounding

**Effort:** 2 недели  
**Dependencies:** Serper API integration (✅ complete)

---

#### P2: Webhook вместо polling
**Цель:** Снизить latency и нагрузку на Telegram API.

**Задачи:**
- [ ] Настроить HTTPS endpoint на сервере (nginx)
- [ ] Переключить бота с polling на webhook
- [ ] Тестирование: latency, reliability
- [ ] Мониторинг: webhook errors

**Effort:** 1 неделя  
**Dependencies:** None

**Преимущества:**
- Latency: 0.5-1 сек (вместо 1-3 сек polling)
- CPU usage: -50% (нет constant polling)

---

#### P3: Prometheus metrics экспорт
**Цель:** Мониторинг метрик в Grafana.

**Задачи:**
- [ ] Добавить `prometheus_client` библиотеку
- [ ] Экспорт метрик: requests, latency, errors, AI calls
- [ ] Endpoint `/metrics` (HTTP)
- [ ] Grafana dashboard

**Effort:** 3 дня  
**Dependencies:** None

---

### 3.2. Q1 2027 (Jan-Mar)

#### P1: Мультиязычность (английский канал)
**Цель:** Запуск англоязычного канала с тем же ботом.

**Задачи:**
- [ ] Параметризация языка в config (`LANGUAGE=ru|en`)
- [ ] EN-версии промптов
- [ ] Отдельный канал: `@SMOKTOLK_EN`
- [ ] A/B тест аудитории

**Effort:** 2 недели  
**Dependencies:** None

**Риски:**
- Англоязычная аудитория может быть меньше
- Нужна отдельная модерация комментариев (2 группы)

---

#### P2: Telegram Mini App (аналитика для админа)
**Цель:** Web-интерфейс для статистики и управления.

**Задачи:**
- [ ] Mini App frontend (React + Telegram WebApp API)
- [ ] Backend API (FastAPI)
- [ ] Графики: публикации, комментарии, AI budget
- [ ] Управление: настройки длины, цензура, паузы

**Effort:** 4 недели  
**Dependencies:** None

**Преимущества:**
- Удобнее чем кнопки бота
- Графики и аналитика
- История публикаций

---

#### P3: Auto-download imageUrl
**Цель:** Скачивать и хранить imageUrl локально (не полагаться на внешние ссылки).

**Задачи:**
- [ ] Функция `download_image(url) -> local_path`
- [ ] Сохранение в `data/images/news_*.png`
- [ ] Fallback: если скачать не удалось → AI-генерация
- [ ] Cleanup: удаление старых картинок (>30 дней)

**Effort:** 2 дня  
**Dependencies:** Serper API integration

**Преимущества:**
- Надёжность: картинка не пропадёт если источник удалит
- Performance: локальная картинка быстрее

---

### 3.3. Q2 2027 (Apr-Jun)

#### P2: RSS-фид для подписчиков
**Цель:** Альтернативный способ подписки (не только Telegram).

**Задачи:**
- [ ] Генерация RSS XML из БД (`articles` table)
- [ ] HTTP endpoint `/rss.xml`
- [ ] Nginx: публичный доступ к `/rss.xml`
- [ ] Тестирование с RSS-читалками

**Effort:** 1 неделя  
**Dependencies:** None

---

#### P3: Экспорт статей в blog формат
**Цель:** Автоматическая публикация статей на блог (SEO).

**Задачи:**
- [ ] Интеграция с Ghost/WordPress API
- [ ] Автоматический экспорт после публикации в канале
- [ ] Конвертация HTML → Markdown (для Ghost)
- [ ] Мониторинг: успешность публикации

**Effort:** 2 недели  
**Dependencies:** None

---

### 3.4. Backlog (низкий приоритет)

**Отклонённые идеи:**
- ❌ Ручное редактирование текста через бота (сложно, низкий приоритет)
- ❌ Интеграция с другими соцсетями (фокус на Telegram)
- ❌ Платная подписка (не соответствует модели канала)

**Идеи для будущего:**
- 💡 AI-голос для Stories (озвучка текста)
- 💡 Personalization: разные стили для разных подписчиков
- 💡 Collaborative features: админы могут комментировать черновики
- 💡 Analytics API: экспорт метрик для внешних систем

---

## 4. Технический долг

### 4.1. Code Quality

| Item | Приоритет | Effort | Status |
|------|-----------|--------|--------|
| **Increase test coverage to 60%** | P1 | 2 недели | 🔄 Planned Q4 2026 |
| **Refactor scheduler.py (too long)** | P2 | 3 дня | 📋 Backlog |
| **Type hints coverage 100%** | P2 | 1 неделя | 📋 Backlog |
| **Move prompts to YAML files** | P3 | 2 дня | 📋 Backlog |
| **Reduce cyclomatic complexity** | P3 | 1 неделя | 📋 Backlog |

---

### 4.2. Infrastructure

| Item | Приоритет | Effort | Status |
|------|-----------|--------|--------|
| **CI/CD: auto-deploy on merge** | P1 | 1 неделя | 🔄 Planned Q1 2027 |
| **Docker containerization** | P2 | 3 дня | 📋 Backlog |
| **PostgreSQL migration** | P3 | 2 недели | 📋 Only if 100x growth |
| **Redis caching layer** | P3 | 1 неделя | 📋 Only if needed |

---

### 4.3. Documentation

| Item | Приоритет | Effort | Status |
|------|-----------|--------|--------|
| **API documentation (OpenAPI)** | P2 | 2 дня | 📋 Backlog |
| **Runbook for incidents** | P1 | 3 дня | 🔄 Planned Q4 2026 |
| **Architecture diagrams (Mermaid)** | P2 | 1 день | ✅ Done (DESIGN.md) |
| **Video tutorial for admins** | P3 | 1 неделя | 📋 Backlog |

---

## 5. Dependencies & Risks

### 5.1. External Dependencies

| Dependency | Risk | Mitigation | Status |
|------------|------|------------|--------|
| **Telegram Bot API** | Критическая зависимость | Резервный бот-токен | ✅ Stable |
| **Google Vertex AI** | Высокий риск (стоимость, доступность) | Fallback на AI Studio | ✅ Stable |
| **Serper News API** | Низкий риск (free tier) | Fallback на grounding | ✅ Stable |
| **GCP Infrastructure** | Средний риск (стоимость) | Migration plan to cheaper provider | ✅ Stable |

---

### 5.2. Technical Risks

**RISK-001: SQLite concurrent writes bottleneck**  
- Вероятность: Низкая (только при 100x росте)  
- Влияние: Высокое (SQLITE_BUSY errors)  
- Митигация: PostgreSQL migration plan готов  
- Триггер: >100 записей/сек

**RISK-002: Telegram API rate limits**  
- Вероятность: Средняя (при росте аудитории)  
- Влияние: Среднее (задержка публикаций)  
- Митигация: Message queue (Celery)  
- Триггер: >30 msg/сек в канал

**RISK-003: AI budget overrun**  
- Вероятность: Низкая (текущий расход $1.75/мес)  
- Влияние: Среднее (нужно увеличить бюджет)  
- Митигация: Alert при >80% бюджета  
- Триггер: Unexpected usage spike

**RISK-004: Vertex AI policy changes**  
- Вероятность: Низкая  
- Влияние: Критическое (нет генерации)  
- Митигация: Fallback на AI Studio + alternative providers  
- Триггер: Breaking API changes

---

## 6. Release Process

### 6.1. Development Workflow

```
[Feature branch]
       ↓
[Local testing + unit tests]
       ↓
[Pull request]
       ↓
[CI: lint + typecheck + tests + security]
       ↓
[Code review] (optional, solo dev)
       ↓
[Merge to main]
       ↓
[Manual deploy to production]
       ↓
[Smoke tests]
       ↓
[Monitor logs 24h]
```

---

### 6.2. Deployment Steps

**Текущий процесс (manual):**

```bash
# 1. SSH на сервер
gcloud compute ssh telegram-bot --zone=us-central1-c

# 2. Switch user
sudo -u shushpanchik_art -s

# 3. Pull changes
cd /opt/SMOKI/bot
git pull origin main

# 4. Install dependencies (если изменились)
venv/bin/pip install -r requirements.txt

# 5. Restart service
sudo systemctl restart smoki-bot

# 6. Check logs
journalctl -u smoki-bot -f -n 50
```

**Planned (CI/CD, Q1 2027):**

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to production
        run: |
          gcloud compute ssh telegram-bot --command="
            cd /opt/SMOKI/bot && 
            git pull && 
            venv/bin/pip install -r requirements.txt && 
            sudo systemctl restart smoki-bot
          "
```

---

### 6.3. Rollback Procedure

**Когда:** Критическая ошибка в production после деплоя.

**Шаги:**
```bash
# 1. SSH на сервер
gcloud compute ssh telegram-bot

# 2. Switch user
sudo -u shushpanchik_art -s

# 3. Rollback к предыдущему commit
cd /opt/SMOKI/bot
git log --oneline -5  # Найти последний рабочий commit
git reset --hard <commit-hash>

# 4. Restart service
sudo systemctl restart smoki-bot

# 5. Verify
journalctl -u smoki-bot -n 50
```

**RTO:** <5 минут  
**Notification:** Алерт админу в Telegram

---

## 7. Testing Strategy

### 7.1. Unit Tests

**Coverage:** 45% (requirement), 60% (target Q4 2026)

**Framework:** pytest + pytest-asyncio

**Modules:**
- `tests/test_content.py` — генерация контента
- `tests/test_censor.py` — автоцензура
- `tests/test_search.py` — Serper API
- `tests/test_comments.py` — модерация комментариев
- `tests/test_publisher.py` — публикация
- `tests/test_env_example.py` — валидация config

**Mocking:**
- Все API вызовы мокируются (`MagicMock`, `AsyncMock`)
- Нет реальных HTTP запросов
- БД: in-memory SQLite (`:memory:`)

---

### 7.2. Integration Tests

**Smoke tests** (manual, после каждого деплоя):

```bash
# 1. Генерация утреннего поста
/generate_morning

# 2. Модерация
[Нажать кнопки: регенерация, публикация]

# 3. Проверка в канале
[Открыть @SMOKTOLK, найти пост]

# 4. Комментарий
[Написать тестовый комментарий, дождаться обработки]

# 5. Heartbeat
journalctl -u smoki-bot | grep HEARTBEAT | tail -1
```

**Автоматизация:** Planned Q1 2027 (Playwright для UI тестов)

---

### 7.3. Load Testing

**Текущая нагрузка:** 2 поста/день + 10-50 комментариев/неделю

**Load test scenario (не запускался):**
- 100 постов/день (50x)
- 500 комментариев/день (100x)
- Измерить: latency, errors, resource usage

**Когда:** Перед масштабированием (если аудитория растёт 10x)

---

## 8. Monitoring & Alerts

### 8.1. Current Monitoring

**Heartbeat:**
- Частота: каждые 4 часа
- Проверка: каждый час (systemd timer)
- Алерт: если нет >8 часов → Telegram alert админу

**Delivery Watchdog:**
- Проверка: PUBLISH_WINDOW_END + 2 часа
- Алерт: если статьи не доставлены → Telegram alert

**AI Budget:**
- Проверка: команда `/stats`
- Алерт: если >80% бюджета → предупреждение в `/stats`

---

### 8.2. Planned Monitoring (Q4 2026)

**Prometheus + Grafana:**
- Метрики: requests, latency, errors, AI calls, budget
- Алерты: email/Telegram при критических метриках
- Дашборд: real-time мониторинг

**Healthcheck endpoint:**
- `/health` (HTTP) — status: ok/degraded/down
- Проверка: БД доступна, scheduler работает, heartbeat fresh

---

## 9. Success Criteria

### 9.1. MVP Success Criteria (✅ Achieved)

- ✅ 2 поста/день публикуются автоматически
- ✅ Время администратора <30 мин/день
- ✅ 0 нарушений правил Telegram
- ✅ Uptime >99%
- ✅ AI budget <$10/мес

---

### 9.2. Q4 2026 Goals

| Goal | Target | Current | Status |
|------|--------|---------|--------|
| **Test coverage** | 60% | 45% | 🔄 In Progress |
| **Webhook latency** | <1 сек | 1-3 сек (polling) | 📋 Planned |
| **Prometheus metrics** | Live | Manual logs | 📋 Planned |

---

### 9.3. Q1 2027 Goals

| Goal | Target | Current | Status |
|------|--------|---------|--------|
| **English channel** | Live | N/A | 📋 Planned |
| **Mini App** | Live | N/A | 📋 Planned |
| **CI/CD** | Auto-deploy | Manual | 📋 Planned |

---

## 10. Team & Resources

### 10.1. Current Team

**Solo Developer:** @shushpanchik_art (owner + developer + admin)

**Roles:**
- Product owner: @shushpanchik_art
- Developer: @shushpanchik_art
- Admin (content moderator): @shushpanchik_art

**Time allocation:**
- Development: ~5 часов/неделя (new features)
- Maintenance: ~2 часа/месяц (monitoring, fixes)
- Content moderation: 15-30 мин/день (черновики)

---

### 10.2. Infrastructure Costs

| Item | Cost/month | Annual |
|------|------------|--------|
| **GCP e2-micro instance** | $7 | $84 |
| **AI (Gemini + Imagen)** | $1.75 (avg) | $21 |
| **Serper API** | $0 (free tier) | $0 |
| **Domain (optional)** | $0 | $0 |
| **Total** | **$8.75** | **$105** |

**Budget:** $10/мес (комфортный запас)

---

## 11. Lessons Learned

### 11.1. What Went Well

✅ **Автоцензура спасает от нарушений**  
- 0 нарушений за 2 года работы
- Автоматическая регенерация работает

✅ **Hybrid search (Serper API) улучшил новости**  
- Актуальные источники
- Картинки из новостей
- Fallback на grounding при ошибках

✅ **Heartbeat monitoring ловит зависания**  
- 2 случая зависания обнаружены вовремя
- Админ узнал о проблеме за 30 минут

✅ **Модерация комментариев экономит время**  
- 100% спама удаляется автоматически
- AI-ответы на вопросы качественные

---

### 11.2. What Could Be Improved

⚠️ **F-strings в gcloud heredoc — частая ошибка**  
- Решение: документировано в SPEC.md, PROJECT_BOOK
- Будущее: pre-commit hook для проверки

⚠️ **Длинные утренние посты (без length_hint)**  
- Решение: всегда передавать `length_hint=prompts.facts_rules(n)`
- Будущее: unit тест на длину постов

⚠️ **Saga теряет контекст между эпизодами**  
- Решение: известное ограничение LLM
- Будущее: RAG (Retrieval-Augmented Generation) для саги

⚠️ **Manual deploy — медленно и рискованно**  
- Решение: CI/CD (planned Q1 2027)

---

## 12. Документация

**См. также:**
- [PRD.md](PRD.md) — продуктовые требования
- [TRD.md](TRD.md) — технические требования
- [FLOW.md](FLOW.md) — пользовательские сценарии
- [DESIGN.md](DESIGN.md) — архитектура системы
- [DB.md](DB.md) — схема базы данных
- [SPEC.md](SPEC.md) — спецификация для разработчиков
- [PROJECT_BOOK.md](PROJECT_BOOK.md) — полная книга проекта

---

**Версия:** 1.0 (13 октября 2026)  
**Контакт:** @shushpanchik_art  
**Лицензия:** Proprietary
