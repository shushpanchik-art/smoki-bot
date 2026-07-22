"""U9b: фактические расходы Google Cloud из BigQuery billing-экспорта.

Единственная публичная функция get_cloud_costs() никогда не бросает
исключений: при любой проблеме (не настроено, таблицы нет, ошибка BigQuery)
возвращает {"available": False, "reason": "..."}. Бот не должен падать.

BigQuery-клиент синхронный, поэтому запросы выполняются в отдельном потоке
через asyncio.to_thread, чтобы не блокировать event loop aiogram.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)


def _sync_fetch() -> dict:
    """Синхронная работа с BigQuery. Выполняется в to_thread."""
    project = (config.GOOGLE_CLOUD_PROJECT or "").strip()
    dataset = (config.BILLING_DATASET or "").strip()
    prefix = (config.BILLING_TABLE_PREFIX or "").strip()

    if not project or not dataset:
        return {"available": False, "reason": "не настроено (нет проекта/датасета)"}

    # Импорт внутри функции: если пакет не установлен — не роняем весь модуль.
    from google.cloud import bigquery  # type: ignore[attr-defined]

    client = bigquery.Client(project=project)

    # 1) Ищем таблицу billing-экспорта по префиксу.
    dataset_ref = f"{project}.{dataset}"
    table_id = None
    for tbl in client.list_tables(dataset_ref):
        if tbl.table_id.startswith(prefix):
            table_id = tbl.table_id
            break

    if table_id is None:
        return {
            "available": False,
            "reason": "Google ещё не наполнил данные (появятся в течение суток)",
        }

    full_table = f"`{project}.{dataset}.{table_id}`"

    # 2) Сумма затрат за текущий календарный месяц (UTC).
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    query = f"""
        SELECT
            IFNULL(SUM(cost), 0.0) AS month_cost,
            ANY_VALUE(currency) AS currency
        FROM {full_table}
        WHERE usage_start_time >= @month_start
    """  # noqa: S608  (идентификаторы из config, значение через параметр)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "month_start", "TIMESTAMP", month_start
            )
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    if not rows:
        return {
            "available": True,
            "month_cost": 0.0,
            "currency": "USD",
            "month": now.strftime("%Y-%m"),
            "budget": config.MONTHLY_BUDGET_USD,
        }

    row = rows[0]
    month_cost = float(row["month_cost"] or 0.0)
    currency = row["currency"] or "USD"
    return {
        "available": True,
        "month_cost": month_cost,
        "currency": currency,
        "month": now.strftime("%Y-%m"),
        "budget": config.MONTHLY_BUDGET_USD,
    }


async def get_cloud_costs() -> dict:
    """Публичная точка входа. Никогда не бросает исключений."""
    try:
        return await asyncio.to_thread(_sync_fetch)
    except Exception as e:  # noqa: BLE001 (нужно поймать всё — бот не падает)
        logger.warning("billing: не удалось получить данные BigQuery: %s", e)
        return {"available": False, "reason": f"ошибка BigQuery: {type(e).__name__}"}
