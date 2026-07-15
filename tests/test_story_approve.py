"""U6.4: approve-flow сторис (статусы в БД)."""
from db import database as db


async def test_approve_flow_statuses(tmp_db):
    await db.init_db()
    jid = await db.add_story_job(
        "channel", theme=1, prompt_en="p",
        image_path="/tmp/x.png", caption="cap",
        publish_at="2020-01-01T10:00:00",
    )
    job = await db.get_story_job(jid)
    assert job["status"] == "pending"

    # due-pending выборка находит просроченный слот
    due = await db.get_due_pending_story_jobs("2025-01-01T00:00:00")
    assert any(d["id"] == jid for d in due)

    # approve → попадает в due_approved для userbot
    await db.update_story_job(jid, status="approved")
    appr = await db.get_due_approved_story_jobs("2025-01-01T00:00:00")
    assert any(a["id"] == jid for a in appr)


async def test_reject_saves_feedback(tmp_db):
    await db.init_db()
    jid = await db.add_story_job("channel", caption="c", image_path="/tmp/x.png")
    await db.update_story_job(jid, status="rejected", feedback="скучно")
    job = await db.get_story_job(jid)
    assert job["status"] == "rejected"
    assert job["feedback"] == "скучно"


async def test_cancel_status(tmp_db):
    await db.init_db()
    jid = await db.add_story_job("flood", caption="c")
    await db.update_story_job(jid, status="cancelled")
    job = await db.get_story_job(jid)
    assert job["status"] == "cancelled"
    # cancelled не попадает ни в due-pending, ни в approved
    assert not any(d["id"] == jid
                   for d in await db.get_due_pending_story_jobs("2030-01-01T00:00:00"))
