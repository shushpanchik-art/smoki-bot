from db import database as db


async def test_story_job_crud(tmp_db):
    await db.init_db()

    job_id = await db.add_story_job(
        target="@SMOKTOLK",
        theme=1,
        prompt_en="a cinematic sunrise",
        image_path="/tmp/x.jpg",
        caption="утро",
        publish_at="2025-01-01T10:00:00",
    )
    assert job_id > 0

    job = await db.get_story_job(job_id)
    assert job is not None
    assert job["target"] == "@SMOKTOLK"
    assert job["status"] == "pending"
    assert job["regen_count"] == 0

    await db.update_story_job(job_id, status="approved", regen_count=1)
    job = await db.get_story_job(job_id)
    assert job["status"] == "approved"
    assert job["regen_count"] == 1


async def test_story_job_queries(tmp_db):
    await db.init_db()

    j1 = await db.add_story_job("@SMOKTOLK", publish_at="2020-01-01T00:00:00")
    j2 = await db.add_story_job("@SMOKTOLK", publish_at="2099-01-01T00:00:00")
    j3 = await db.add_story_job("@SMOKTOLK")  # publish_at NULL

    # pending list
    pending = await db.get_pending_story_jobs()
    assert {p["id"] for p in pending} == {j1, j2, j3}

    # approve j1, j2, j3
    for jid in (j1, j2, j3):
        await db.update_story_job(jid, status="approved")

    # due: publish_at <= now OR NULL -> j1 и j3, но не j2 (2099)
    due = await db.get_due_approved_story_jobs("2025-06-01T00:00:00")
    due_ids = {d["id"] for d in due}
    assert j1 in due_ids
    assert j3 in due_ids
    assert j2 not in due_ids

    # published images
    await db.update_story_job(j1, status="published", image_path="/tmp/a.jpg")
    imgs = await db.get_published_story_images()
    assert any(i["id"] == j1 for i in imgs)
    assert all(i["image_path"] for i in imgs)


async def test_update_story_job_noop(tmp_db):
    await db.init_db()
    jid = await db.add_story_job("@SMOKTOLK")
    await db.update_story_job(jid)  # пустой — no-op, не падает
    job = await db.get_story_job(jid)
    assert job["status"] == "pending"
