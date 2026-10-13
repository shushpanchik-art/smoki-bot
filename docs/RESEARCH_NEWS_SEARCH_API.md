# Исследование: Интеграция API для улучшения поиска новостей

**Дата:** 13 октября 2026  
**Цель:** Оценить Vercel AI и Serper API для улучшения генерации новостного контента

---

## Текущее состояние

### Реализация в проекте

**Используется:** Google Search grounding через `google-genai` SDK

```python
# ai/gemini.py:98-106
tools: types.ToolListUnion | None = (
    [types.Tool(google_search=types.GoogleSearch())]
    if use_search else None
)
```

**Где применяется:**
- `services/content.py:193` — генерация статей (всегда `use_search=True`)
- `services/stories.py:94-156` — Stories (для тем: новости, технологии, история)

### Ограничения текущего решения

1. **Черный ящик** — нет контроля над:
   - Источниками поиска
   - Свежестью результатов
   - Фильтрацией по языку/региону
   - Приоритизацией новостных источников

2. **Нет метаданных** — модель получает результаты, но мы не видим:
   - Какие источники были использованы
   - Насколько свежие данные
   - Релевантность результатов

3. **Стоимость** — Google Search grounding оплачивается отдельно, но без детальной аналитики

---

## Альтернатива 1: Serper API

### Что это?

Google Search API с низкой задержкой и структурированными результатами.

**Ключевые возможности:**
- News Search endpoint — специализированный поиск новостей
- Актуальность: результаты за последние 24 часа
- Метаданные: дата публикации, источник, thumbnail
- Низкая задержка: ~500ms
- JSON структура для парсинга

### Стоимость

- **Free tier:** 2,500 поисков/месяц ($0)
- **Pro:** $50/месяц за 5,000 поисков ($0.01/запрос)
- **Ultra:** $225/месяц за 30,000 поисков ($0.0075/запрос)

**Текущая нагрузка проекта:**
- 2 статьи/день × 30 дней = 60 запросов/месяц
- Stories (замороженo) = 0 запросов
- **Итого:** ~60-100 запросов/месяц → Free tier достаточно

### Преимущества vs Google Search grounding

✅ **Контроль источников** — видим все найденные новости  
✅ **Фильтры** — по дате, языку, региону  
✅ **Прозрачность** — знаем откуда данные  
✅ **Стоимость** — Free tier покрывает текущую нагрузку  
✅ **Независимость** — не привязаны к Gemini grounding  

### Недостатки

❌ **Дополнительный API** — нужен отдельный ключ и обработка  
❌ **Интеграция в промпт** — нужно самостоятельно формировать контекст для Gemini  
❌ **Лишний шаг** — Serper → обработка → Gemini (вместо прямого grounding)  

### Код интеграции (пример)

```python
import httpx
import config

async def search_news(query: str, days: int = 7) -> list[dict]:
    """Поиск свежих новостей через Serper News API."""
    url = "https://google.serper.dev/news"
    headers = {
        "X-API-KEY": config.SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": 5,
        "tbs": f"qdr:d{days}",  # последние N дней
        "gl": "ru",  # регион
        "hl": "ru"   # язык
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
    # Парсим результаты
    news = []
    for item in data.get("news", []):
        news.append({
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "source": item.get("source"),
            "date": item.get("date"),
            "link": item.get("link")
        })
    return news

# Использование в services/content.py
async def generate_article_with_serper(topic: str) -> dict:
    # 1. Поиск актуальных новостей по теме
    news = await search_news(topic, days=7)
    
    # 2. Формирование контекста из новостей
    news_context = "\n\n".join([
        f"📰 {n['title']}\n{n['snippet']}\nИсточник: {n['source']}, {n['date']}"
        for n in news[:3]
    ])
    
    # 3. Генерация с обогащённым промптом
    enriched_prompt = (
        f"{prompts.article_prompt(topic)}\n\n"
        f"СВЕЖИЕ МАТЕРИАЛЫ ПО ТЕМЕ:\n{news_context}"
    )
    
    body_raw = await _text(enriched_prompt, use_search=False)
    # ... rest of generation
```

---

## Альтернатива 2: Vercel AI

### Что это?

**Vercel AI SDK** — TypeScript/JavaScript библиотека для AI-приложений.

**Важно:** Это не сервис для поиска новостей, а инструмент для:
- Унификации вызовов к разным LLM (OpenAI, Anthropic, Google, etc.)
- Streaming ответов
- Tool calling / function calling
- RAG (Retrieval-Augmented Generation)

### Применимость к проекту

❌ **Не подходит** для текущей задачи:
1. Проект на Python (Vercel AI SDK — TypeScript/JS)
2. Нет функционала поиска новостей (только обёртка над LLM)
3. Vercel Functions — для деплоя веб-приложений, не для Telegram ботов

**Вывод:** Vercel AI не решает задачу улучшения новостного поиска.

---

## Альтернатива 3: Улучшение текущего решения

### Подход: "Hybrid Search"

Комбинирование Google Search grounding + явный новостный поиск.

**Идея:**
1. Для **общих тем** — Google Search grounding (как сейчас)
2. Для **новостных тем** — Serper News API с метаданными
3. Для **технических тем** — Serper обычный поиск + GitHub Issues (через Kindly Web Search)

### Преимущества

✅ Сохраняем текущую работающую систему  
✅ Добавляем контроль только там, где нужно  
✅ Постепенная миграция без ломки  
✅ A/B тестирование: grounding vs Serper  

### Реализация

```python
# services/content.py

async def _smart_search_context(topic: str) -> str | None:
    """Умный выбор источника контекста по типу темы."""
    topic_lower = topic.lower()
    
    # Новостные триггеры
    news_keywords = ["новост", "событи", "произошл", "заявил", "объявил"]
    if any(kw in topic_lower for kw in news_keywords):
        news = await search_news(topic, days=3)
        if news:
            return "\n\n".join([
                f"• {n['title']} ({n['source']}, {n['date']})\n{n['snippet']}"
                for n in news[:3]
            ])
    
    # Для остальных — полагаемся на Google Search grounding
    return None


async def generate_article(topic: str, ...) -> dict:
    # ... existing code ...
    
    # Попытка получить явный контекст
    extra_context = await _smart_search_context(topic)
    
    if extra_context:
        # Генерация с явным контекстом, БЕЗ grounding
        enriched = f"{prompt}\n\nАКТУАЛЬНЫЕ МАТЕРИАЛЫ:\n{extra_context}"
        body_raw = await _text(enriched, use_search=False)
    else:
        # Генерация с Google Search grounding (как сейчас)
        body_raw = await _text(prompt, use_search=True)
```

---

## Рекомендации

### Краткосрочная перспектива (1-2 недели)

**Рекомендация:** Протестировать Serper API на новостных темах

**План:**
1. Регистрация на https://serper.dev (free tier)
2. Добавить `SERPER_API_KEY` в `.env`
3. Создать модуль `ai/search.py` с функциями Serper
4. Реализовать `_smart_search_context()` в `services/content.py`
5. A/B тест на 10 статьях: grounding vs Serper
6. Сравнить:
   - Релевантность новостей
   - Свежесть информации
   - Качество финальной статьи
   - Стоимость (Serper: $0, grounding: трафик GCP)

**Риски:** Низкие (free tier, не ломаем текущую систему)

### Среднесрочная перспектива (1-2 месяца)

**Рекомендация:** Hybrid search для разных типов контента

**Сценарии:**
- **Новости** → Serper News API (свежесть + источники)
- **Общие темы** → Google Search grounding (широкий охват)
- **Технические** → Kindly Web Search MCP (GitHub Issues, StackOverflow)

**Преимущества:**
- Лучшее качество для каждого типа контента
- Контроль над источниками
- Снижение стоимости grounding

### Долгосрочная перспектива (3+ месяца)

**Рекомендация:** RAG (Retrieval-Augmented Generation) с кэшированием

**Идея:**
1. Собственная база новостей по нише (вейпы, кальяны)
2. RSS-агрегация из проверенных источников
3. Векторный поиск (embedding) по базе
4. Генерация на основе своих данных + Serper для свежих событий

**Преимущества:**
- Независимость от внешних API
- Контроль качества источников
- Нулевая стоимость поиска (кроме хранения)

---

## Сравнительная таблица

| Критерий | Google Search grounding | Serper API | Vercel AI |
|----------|-------------------------|------------|-----------|
| **Актуальность новостей** | ⭐⭐⭐ (нет контроля) | ⭐⭐⭐⭐⭐ (фильтр по дате) | ❌ (нет поиска) |
| **Стоимость (текущая нагрузка)** | ~$5-10/мес (GCP traffic) | $0 (free tier) | N/A |
| **Прозрачность источников** | ❌ (черный ящик) | ✅ (видим всё) | N/A |
| **Простота интеграции** | ✅ (уже работает) | ⭐⭐⭐ (новый API) | ❌ (другой язык) |
| **Контроль качества** | ❌ | ✅ | N/A |
| **Фильтры (язык, регион)** | ❌ | ✅ | N/A |
| **Применимость к проекту** | ✅ Да | ✅ Да | ❌ Нет |

---

## Выводы

1. **Vercel AI** — не подходит (TypeScript SDK, нет функционала поиска новостей)

2. **Serper API** — перспективная замена/дополнение:
   - Free tier покрывает текущую нагрузку
   - Лучший контроль над новостными источниками
   - Простая интеграция через REST API
   - Подходит для Python проекта

3. **Рекомендация:** Hybrid подход
   - Новостные темы → Serper News API
   - Общие темы → Google Search grounding (текущее решение)
   - Постепенная миграция с A/B тестированием

4. **Первый шаг:** 
   - Зарегистрироваться на Serper.dev
   - Реализовать `ai/search.py` с News API
   - Протестировать на 5-10 новостных темах
   - Сравнить качество с текущим grounding

---

## Ссылки и ресурсы

- [Serper API Documentation](https://serper.dev/docs)
- [Kindly Web Search MCP Server](https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server) — 399⭐, production-ready
- [NyanNyanovich/nyan](https://github.com/NyanNyanovich/nyan) — 330⭐, Telegram news aggregator
- [Google Gemini Search grounding docs](https://ai.google.dev/gemini-api/docs/grounding)

---

**Статус:** Исследование завершено  
**Следующий шаг:** Ждём решения по прототипированию Serper интеграции
