"""Сервис саги: генерация эпизода, парсинг meta, продвижение состояния.

Ядро конвейера. НЕ публикует (это делает publisher/scheduler) — только
возвращает готовый текст эпизода и обновляет saga_state/saga_summaries.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from ai import gemini, prompts
from db import database as db

logger = logging.getLogger(__name__)

# Порог принудительного финала: если эпизод в арке дошёл до этого номера,
# просим модель закрыть арку (arc_status=completed).
FORCE_FINALE_AT = 8
DEFAULT_ARC_LENGTH = 6
META_MARK = "===META==="


# ---------------------------------------------------------------- генерация
async def _text(prompt: str, **kw) -> str:
    out = await asyncio.to_thread(gemini.generate_text, prompt, **kw)
    try:
        import config
        await db.log_ai("text", config.GEMINI_TEXT_MODEL,
                        input_tokens=len(prompt) // 4,
                        output_tokens=len(out) // 4)
    except Exception:
        logger.exception("log_ai saga")
    return out


def _should_force_finale(state: dict | None) -> bool:
    if not state:
        return False
    planned = int(state.get("planned_arc_length") or DEFAULT_ARC_LENGTH)
    in_arc = int(state.get("episode_in_arc") or 0)
    # финал если дошли до плановой длины арки ИЛИ упёрлись в жёсткий потолок
    return in_arc >= planned - 1 or in_arc >= FORCE_FINALE_AT


async def generate_episode() -> tuple[str, dict]:
    """Генерирует один эпизод.

    Возвращает (body_text, meta_dict). meta уже применён к БД.
    body_text — чистый текст эпизода (без блока META), готов к публикации.
    """
    state = await db.get_saga_state()
    summaries = await db.get_saga_summaries()
    force = _should_force_finale(state)

    prompt = prompts.saga_prompt(state, summaries, force_finale=force)
    raw = await _text(prompt, temperature=0.95, max_output_tokens=8192)

    # Нормальный ответ ВСЕГДА содержит блок META. Его отсутствие = обрыв
    # генерации (MAX_TOKENS) до меты. Не публикуем огрызок и не двигаем
    # состояние саги вслепую — падаем, scheduler уйдёт на фолбэк.
    if META_MARK not in raw:
        raise RuntimeError(
            f"saga: ответ оборван без блока META (len={len(raw)}), "
            "эпизод не сгенерирован полностью"
        )

    body, meta = _split_meta(raw)
    await _apply_meta(state, meta, body)
    logger.info("saga episode готов: arc=%s ep_in_arc=%s status=%s len=%d",
                meta.get("arc_number"), meta.get("episode_in_arc"),
                meta.get("arc_status"), len(body))
    return body, meta


# ------------------------------------------------------------- парсинг meta
def _split_meta(raw: str) -> tuple[str, dict]:
    """Режет ответ на текст эпизода и dict meta. meta может отсутствовать."""
    if META_MARK not in raw:
        logger.warning("saga: META не найдена в ответе — пустой meta")
        return raw.strip(), {}
    body, _, tail = raw.partition(META_MARK)
    meta = _parse_meta_json(tail)
    return body.strip(), meta


def _parse_meta_json(tail: str) -> dict:
    """Достаёт JSON из хвоста после META (терпим к обёрткам ```json)."""
    m = re.search(r"\{.*\}", tail, re.DOTALL)
    if not m:
        logger.warning("saga: JSON meta не распознан")
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        logger.exception("saga: битый JSON в meta")
        return {}


def _dump(value) -> str:
    """JSON-строка из dict/list, либо пропуск строки как есть."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


# ------------------------------------------------------- продвижение state
async def _apply_meta(state: dict | None, meta: dict, body: str) -> None:
    """Обновляет saga_state и saga_summaries по meta очередного эпизода.

    При arc_status == 'completed' закрывает арку и заводит следующую,
    беря arc_goal из pending_arc_seed (задел следующей арки от модели).
    """
    prev_arc = int((state or {}).get("arc_number") or 1)
    prev_ep = int((state or {}).get("episode_number") or 0)
    ep_number = prev_ep + 1

    summary = (meta.get("summary") or "").strip()
    if summary:
        await db.add_saga_summary(ep_number, prev_arc, summary)

    fields: dict = {"episode_number": ep_number}

    # значения, которые модель обновляет в каждом эпизоде
    if "characters" in meta:
        fields["characters_json"] = _dump(meta["characters"])
    if "locations" in meta:
        fields["locations_json"] = _dump(meta["locations"])
    if meta.get("narration"):
        fields["narration"] = meta["narration"]
    if meta.get("harmon_stage"):
        fields["harmon_stage"] = meta["harmon_stage"]
    if summary:
        fields["last_summary"] = summary

    status = (meta.get("arc_status") or "in_progress").strip()

    if status == "completed":
        # 1) дописываем синопсис завершённой арки
        syn_raw = (state or {}).get("arc_synopsis_json") or "[]"
        try:
            synopses = json.loads(syn_raw)
        except json.JSONDecodeError:
            synopses = []
        arc_syn = (meta.get("arc_synopsis") or summary or "").strip()
        if arc_syn:
            synopses.append(arc_syn)
        fields["arc_synopsis_json"] = json.dumps(synopses, ensure_ascii=False)

        # 2) следующая арка: goal = pending_arc_seed (задел от модели)
        seed = (meta.get("pending_arc_seed")
                or (state or {}).get("pending_arc_seed") or "").strip()
        fields["arc_number"] = prev_arc + 1
        fields["arc_goal"] = seed or None
        fields["pending_arc_seed"] = None
        fields["episode_in_arc"] = 0
        fields["harmon_stage"] = "1-Ты"
        fields["arc_status"] = "in_progress"
        fields["arc_plan_json"] = "[]"
        fields["planned_arc_length"] = int(
            meta.get("next_arc_length") or DEFAULT_ARC_LENGTH)
    else:
        # арка продолжается
        fields["arc_status"] = "in_progress"
        fields["episode_in_arc"] = int(
            (state or {}).get("episode_in_arc") or 0) + 1
        # первая арка: модель задаёт цель/план/длину на первом эпизоде
        if meta.get("arc_goal"):
            fields["arc_goal"] = meta["arc_goal"]
        if meta.get("arc_plan"):
            fields["arc_plan_json"] = _dump(meta["arc_plan"])
        if meta.get("planned_arc_length"):
            fields["planned_arc_length"] = int(meta["planned_arc_length"])
        # задел следующей арки, если модель его дала заранее
        if meta.get("pending_arc_seed"):
            fields["pending_arc_seed"] = meta["pending_arc_seed"]

    await db.upsert_saga_state(**fields)


async def set_prev_message_id(message_id: int) -> None:
    """Publisher вызывает после отправки — для reply-цепочки эпизодов."""
    await db.upsert_saga_state(prev_message_id=message_id)


async def set_prev_ids(last_id: int, first_id: int) -> None:
    """Сохраняет id последнего (для reply-цепочки) и первого (для
    ссылки-стрелки с предыдущего эпизода) сообщений эпизода."""
    await db.upsert_saga_state(
        prev_message_id=last_id,
        prev_first_message_id=first_id,
    )
