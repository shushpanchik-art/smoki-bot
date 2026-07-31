"""Тесты сервиса саги: _apply_meta двигает saga_state корректно (tmp_db).

Проверяем без вызова ИИ — только логику продвижения состояния:
первая арка, продолжение, переход арок (seed -> goal), парсинг META.
"""
import json
import re
from pathlib import Path

import pytest

from services import saga


# ------------------------------------------------------------ парсинг META
def test_split_meta_ok():
    raw = "Текст эпизода.\n===META===\n```json\n{\"summary\": \"s\"}\n```"
    body, meta = saga._split_meta(raw)
    assert body == "Текст эпизода."
    assert meta == {"summary": "s"}


def test_split_meta_absent():
    body, meta = saga._split_meta("Просто эпизод без меты")
    assert body == "Просто эпизод без меты"
    assert meta == {}


def test_split_meta_broken_json():
    body, meta = saga._split_meta("Тело\n===META===\n{битый}")
    assert body == "Тело"
    assert meta == {}


# ------------------------------------------------------ финал по счётчику
def test_should_force_finale():
    assert saga._should_force_finale(None) is False
    assert saga._should_force_finale(
        {"planned_arc_length": 6, "episode_in_arc": 0}) is False
    assert saga._should_force_finale(
        {"planned_arc_length": 6, "episode_in_arc": 5}) is True
    # перебор сверх FORCE_FINALE_AT
    assert saga._should_force_finale(
        {"planned_arc_length": 20, "episode_in_arc": 8}) is True


# ------------------------------------------- первый эпизод (пустое state)
@pytest.mark.asyncio
async def test_apply_meta_first_episode(tmp_db):
    from db import database as db
    await db.init_db()

    meta = {
        "summary": "Знакомство с героем.",
        "characters": {"Игорь": "владелец вейпшопа"},
        "locations": ["магазин"],
        "narration": "3-е лицо",
        "harmon_stage": "2-Нужда",
        "arc_goal": "Спасти магазин от закрытия",
        "arc_plan": ["завязка", "конфликт", "финал"],
        "planned_arc_length": 5,
        "arc_status": "in_progress",
    }
    await saga._apply_meta(None, meta, "тело")

    st = await db.get_saga_state()
    assert st["episode_number"] == 1
    assert st["arc_number"] == 1
    assert st["episode_in_arc"] == 1
    assert st["arc_goal"] == "Спасти магазин от закрытия"
    assert st["planned_arc_length"] == 5
    assert st["harmon_stage"] == "2-Нужда"
    assert json.loads(st["characters_json"]) == {"Игорь": "владелец вейпшопа"}
    assert st["arc_status"] == "in_progress"

    summaries = await db.get_saga_summaries()
    assert len(summaries) == 1
    assert summaries[0]["summary"] == "Знакомство с героем."
    assert summaries[0]["episode_number"] == 1
    assert summaries[0]["arc_number"] == 1


# ---------------------------------------------- продолжение той же арки
@pytest.mark.asyncio
async def test_apply_meta_continue_arc(tmp_db):
    from db import database as db
    await db.init_db()
    await db.upsert_saga_state(
        episode_number=3, arc_number=2, episode_in_arc=2,
        arc_goal="Цель2", planned_arc_length=6, arc_status="in_progress")

    await saga._apply_meta(
        await db.get_saga_state(),
        {"summary": "продолжение", "arc_status": "in_progress"},
        "тело")

    st = await db.get_saga_state()
    assert st["episode_number"] == 4
    assert st["arc_number"] == 2  # арка НЕ сменилась
    assert st["episode_in_arc"] == 3
    assert st["arc_goal"] == "Цель2"  # цель сохранилась


# ------------------------------- КЛЮЧЕВОЕ: переход арок, seed -> goal
@pytest.mark.asyncio
async def test_apply_meta_arc_completed_seed_becomes_goal(tmp_db):
    from db import database as db
    await db.init_db()
    await db.upsert_saga_state(
        episode_number=5, arc_number=1, episode_in_arc=5,
        arc_goal="Старая цель", planned_arc_length=6,
        arc_synopsis_json="[]", arc_status="in_progress")

    meta = {
        "summary": "Арка закрыта победой.",
        "arc_status": "completed",
        "arc_synopsis": "Первая арка: магазин спасён.",
        "pending_arc_seed": "Новый конкурент открылся напротив",
        "next_arc_length": 7,
        "harmon_stage": "6-Возврат",
    }
    await saga._apply_meta(await db.get_saga_state(), meta, "финальное тело")

    st = await db.get_saga_state()
    assert st["episode_number"] == 6
    # новая арка
    assert st["arc_number"] == 2
    assert st["episode_in_arc"] == 0
    assert st["arc_status"] == "in_progress"
    # goal взят из seed (замечание #3)
    assert st["arc_goal"] == "Новый конкурент открылся напротив"
    assert st["pending_arc_seed"] is None
    assert st["planned_arc_length"] == 7
    assert st["harmon_stage"] == "1-Ты"  # сброс на старт круга
    assert st["arc_plan_json"] == "[]"   # план сброшен
    # синопсис завершённой арки дописан
    assert json.loads(st["arc_synopsis_json"]) == [
        "Первая арка: магазин спасён."]

    # summary записан с НОМЕРОМ СТАРОЙ арки (эпизод-финал = арка 1)
    summaries = await db.get_saga_summaries()
    assert summaries[-1]["arc_number"] == 1
    assert summaries[-1]["episode_number"] == 6


@pytest.mark.asyncio
async def test_apply_meta_completed_seed_from_state(tmp_db):
    """Если seed не в meta, берётся заранее сохранённый pending_arc_seed."""
    from db import database as db
    await db.init_db()
    await db.upsert_saga_state(
        episode_number=4, arc_number=3, episode_in_arc=6,
        pending_arc_seed="Задел из прошлого эпизода",
        arc_synopsis_json="[]", arc_status="in_progress")

    await saga._apply_meta(
        await db.get_saga_state(),
        {"summary": "финал", "arc_status": "completed"},
        "тело")

    st = await db.get_saga_state()
    assert st["arc_number"] == 4
    assert st["arc_goal"] == "Задел из прошлого эпизода"
    assert st["pending_arc_seed"] is None


@pytest.mark.asyncio
async def test_set_prev_message_id(tmp_db):
    from db import database as db
    await db.init_db()
    await saga.set_prev_message_id(4242)
    st = await db.get_saga_state()
    assert st["prev_message_id"] == 4242


# ----------------------- баг 3: номер эпизода в хедере без двойного +1
@pytest.mark.asyncio
async def test_episode_header_number_no_double_shift(tmp_db):
    """После _apply_meta scheduler берёт ep = episode_in_arc (без +1).

    Раньше scheduler делал episode_in_arc + 1, а _apply_meta уже
    инкрементил счётчик — 1-й эпизод показывался как «эпизод 2».
    """
    from db import database as db
    await db.init_db()

    # первый эпизод
    await saga._apply_meta(None, {"summary": "s1", "arc_goal": "g",
                                  "arc_status": "in_progress"}, "тело")
    st = await db.get_saga_state()
    ep = int(st.get("episode_in_arc") or 1)  # формула scheduler
    assert ep == 1, f"1-й эпизод должен быть №1, а не {ep}"

    # второй эпизод
    await saga._apply_meta(st, {"summary": "s2",
                                "arc_status": "in_progress"}, "тело")
    st2 = await db.get_saga_state()
    ep2 = int(st2.get("episode_in_arc") or 1)
    assert ep2 == 2, f"2-й эпизод должен быть №2, а не {ep2}"


# диапазоны эмодзи: символьные пикто, доп.символы, дингбаты, VS-16
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE0F\U00002190-\U000021FF]"
)


def test_scheduler_header_no_emoji_and_no_double_ep():
    """Баг 5: в блоке header нет НИ ОДНОГО эмодзи; баг 3: ep без +1."""
    src = Path("scheduler.py").read_text(encoding="utf-8")
    # вырезаем только блок header = ( ... )
    m = re.search(r"header = \((.*?)\)", src, re.DOTALL)
    assert m, "блок header не найден в scheduler.py"
    header_block = m.group(1)
    found = _EMOJI.findall(header_block)
    assert not found, f"эмодзи в хедере: {found!r}"
    assert 'ep = int(state.get("episode_in_arc") or 0) + 1' not in src, \
        "остался двойной +1"
    assert 'ep = int(state.get("episode_in_arc") or 1)' in src
