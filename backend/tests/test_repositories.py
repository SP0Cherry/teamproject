"""Repository-layer tests: CRUD happy paths + None/edge branches (TEST-04).

Covers data-access branches that HTTP-level tests don't reach:
task / notification / skill / group / attachment repositories.
Uses the isolated in-memory SQLite session from conftest.
"""

import pytest

from app.core.security import hash_password
from app.models.attachment import Attachment, AttachmentStatus
from app.models.group import GroupRole
from app.models.notification import NotificationStatus
from app.models.skill import SkillCapability
from app.models.task import TaskStatus
from app.models.user import User
from app.repositories.attachment import AttachmentRepository
from app.repositories.group import GroupRepository
from app.repositories.notification import NotificationRepository
from app.repositories.skill import SkillRepository
from app.repositories.task import TaskRepository


async def _seed_users(db_session, *ids):
    for uid in ids:
        db_session.add(User(id=uid, username=uid, password_hash=hash_password("x")))
    await db_session.commit()


@pytest.mark.asyncio
async def test_task_repo_crud(db_session):
    repo = TaskRepository(db_session)
    task = await repo.create(task_type="index", owner_id="u1", result=None)
    assert task.status == TaskStatus.PENDING
    assert task.attempts == 0

    fetched = await repo.get(task.id)
    assert fetched is not None and fetched.id == task.id
    assert await repo.get("nonexistent") is None

    updated = await repo.update_status(
        task.id, TaskStatus.SUCCEEDED, progress=100, error=None, result="ok"
    )
    assert updated.status == TaskStatus.SUCCEEDED
    assert updated.progress == 100
    assert updated.result == "ok"
    assert updated.attempts == 1

    # non-None error branch is persisted
    failed = await repo.update_status(task.id, TaskStatus.FAILED, error="boom")
    assert failed.error == "boom"
    assert failed.attempts == 2

    # update on missing id returns None without raising
    assert await repo.update_status("missing", TaskStatus.SUCCEEDED) is None


@pytest.mark.asyncio
async def test_notification_repo_crud(db_session):
    repo = NotificationRepository(db_session)
    n1 = await repo.create(
        owner_id="u1", group_id=None, source="manual", raw_text="hello", parsed="[]"
    )
    n2 = await repo.create(
        owner_id="u1", group_id=None, source="manual", raw_text="other"
    )
    await repo.create(
        owner_id="u2", group_id=None, source="manual", raw_text="mine"
    )

    mine = await repo.list_for_user("u1")
    assert {n.id for n in mine} == {n1.id, n2.id}

    assert (
        await repo.update_status(n1.id, NotificationStatus.CONFIRMED)
    ).status == NotificationStatus.CONFIRMED
    assert await repo.update_status("missing", NotificationStatus.CONFIRMED) is None

    group_repo = GroupRepository(db_session)
    g = await group_repo.create("g", None, owner_id="u1")
    pub = await repo.create(
        owner_id="u1", group_id=g.id, source="group", raw_text="pub"
    )
    priv = await repo.create(
        owner_id="u1", group_id=g.id, source="group", raw_text="priv"
    )
    await repo.set_published(pub.id, True)
    group_notifs = await repo.list_for_group(g.id)
    group_ids = {n.id for n in group_notifs}
    assert pub.id in group_ids
    assert priv.id not in group_ids

    assert await repo.set_published("missing", False) is None


@pytest.mark.asyncio
async def test_skill_repo_crud_and_versioning(db_session):
    repo = SkillRepository(db_session)
    s = await repo.create(
        owner_id="u1",
        name="skill1",
        capability=SkillCapability.QA,
        tool_refs="[]",
    )
    assert s.version == 1

    assert (await repo.get_owned(s.id, "u1")).name == "skill1"
    assert await repo.get_owned(s.id, "other") is None  # not owner -> None

    assert len(await repo.list_for_owner("u1")) == 1

    updated = await repo.update_owned(s.id, "u1", name="renamed")
    assert updated.name == "renamed"
    assert updated.version == 2  # version increments on update
    assert await repo.update_owned("missing", "u1", name="x") is None

    deleted = await repo.delete_owned(s.id, "u1")
    assert deleted is not None
    assert await repo.get_owned(s.id, "u1") is None
    assert await repo.delete_owned("missing", "u1") is None


@pytest.mark.asyncio
async def test_group_repo_membership_and_edges(db_session):
    await _seed_users(db_session, "owner1", "u2")
    repo = GroupRepository(db_session)
    g = await repo.create("team", "desc", owner_id="owner1")
    assert g.invite_token and len(g.invite_token) > 0

    owner_membership = await repo.get_membership(g.id, "owner1")
    assert owner_membership is not None
    assert owner_membership.role == GroupRole.OWNER

    assert (await repo.get_by_invite_token(g.invite_token)).id == g.id
    assert await repo.get_by_invite_token("nope") is None

    first = await repo.add_member(g.id, "u2", GroupRole.MEMBER)
    second = await repo.add_member(g.id, "u2", GroupRole.MEMBER)
    assert first.id == second.id  # idempotent: no duplicate member
    members = await repo.list_members(g.id)
    assert len(members) == 2  # owner + u2 (join requires real User rows)

    assert await repo.remove_member(g.id, "ghost") is False
    assert await repo.remove_member(g.id, "u2") is True
    assert await repo.get_membership(g.id, "u2") is None

    old_token = g.invite_token
    with pytest.raises(ValueError):
        await repo.regenerate_invite_token("missing")
    new_token = await repo.regenerate_invite_token(g.id)
    assert new_token != old_token
    assert g.invite_token == new_token  # in-session object reflects the refresh

    assert await repo.set_sync(g.id, "ghost", True) is None
    synced = await repo.set_sync(g.id, "owner1", True)
    assert synced.sync_enabled is True
    assert any(m.user_id == "owner1" for m in await repo.list_synced_members(g.id))


@pytest.mark.asyncio
async def test_attachment_repo_crud_and_versions(db_session):
    repo = AttachmentRepository(db_session)
    a = await repo.create(
        owner_id="u1",
        group_id=None,
        filename="f.txt",
        mime_type="text/plain",
        file_size=10,
        storage_path="/tmp/f.txt",
    )
    assert a.status == AttachmentStatus.PENDING
    assert a.version == 1

    assert (await repo.get(a.id)).id == a.id
    assert await repo.get("missing") is None

    assert len(await repo.list_for_user("u1")) == 1
    assert len(await repo.list_for_user("other")) == 0

    updated = await repo.update_status(
        a.id, AttachmentStatus.SUCCEEDED, extracted_text="hello", error=None
    )
    assert updated.extracted_text == "hello"
    assert updated.status == AttachmentStatus.SUCCEEDED

    # non-None error branch is persisted
    err = await repo.update_status(a.id, AttachmentStatus.FAILED, error="parse fail")
    assert err.error == "parse fail"
    assert await repo.update_status("missing", AttachmentStatus.SUCCEEDED) is None

    # list_for_group: returns top-level (parent_id IS NULL) group attachments only
    group_repo = GroupRepository(db_session)
    g = await group_repo.create("att-group", None, owner_id="u1")
    ga = await repo.create(
        owner_id="u1",
        group_id=g.id,
        filename="g.txt",
        mime_type="text/plain",
        file_size=1,
        storage_path="/tmp/g.txt",
    )
    group_atts = await repo.list_for_group(g.id)
    assert any(x.id == ga.id for x in group_atts)
    assert all(x.parent_id is None for x in group_atts)

    v2 = await repo.create_version(a, title="v2", extracted_text="v2 text")
    assert v2.version == 2
    assert v2.parent_id == a.id
    versions = await repo.list_versions(a.id)
    assert len(versions) == 1 and versions[0].id == v2.id

    assert await repo.delete("missing") is False
    assert await repo.delete(a.id) is True
    assert await repo.get(a.id) is None
