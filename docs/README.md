# SMOKI-bot — Документация

**Версия:** 2.0  
**Дата:** 13 октября 2026

Добро пожаловать в документацию SMOKI-bot — AI-powered системы автоматизации Telegram-канала [@SMOKTOLK](https://t.me/smoktolk).

---

## 📚 Навигация по документам

### Для продакт-менеджеров и владельцев продукта

- **[PRD.md](PRD.md)** — Product Requirements Document  
  Что делает бот, какие проблемы решает, ключевые фичи, метрики успеха, roadmap

- **[FLOW.md](FLOW.md)** — User Flow Document  
  Путь пользователя: что видит администратор, как работает модерация, subscriber experience

### Для разработчиков

- **[SPEC.md](SPEC.md)** — Developer Specification ⭐  
  **Начните здесь!** Практическое руководство: quick start, SSH доступ, локальная разработка, CI/CD, troubleshooting

- **[TRD.md](TRD.md)** — Technical Requirements Document  
  Функциональные требования (R-GEN-001...), NFR, интеграции (Gemini, Serper, Telegram)

- **[DESIGN.md](DESIGN.md)** — System Design Document  
  Архитектура: компоненты, data flow, security, deployment, scaling

- **[DB.md](DB.md)** — Database Design Document  
  Схема БД, все таблицы, индексы, миграции, backup/recovery

### Для тимлидов и архитекторов

- **[PLAN.md](PLAN.md)** — Implementation Plan  
  Timeline, completed milestones, roadmap (Q4 2026 — Q2 2027), technical debt, risk analysis

- **[PROJECT_BOOK.md](PROJECT_BOOK.md)** — Project Book  
  История проекта (2024-2026), выученные уроки, контекст решений, метрики успеха

---

## 🚀 Quick Start

Если вы **новый разработчик в проекте**, следуйте этой последовательности:

1. **[PRD.md](PRD.md)** — поймите что делает продукт (10 мин)
2. **[SPEC.md](SPEC.md)** — настройте окружение и запустите бота локально (30 мин)
3. **[DESIGN.md](DESIGN.md)** — изучите архитектуру (20 мин)
4. **[DB.md](DB.md)** — разберитесь со схемой БД (15 мин)

Если вы **product manager или stakeholder**:
- Читайте [PRD.md](PRD.md) → [FLOW.md](FLOW.md) → [PLAN.md](PLAN.md)

Если вы **новый админ канала**:
- Читайте [FLOW.md](FLOW.md) — там описан ваш ежедневный workflow

---

## 📖 Описание документов

### [PRD.md](PRD.md) — Product Requirements Document
**Размер:** ~275 строк  
**Для кого:** PM, stakeholders, новые члены команды

**Содержание:**
- Обзор продукта и целевые пользователи
- 9 ключевых фич (F1-F9) с приоритетами P0-P2
- Метрики успеха (публикации/день, время админа, uptime)
- User stories (администратор, подписчик)
- Ограничения и non-goals
- Roadmap на 2026-2027

---

### [TRD.md](TRD.md) — Technical Requirements Document
**Размер:** ~575 строк  
**Для кого:** Разработчики, QA, архитекторы

**Содержание:**
- Tech stack: Python 3.11, aiogram 3.x, SQLite, APScheduler, Google Gemini, Serper API
- 20+ функциональных требований (R-GEN-001 через R-COM-001)
- NFR: производительность, безопасность, масштабируемость
- Интеграции: API endpoints, rate limits, error handling

**Ключевые разделы:**
- R-GEN: Генерация контента (hybrid search, autocensor, image generation)
- R-MOD: Модерация (5-button approval, deadline auto-publish)
- R-SCH: Расписание (cron, timezone, manual trigger)
- R-COM: Модерация комментариев (AI classification, auto-delete spam)

---

### [FLOW.md](FLOW.md) — User Flow Document
**Размер:** ~460 строк  
**Для кого:** PM, UX designers, новые админы

**Содержание:**
- Ежедневный workflow администратора
- Утренний пост (08:00-10:00): генерация → модерация → публикация
- Вечерний пост (19:00-20:30): тот же flow
- 5 кнопок модерации: ✅ Опубликовать / 🔄 Регенерировать текст / 🖼 Регенерировать картинку / 📝 Редактировать / ⛔ Отмена
- Subscriber experience: что видят подписчики vs что происходит под капотом
- Edge cases: пропущенный deadline, ошибки генерации, отсутствие admin

---

### [DESIGN.md](DESIGN.md) — System Design Document
**Размер:** ~750 строк  
**Для кого:** Разработчики, архитекторы, DevOps

**Содержание:**
- High-level архитектура (ASCII diagram)
- 6 слоёв: Bot Core, Handlers, Services, AI Layer, Database, Scheduler
- Data flow diagrams: morning post generation, deadline auto-publish, comment moderation
- Компоненты: services/content.py, ai/gemini.py, scheduler.py, db/
- Security: authentication (Workload Identity), content safety (autocensor), data protection
- Deployment: GCP Compute Engine, systemd, monitoring (heartbeat)

**Ключевые диаграммы:**
- Morning post generation flow (10 шагов)
- Deadline auto-publish flow (проверка каждые 5 минут)
- Comment moderation flow (сбор → классификация → действие)

---

### [DB.md](DB.md) — Database Design Document
**Размер:** ~650 строк  
**Для кого:** Разработчики, DBA

**Содержание:**
- 8 таблиц: published_topics, articles, comments, ai_logs, settings, story_jobs, saga_state, saga_summaries
- Полная схема с описанием каждого поля и constraint
- Индексы для оптимизации запросов
- Примеры SQL queries (CRUD операции)
- Миграции: schema changes, data migrations
- Backup/recovery: процедуры, расписание, restore

**Ключевые таблицы:**
- `published_topics` — хранит темы для избежания повторов (90 дней)
- `articles` — черновики и опубликованные статьи (status, deadline, auto_publish)
- `comments` — модерация комментариев (category: reklama/toxic/question/neutral/positive)
- `ai_logs` — аудит всех AI запросов (prompt, response, metadata)

---

### [PLAN.md](PLAN.md) — Implementation Plan
**Размер:** ~570 строк  
**Для кого:** Тимлиды, PM, stakeholders

**Содержание:**
- Timeline: 2024-Q2 (концепция) → 2027+ (roadmap)
- Completed milestones: MVP, Autocensor, Comment moderation, Serper integration
- Current status (октябрь 2026): production, 2 posts/day, 99.5% uptime
- Roadmap:
  - Q4 2026: A/B test Serper vs grounding, Webhook, Prometheus
  - Q1 2027: Multilang, Telegram Mini App, CI/CD
  - Q2 2027: RSS feed, Blog export
- Technical debt tracking: 5 items (refactor scheduler, migrate to PostgreSQL, etc.)
- Risk analysis: 6 risks + mitigation strategies

---

### [SPEC.md](SPEC.md) — Developer Specification ⭐
**Размер:** ~400 строк (было 68KB в версии 1.0)  
**Для кого:** Разработчики (главный документ для разработки)

**Содержание:**
- **Quick start:** клонирование → setup → запуск за 10 минут
- **Infrastructure:** GCP project, Compute Engine VM, systemd service
- **SSH доступ:** для человека и для AI (heredoc patterns, safety)
- **Локальная разработка:** requirements, env setup, database init
- **CI/CD:** GitHub Actions (10 jobs), linters, tests, coverage
- **Configuration:** все env переменные с описанием и примерами
- **Troubleshooting:** 10+ типичных проблем и решений
- **Monitoring:** heartbeat, systemd logs, journalctl commands

**Ключевые фичи:**
- Кросс-ссылки на все специализированные документы
- Минимум дублирования (детали вынесены в PRD/TRD/DESIGN/DB)
- Практический фокус: как запустить, как дебажить, как деплоить

---

### [PROJECT_BOOK.md](PROJECT_BOOK.md) — Project Book
**Размер:** ~400 строк  
**Для кого:** Все (история и контекст)

**Содержание:**
- **История:** от концепции (2024-Q2) до production (2026-Q3)
- **Выученные уроки:**
  - Автоцензура — must have (0 нарушений за 2 года)
  - F-strings в gcloud heredoc — частая ошибка
  - Утренний пост без length_hint — проблема
  - Heartbeat monitoring ловит зависания
  - Serper imageUrl улучшает новости
- **Ключевые решения:**
  - Почему SQLite, а не PostgreSQL?
  - Почему Gemini, а не GPT-4?
  - Почему 5 кнопок модерации?
  - Почему автопубликация по дедлайну?
- **Метрики успеха:** продуктовые и технические (октябрь 2026)
- **Команда и ресурсы:** solo developer, time allocation, infrastructure costs

---

## 🔗 Связи между документами

```
PRD.md (что) ──┬──> FLOW.md (как видит пользователь)
               ├──> TRD.md (технические требования)
               └──> PLAN.md (roadmap)

TRD.md (требования) ──> DESIGN.md (как реализовано)

DESIGN.md (архитектура) ──┬──> DB.md (схема БД)
                          └──> SPEC.md (как запустить)

SPEC.md (dev guide) ──> все остальные документы (ссылки в тексте)

PROJECT_BOOK.md (контекст) ──> все документы (история решений)
```

---

## 📝 История версий

### Версия 2.0 (13 октября 2026)
- Создана новая структура документации (PRD, TRD, FLOW, DESIGN, DB, PLAN, PROJECT_BOOK)
- SPEC.md рефакторинг: 68KB → 15KB, удалено дублирование
- Добавлены кросс-ссылки между документами
- PROJECT_BOOK.txt конвертирован в PROJECT_BOOK.md
- Создан этот README.md

### Версия 1.0 (до октября 2026)
- Монолитный SPEC.md (68KB)
- PROJECT_BOOK.txt (81KB)
- WORKLOG.md (устаревший)

---

## 🛠️ Maintenance

**Кто обновляет:**
- **PRD.md, FLOW.md, PLAN.md** — Product Manager
- **TRD.md, DESIGN.md, DB.md** — Lead Developer
- **SPEC.md** — любой разработчик (практические гайды)
- **PROJECT_BOOK.md** — Lead Developer (lessons learned после инцидентов)

**Когда обновляять:**
- **PRD/PLAN** — при изменении roadmap или добавлении фич
- **TRD** — при добавлении новых требований или интеграций
- **DESIGN** — при архитектурных изменениях
- **DB** — при изменении схемы (сразу после миграции)
- **SPEC** — при изменении инфраструктуры, CI/CD или troubleshooting
- **PROJECT_BOOK** — после инцидентов, релизов или важных решений

---

## 📞 Контакты

**Владелец проекта:** @shushpanchik_art  
**Канал:** [@SMOKTOLK](https://t.me/smoktolk)  
**Репозиторий:** Private (GCP Source Repositories)

---

**Последнее обновление:** 13 октября 2026  
**Версия документации:** 2.0
