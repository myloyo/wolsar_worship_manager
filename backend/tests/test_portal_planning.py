from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from worship_bot.api.routers.notifications import claim_notifications, notification_result
from worship_bot.api.schemas import NotificationResult
from worship_bot.api.security import create_access_token
from worship_bot.application.exceptions import AccessDeniedError
from worship_bot.application.services.planning import validate_proposal
from worship_bot.config import Settings, get_settings
from worship_bot.domain.planning import PlannedAssignment, PlannedEvent, ScheduleProposal
from worship_bot.domain.portal import permissions_for
from worship_bot.infrastructure.database import get_session
from worship_bot.infrastructure.event_notifications import (
    event_notification_enabled,
    event_recipients,
)
from worship_bot.infrastructure.models import (
    Base,
    ChurchMembershipRecord,
    ChurchMinistryRecord,
    ChurchRecord,
    EventNotificationPreferenceRecord,
    EventRecord,
    EventRoleSlotRecord,
    EventSeriesRecord,
    ExternalAccountRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    NotificationJobRecord,
    UserMinistryRoleRecord,
    UserRecord,
)
from worship_bot.infrastructure.models.portal import LoginCodeRecord
from worship_bot.infrastructure.notification_queue import queue_event_reminders
from worship_bot.infrastructure.repositories.events import SqlEventCalendarRepository
from worship_bot.infrastructure.repositories.planning import SqlPlanningRepository
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository
from worship_bot.main import app


@pytest.mark.parametrize("access", ["admin", "coordinator"])
async def test_manager_deletes_only_selected_event_and_related_data(
    portal_session: AsyncSession, portal_http: AsyncClient, content_event: EventRecord, access: str
) -> None:
    # Arrange
    membership = await portal_session.get(MinistryMembershipRecord, 1)
    assert membership is not None
    membership.access_level = access
    series = EventSeriesRecord(
        church_ministry_id=1, event_name="Weekly", starts_at=content_event.event_date
    )
    portal_session.add(series)
    await portal_session.flush()
    content_event.event_series_id = series.id
    next_event = EventRecord(
        event_name="Next week",
        event_date=content_event.event_date + timedelta(days=7),
        church_id=1,
        church_ministry_id=1,
        event_series_id=series.id,
    )
    portal_session.add_all(
        [
            next_event,
            EventNotificationPreferenceRecord(event_id=content_event.id, user_id=2, enabled=True),
            NotificationJobRecord(
                event_id=content_event.id,
                user_id=2,
                notification_type="event",
                scheduled_at=datetime.now(UTC),
                deduplication_key="delete-test",
            ),
        ]
    )
    await portal_session.commit()
    await portal_session.execute(text("PRAGMA foreign_keys=ON"))
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    deleted_id = content_event.id

    # Act
    response = await portal_http.delete(f"/api/v1/portal/events/{deleted_id}")
    missing = await portal_http.get(f"/api/v1/portal/events/{deleted_id}")
    remaining = await portal_http.get(f"/api/v1/portal/events/{next_event.id}")

    # Assert
    assert response.status_code == 204
    assert missing.status_code == 404
    assert remaining.status_code == 200
    for model in (EventRoleSlotRecord, NotificationJobRecord, EventNotificationPreferenceRecord):
        assert (
            await portal_session.scalar(
                select(func.count()).select_from(model).where(model.event_id == deleted_id)
            )
            == 0
        )


async def test_member_can_open_event_but_cannot_delete_it(
    portal_session: AsyncSession, portal_http: AsyncClient, content_event: EventRecord
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    details = await portal_http.get(f"/api/v1/portal/events/{content_event.id}")
    deleted = await portal_http.delete(f"/api/v1/portal/events/{content_event.id}")

    # Assert
    assert details.status_code == 200
    assert details.json()["role_slots"][0]["user_ministry_role_id"] == 1
    assert deleted.status_code == 403


@pytest.mark.parametrize("status", ["pending", "confirmed"])
async def test_replacement_retains_assignment_and_notifies_scoped_managers_once(
    portal_session: AsyncSession, portal_http: AsyncClient, content_event: EventRecord, status: str
) -> None:
    # Arrange
    slot = await portal_session.scalar(
        select(EventRoleSlotRecord).where(EventRoleSlotRecord.event_id == content_event.id)
    )
    assert slot is not None
    slot.confirmation_status = status
    portal_session.add_all(
        [
            UserRecord(id=3, name="Coordinator", surname="Three", church_id=1),
            UserRecord(id=4, name="Other admin", surname="Four", church_id=1),
            MinistryTypeRecord(id=2, code="youth", name="Youth"),
            ChurchMinistryRecord(id=2, church_id=1, ministry_type_id=2),
        ]
    )
    await portal_session.flush()
    portal_session.add_all(
        [
            MinistryMembershipRecord(user_id=3, church_ministry_id=1, access_level="coordinator"),
            MinistryMembershipRecord(user_id=4, church_ministry_id=2, access_level="admin"),
            ExternalAccountRecord(
                user_id=1,
                provider="telegram",
                external_user_id="manager",
                verified_at=datetime.now(UTC),
            ),
            EventNotificationPreferenceRecord(event_id=content_event.id, user_id=1, enabled=False),
        ]
    )
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    listed = (await portal_http.get("/api/v1/portal/me/assignments")).json()
    payload = {"accept": False, "revision": listed[0]["revision"]}

    # Act
    requested = await portal_http.put(f"/api/v1/portal/me/assignments/{slot.id}", json=payload)
    repeated = await portal_http.put(f"/api/v1/portal/me/assignments/{slot.id}", json=payload)
    jobs = list(
        await portal_session.scalars(
            select(NotificationJobRecord).where(
                NotificationJobRecord.notification_type == "replacement"
            )
        )
    )
    delivered = await claim_notifications(portal_session)

    # Assert
    assert requested.status_code == repeated.status_code == 204
    assert slot.user_ministry_role_id == 1
    assert slot.confirmation_status == "replacement"
    assert {job.user_id for job in jobs} == {1, 3}
    assert len(jobs) == 2
    assert len(delivered) == 1
    assert "Member Two" in delivered[0].text
    assert "Vocal" in delivered[0].text
    assert "замен" in delivered[0].text


async def test_event_notification_opt_out_suppresses_reminders_content_and_delivery(
    portal_session: AsyncSession, portal_http: AsyncClient, content_event: EventRecord
) -> None:
    # Arrange
    content_event.event_reminder_at = content_event.event_date - timedelta(days=1)
    portal_session.add(
        ExternalAccountRecord(
            user_id=2, provider="telegram", external_user_id="member", verified_at=datetime.now(UTC)
        )
    )
    await queue_event_reminders(portal_session, content_event.id)
    job = NotificationJobRecord(
        event_id=content_event.id,
        user_id=2,
        notification_type="assignment",
        scheduled_at=datetime.now(UTC),
        deduplication_key="muted-assignment",
    )
    portal_session.add(job)
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    default = await portal_http.get(f"/api/v1/portal/events/{content_event.id}/notifications")

    # Act
    saved = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/notifications", json={"enabled": False}
    )
    content = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/content",
        json={"revision": 0, "songs_text": "New song", "clothing_text": "Blue"},
    )
    claimed = await claim_notifications(portal_session)
    recipients = await event_recipients(portal_session, content_event.id)

    # Assert
    assert default.json() == {"enabled": True}
    assert saved.status_code == content.status_code == 204
    assert recipients == set()
    assert not await event_notification_enabled(portal_session, job)
    assert claimed == []
    assert (
        await portal_session.scalar(
            select(func.count())
            .select_from(NotificationJobRecord)
            .where(NotificationJobRecord.notification_type == "event_content")
        )
        == 0
    )
    assert (
        await portal_session.scalar(
            select(func.count())
            .select_from(NotificationJobRecord)
            .where(
                NotificationJobRecord.notification_type.in_(("event", "event_2h")),
                NotificationJobRecord.status == "cancelled",
            )
        )
        == 2
    )


async def test_unassigned_member_can_subscribe_to_event_and_receive_updates(
    portal_session: AsyncSession, portal_http: AsyncClient, content_event: EventRecord
) -> None:
    # Arrange
    content_event.event_reminder_at = content_event.event_date - timedelta(days=1)
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    default = await portal_http.get(f"/api/v1/portal/events/{content_event.id}/notifications")

    # Act
    subscribed = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/notifications", json={"enabled": True}
    )
    recipients = await event_recipients(portal_session, content_event.id)
    jobs = list(
        await portal_session.scalars(
            select(NotificationJobRecord).where(NotificationJobRecord.user_id == 1)
        )
    )

    # Assert
    assert default.json() == {"enabled": False}
    assert subscribed.status_code == 204
    assert recipients == {1, 2}
    assert {job.notification_type for job in jobs} == {"event", "event_2h"}


async def test_member_sees_events_without_personal_assignments(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    unassigned = EventRecord(
        event_name="Open service",
        church_id=1,
        church_ministry_id=1,
        event_date=datetime.now(UTC) + timedelta(days=6),
    )
    portal_session.add(unassigned)
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.get(
        "/api/v1/portal/ministries/1/events",
        params={
            "start": datetime.now(UTC).isoformat(),
            "end": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
        },
    )

    # Assert
    assert response.status_code == 200
    assert {event["event_id"] for event in response.json()} == {content_event.id, unassigned.id}


async def test_worship_event_starts_with_nine_default_unassigned_slots(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
) -> None:
    # Arrange
    from worship_bot.domain.worship_roles import WORSHIP_ROLES

    portal_session.add_all(
        MinistryRoleRecord(church_ministry_id=1, code=code, name=name)
        for code, name in WORSHIP_ROLES
        if code != "lead_vocal"
    )
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    templates = await portal_http.get("/api/v1/portal/ministries/1/templates")
    created = await portal_http.post(
        "/api/v1/portal/ministries/1/events",
        json={
            "event_name": "Воскресное собрание",
            "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        },
    )

    # Assert
    assert templates.status_code == 200
    assert all(len(template["role_slots"]) == 9 for template in templates.json())
    assert created.status_code == 200
    slots = created.json()[0]["role_slots"]
    assert len(slots) == 9
    assert all(slot["user_ministry_role_id"] is None for slot in slots)
    back_id = await portal_session.scalar(
        select(MinistryRoleRecord.id).where(MinistryRoleRecord.code == "back_vocal")
    )
    assert sorted(slot["slot_number"] for slot in slots if slot["ministry_role_id"] == back_id) == [
        1,
        2,
    ]


@pytest.fixture
async def content_event(portal_session: AsyncSession) -> EventRecord:
    event = EventRecord(
        event_name="Воскресное собрание",
        event_kind="sunday",
        event_date=datetime.now(UTC) + timedelta(days=5),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    portal_session.add(
        EventRoleSlotRecord(event_id=event.id, ministry_role_id=1, user_ministry_role_id=1)
    )
    await portal_session.commit()
    return event


async def test_assigned_lead_saves_content_and_notifies_once_per_recipient(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    payload = {
        "revision": 0,
        "songs_text": "1. Песня\n2. Другая песня",
        "clothing_text": "Белый верх",
    }

    # Act
    response = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/content", json=payload
    )
    repeated = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/content", json={**payload, "revision": 1}
    )
    jobs = list(
        await portal_session.scalars(
            select(NotificationJobRecord).where(
                NotificationJobRecord.notification_type == "event_content"
            )
        )
    )

    # Assert
    assert response.status_code == repeated.status_code == 204
    assert content_event.songs_text == payload["songs_text"]
    assert content_event.clothing_text == "Белый верх"
    assert content_event.content_revision == 1
    assert [job.user_id for job in jobs] == [2]


async def test_admin_without_assigned_lead_cannot_edit_event_content(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/content",
        json={"revision": 0, "songs_text": "New", "clothing_text": "New"},
    )

    # Assert
    assert response.status_code == 403
    assert content_event.songs_text == ""
    assert content_event.content_revision == 0


async def test_event_content_rejects_stale_revision(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    content_event.content_revision = 1
    content_event.songs_text = "Already updated"
    await portal_session.commit()

    # Act
    response = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/content",
        json={"revision": 0, "songs_text": "Overwrite", "clothing_text": ""},
    )

    # Assert
    assert response.status_code == 422
    assert content_event.songs_text == "Already updated"


async def test_restricting_role_rejects_existing_incompatible_assignments(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.put(
        "/api/v1/portal/ministries/1/members/2/roles/1/event-kinds",
        json={"allowed_event_kinds": ["prayer"]},
    )
    role = await portal_session.get(UserMinistryRoleRecord, 1)

    # Assert
    assert response.status_code == 422
    assert role is not None and role.allowed_event_kinds == []


@pytest.mark.parametrize("path", ["/role-slots", ""])
async def test_restricted_participant_cannot_be_assigned_to_other_event_kind(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    path: str,
) -> None:
    # Arrange
    role = await portal_session.get(UserMinistryRoleRecord, 1)
    assert role is not None
    role.allowed_event_kinds = ["prayer"]
    event = EventRecord(
        event_name="Sunday",
        event_kind="sunday",
        church_id=1,
        church_ministry_id=1,
        event_date=datetime.now(UTC) + timedelta(days=3),
    )
    portal_session.add(event)
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.post(
        f"/api/v1/portal/events/{event.id}/role-slots"
        if path
        else "/api/v1/portal/ministries/1/events",
        json={"ministry_role_id": 1, "user_ministry_role_id": 1}
        if path
        else {
            "event_name": "Sunday",
            "event_kind": "sunday",
            "starts_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "role_slots": [{"ministry_role_id": 1, "user_ministry_role_id": 1}],
        },
    )

    # Assert
    assert response.status_code == 422
    assert await portal_session.scalar(select(func.count()).select_from(EventRoleSlotRecord)) == 0


async def test_member_cannot_change_event_kind_restrictions(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.put(
        "/api/v1/portal/ministries/1/members/2/roles/1/event-kinds",
        json={"allowed_event_kinds": ["sunday"]},
    )

    # Assert
    assert response.status_code == 403


async def test_back_vocalist_cannot_edit_content_even_when_assigned(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    role = await portal_session.get(MinistryRoleRecord, 1)
    assert role is not None
    role.code = "back_vocal"
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    permission = await portal_http.get(
        f"/api/v1/portal/events/{content_event.id}/content-permission"
    )
    response = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/content",
        json={"revision": 0, "songs_text": "New", "clothing_text": "New"},
    )

    # Assert
    assert permission.json() == {"can_edit": False}
    assert response.status_code == 403


@pytest.mark.parametrize("access", ["coordinator", "admin"])
async def test_manager_saves_allowed_event_kinds_per_role(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    access: str,
) -> None:
    # Arrange
    membership = await portal_session.get(MinistryMembershipRecord, 1)
    assert membership is not None
    membership.access_level = access
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.put(
        "/api/v1/portal/ministries/1/members/2/roles/1/event-kinds",
        json={"allowed_event_kinds": ["prayer", "sunday"]},
    )
    people = await portal_http.get("/api/v1/portal/ministries/1/members")

    # Assert
    assert response.status_code == 204
    person = next(person for person in people.json() if person["id"] == 2)
    assert person["roles"][0]["allowed_event_kinds"] == ["prayer", "sunday"]


async def test_changing_event_kind_respects_assigned_roles(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    content_event: EventRecord,
) -> None:
    # Arrange
    role = await portal_session.get(UserMinistryRoleRecord, 1)
    assert role is not None
    role.allowed_event_kinds = ["sunday"]
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.put(
        f"/api/v1/portal/events/{content_event.id}/kind", json={"event_kind": "praise"}
    )

    # Assert
    assert response.status_code == 422
    assert content_event.event_kind == "sunday"


@pytest.mark.parametrize("access", ["admin", "coordinator"])
async def test_manager_adds_role_to_self_idempotently(
    portal_http: AsyncClient, portal_session: AsyncSession, access: str
) -> None:
    # Arrange
    membership = await portal_session.get(MinistryMembershipRecord, 1)
    assert membership is not None
    membership.access_level = access
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    first = await portal_http.post(
        "/api/v1/portal/ministries/1/members/1/roles", json={"ministry_role_id": 1}
    )
    repeated = await portal_http.post(
        "/api/v1/portal/ministries/1/members/1/roles", json={"ministry_role_id": 1}
    )

    # Assert
    assert first.status_code == 204
    assert repeated.status_code == 204
    assert membership.access_level == access
    assert (
        await portal_session.scalar(
            select(func.count())
            .select_from(UserMinistryRoleRecord)
            .where(
                UserMinistryRoleRecord.ministry_membership_id == 1,
                UserMinistryRoleRecord.ministry_role_id == 1,
            )
        )
        == 1
    )


async def test_member_cannot_assign_self_a_role(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.post(
        "/api/v1/portal/ministries/1/members/2/roles", json={"ministry_role_id": 1}
    )

    # Assert
    assert response.status_code == 403


@pytest.fixture
async def portal_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(
            [
                ChurchRecord(id=1, name="Test church"),
                MinistryTypeRecord(id=1, code="worship", name="Worship"),
            ]
        )
        await session.flush()
        session.add_all(
            [
                UserRecord(id=1, name="Admin", surname="One", church_id=1),
                UserRecord(id=2, name="Member", surname="Two", church_id=1),
                ChurchMinistryRecord(id=1, church_id=1, ministry_type_id=1),
            ]
        )
        await session.flush()
        session.add_all(
            [
                ChurchMembershipRecord(id=1, user_id=1, church_id=1),
                ChurchMembershipRecord(id=2, user_id=2, church_id=1),
                MinistryMembershipRecord(
                    id=1, user_id=1, church_ministry_id=1, access_level="admin"
                ),
                MinistryMembershipRecord(
                    id=2, user_id=2, church_ministry_id=1, access_level="member"
                ),
                MinistryRoleRecord(id=1, church_ministry_id=1, name="Vocal", code="lead_vocal"),
            ]
        )
        await session.flush()
        session.add(
            UserMinistryRoleRecord(
                id=1, church_membership_id=2, ministry_membership_id=2, ministry_role_id=1
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
def proposal() -> ScheduleProposal:
    return ScheduleProposal(
        reply="Prepared",
        warnings=[],
        events=[
            PlannedEvent(
                existing_event_id=None,
                event_name="Service",
                starts_at=datetime(2026, 11, 1, 10, tzinfo=UTC),
                additional_info=None,
                assignments=[PlannedAssignment(ministry_role_id=1, user_ministry_role_id=1)],
            )
        ],
    )


@pytest.fixture
def member_context() -> list[dict[str, Any]]:
    return [{"id": 2, "roles": [{"id": 1, "user_ministry_role_id": 1}]}]


async def test_login_code_can_be_exchanged_only_once(portal_session: AsyncSession) -> None:
    # Arrange
    repository = SqlPortalRepository(portal_session)
    ticket = await repository.issue_login(1)

    # Act
    first = await repository.exchange_login(ticket.code)
    replay = await repository.exchange_login(ticket.code)

    # Assert
    assert first == 1
    assert replay is None


async def test_expired_login_code_is_rejected(portal_session: AsyncSession) -> None:
    # Arrange
    repository = SqlPortalRepository(portal_session)
    ticket = await repository.issue_login(1)
    record = await portal_session.scalar(select(LoginCodeRecord))
    assert record is not None
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await portal_session.commit()

    # Act
    user_id = await repository.exchange_login(ticket.code)

    # Assert
    assert user_id is None


async def test_member_cannot_generate_schedule(portal_session: AsyncSession) -> None:
    # Arrange
    repository = SqlPortalRepository(portal_session)

    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await repository.require_permission(2, 1, "use_assistant")


async def test_admin_profile_has_scoped_permissions(portal_session: AsyncSession) -> None:
    # Arrange
    repository = SqlPortalRepository(portal_session)

    # Act
    profile = await repository.profile(1)
    members = await repository.members(1)

    # Assert
    assert profile.ministries[0].permissions == permissions_for("admin")
    assert members[1].roles[0].user_ministry_role_id == 1


async def test_apply_creates_assignments_and_notifications(
    portal_session: AsyncSession, proposal: ScheduleProposal
) -> None:
    # Arrange
    repository = SqlPlanningRepository(portal_session)
    record = await repository.create(1, 1, "2026-11")
    record.proposal = proposal.model_dump(mode="json")
    record.revision = 1
    await portal_session.commit()

    # Act
    ids = await repository.apply(record, 1)

    # Assert
    assert len(ids) == 1
    assert record.applied_at is not None
    assert await portal_session.scalar(select(func.count()).select_from(NotificationJobRecord)) == 1


@pytest.mark.parametrize("event_state", ["new", "empty", "occupied"])
async def test_assistant_fills_two_back_vocal_slots(
    portal_session: AsyncSession,
    portal_http: AsyncClient,
    proposal: ScheduleProposal,
    monkeypatch: pytest.MonkeyPatch,
    event_state: str,
) -> None:
    # Arrange
    role = await portal_session.get(MinistryRoleRecord, 1)
    assert role is not None
    role.code = "back_vocal"
    role.name = "Бэк-вокал"
    portal_session.add(
        MinistryRoleRecord(id=2, church_ministry_id=1, name="Скрипка", code="violin")
    )
    portal_session.add(
        UserMinistryRoleRecord(
            id=2, church_membership_id=1, ministry_membership_id=1, ministry_role_id=1
        )
    )
    planned = proposal.events[0]
    planned.assignments.append(PlannedAssignment(ministry_role_id=1, user_ministry_role_id=2))
    planned.extra_role_ids.append(2)
    if event_state != "new":
        event = EventRecord(
            church_id=1,
            church_ministry_id=1,
            event_name=planned.event_name,
            event_date=planned.starts_at,
        )
        portal_session.add(event)
        await portal_session.flush()
        planned.existing_event_id = event.id
        if event_state == "occupied":
            portal_session.add(
                EventRoleSlotRecord(
                    event_id=event.id,
                    ministry_role_id=1,
                    slot_number=1,
                    user_ministry_role_id=2,
                    confirmation_status="confirmed",
                )
            )
    await portal_session.commit()
    record = await SqlPlanningRepository(portal_session).create(1, 1, "2026-11")
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    async def generate(*args: object) -> ScheduleProposal:
        return proposal

    monkeypatch.setattr("worship_bot.api.routers.planning.generate_proposal", generate)
    url = f"/api/v1/portal/assistant/sessions/{record.id}"

    # Act
    draft = await portal_http.post(f"{url}/messages", json={"message": "Два бэк-вокала"})
    assert draft.status_code == 200, draft.text
    assert draft.json()["proposal"]["events"][0]["extra_role_ids"] == [2]
    assert await portal_session.scalar(select(func.count()).select_from(EventRoleSlotRecord)) == (
        1 if event_state == "occupied" else 0
    )
    applied = await portal_http.post(f"{url}/apply", json={"revision": draft.json()["revision"]})

    # Assert
    assert applied.status_code == 200, applied.text
    slots = list(
        await portal_session.scalars(
            select(EventRoleSlotRecord)
            .where(EventRoleSlotRecord.event_id == applied.json()["event_ids"][0])
            .order_by(EventRoleSlotRecord.ministry_role_id, EventRoleSlotRecord.slot_number)
        )
    )
    assert [(slot.slot_number, slot.user_ministry_role_id) for slot in slots[:2]] == (
        [(1, 2), (2, 1)] if event_state == "occupied" else [(1, 1), (2, 2)]
    )
    assert len(slots) == 3
    assert slots[2].ministry_role_id == 2 and slots[2].user_ministry_role_id is None
    assert slots[0].confirmation_status == ("confirmed" if event_state == "occupied" else "pending")


async def test_invalid_proposal_does_not_write_events(
    portal_session: AsyncSession, proposal: ScheduleProposal
) -> None:
    # Arrange
    repository = SqlPlanningRepository(portal_session)
    record = await repository.create(1, 1, "2026-11")
    proposal.events[0].assignments[0].user_ministry_role_id = 999
    record.proposal = proposal.model_dump(mode="json")
    record.revision = 1
    await portal_session.commit()

    # Act / Assert
    with pytest.raises(ValueError, match="не имеет"):
        await repository.apply(record, 1)

    # Assert
    assert await portal_session.scalar(select(func.count()).select_from(EventRecord)) == 0


async def test_stale_proposal_revision_is_rejected(
    portal_session: AsyncSession, proposal: ScheduleProposal
) -> None:
    # Arrange
    repository = SqlPlanningRepository(portal_session)
    record = await repository.create(1, 1, "2026-11")
    record.proposal = proposal.model_dump(mode="json")
    record.revision = 2
    await portal_session.commit()

    # Act / Assert
    with pytest.raises(ValueError, match="изменился"):
        await repository.apply(record, 1)


@pytest.mark.parametrize("month", ["2026-10", "2026-12"])
def test_proposal_cannot_write_outside_target_month(
    proposal: ScheduleProposal, member_context: list[dict[str, Any]], month: str
) -> None:
    # Act / Assert
    with pytest.raises(ValueError, match="выбранному месяцу"):
        validate_proposal(proposal, month, member_context, [])


@pytest.fixture
async def portal_http(portal_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    previous = dict(app.dependency_overrides)
    settings = Settings(
        jwt_secret=SecretStr("test-secret-with-at-least-32-characters"),
        bot_service_token=SecretStr("unit-only-bot-service-token"),
    )

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield portal_session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def test_web_login_sets_http_only_cookie(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(1)

    # Act
    response = await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    profile = await portal_http.get("/api/v1/portal/me")

    # Assert
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert profile.json()["id"] == 1


async def test_member_cannot_access_another_ministry(portal_http: AsyncClient) -> None:
    # Arrange
    token = create_access_token(
        2, Settings(jwt_secret=SecretStr("test-secret-with-at-least-32-characters"))
    )

    # Act
    response = await portal_http.get(
        "/api/v1/portal/ministries/999/members", headers={"Authorization": "Bearer " + token}
    )

    # Assert
    assert response.status_code == 403


async def test_member_cannot_call_assistant_directly(portal_http: AsyncClient) -> None:
    # Arrange
    token = create_access_token(
        2, Settings(jwt_secret=SecretStr("test-secret-with-at-least-32-characters"))
    )

    # Act
    response = await portal_http.post(
        "/api/v1/portal/assistant/sessions",
        json={"ministry_id": 1, "month": "2026-11"},
        headers={"Authorization": "Bearer " + token},
    )

    # Assert
    assert response.status_code == 403


async def test_notification_claim_and_acknowledgement(portal_session: AsyncSession) -> None:
    # Arrange
    event = EventRecord(
        event_name="Service",
        event_date=datetime.now(UTC) + timedelta(days=2),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    portal_session.add(
        ExternalAccountRecord(
            user_id=2, provider="telegram", external_user_id="42", verified_at=datetime.now(UTC)
        )
    )
    job = NotificationJobRecord(
        event_id=event.id,
        user_id=2,
        notification_type="assignment",
        scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
        payload={"text": "Назначение"},
        deduplication_key="test-assignment",
    )
    portal_session.add(job)
    await portal_session.commit()

    # Act
    claimed = await claim_notifications(portal_session)
    await notification_result(
        job.id,
        NotificationResult(claim_token=claimed[0].claim_token, delivered=True),
        portal_session,
    )

    # Assert
    assert claimed[0].external_user_id == "42"
    assert job.status == "sent"
    assert job.attempts == 1
    assert job.claim_token is None


async def test_reminder_queue_has_day_and_two_hour_jobs(portal_session: AsyncSession) -> None:
    # Arrange
    start = datetime.now(UTC) + timedelta(days=3)
    event = EventRecord(
        event_name="Service",
        event_date=start,
        event_reminder_at=start - timedelta(days=1),
        rehearsal_at=start - timedelta(hours=12),
        rehearsal_reminder_at=start - timedelta(hours=36),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    portal_session.add(
        EventRoleSlotRecord(
            event_id=event.id, ministry_role_id=1, slot_number=1, user_ministry_role_id=1
        )
    )
    await portal_session.flush()

    # Act
    await queue_event_reminders(portal_session, event.id)
    jobs = list(await portal_session.scalars(select(NotificationJobRecord)))

    # Assert
    assert {job.notification_type for job in jobs} == {
        "event",
        "event_2h",
        "rehearsal",
        "rehearsal_2h",
    }
    assert len({job.deduplication_key for job in jobs}) == 4


async def test_calendar_preserves_rehearsal_settings(portal_session: AsyncSession) -> None:
    # Arrange
    start = datetime.now(UTC) + timedelta(days=3)
    event = EventRecord(
        event_name="Service",
        event_date=start,
        rehearsal_at=start - timedelta(hours=12),
        event_reminder_at=start - timedelta(days=1),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    repository = SqlEventCalendarRepository(portal_session)

    # Act
    items = await repository.load_calendar_items((event.id,))

    # Assert
    assert items[0].event.rehearsal_at == event.rehearsal_at
    assert items[0].event.event_reminder_at == event.event_reminder_at


async def test_applied_draft_cannot_be_reused(portal_session: AsyncSession) -> None:
    # Arrange
    repository = SqlPlanningRepository(portal_session)
    record = await repository.create(1, 1, "2026-11")
    record.applied_at = datetime.now(UTC)
    await portal_session.commit()

    # Act / Assert
    with pytest.raises(ValueError, match="уже применён"):
        await repository.get(record.id, 1)


async def test_ministry_admin_can_promote_member(portal_session: AsyncSession) -> None:
    # Arrange
    from worship_bot.application.services import MinistryService
    from worship_bot.infrastructure.repositories.churches import SqlChurchRepository
    from worship_bot.infrastructure.repositories.ministries import SqlMinistryRepository

    service = MinistryService(
        SqlMinistryRepository(portal_session), SqlChurchRepository(portal_session)
    )

    # Act
    await service.set_member_access_level(1, 1, 2, "admin")

    # Assert
    assert await SqlMinistryRepository(portal_session).access_level(2, 1) == "admin"


async def test_member_cannot_promote_self(portal_session: AsyncSession) -> None:
    # Arrange
    from worship_bot.application.services import MinistryService
    from worship_bot.infrastructure.repositories.churches import SqlChurchRepository
    from worship_bot.infrastructure.repositories.ministries import SqlMinistryRepository

    service = MinistryService(
        SqlMinistryRepository(portal_session), SqlChurchRepository(portal_session)
    )

    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await service.set_member_access_level(2, 1, 2, "admin")
    assert await SqlMinistryRepository(portal_session).access_level(2, 1) == "member"


async def test_last_admin_cannot_be_demoted(portal_session: AsyncSession) -> None:
    # Arrange
    from worship_bot.infrastructure.repositories.ministries import SqlMinistryRepository

    repository = SqlMinistryRepository(portal_session)

    # Act / Assert
    with pytest.raises(ValueError, match="администратора"):
        await repository.set_access_level(1, 1, "member")
    assert await repository.access_level(1, 1) == "admin"


async def test_push_subscription_tracks_status_and_is_owned(portal_session: AsyncSession) -> None:
    # Arrange
    from fastapi import HTTPException
    from worship_bot.api.push_schemas import PushKeys, PushRegistration, PushState
    from worship_bot.api.routers.web_push import subscribe, sync_push_state

    settings = Settings(vapid_private_key=SecretStr("not-a-real-key"), vapid_public_key="public")
    registration = PushRegistration(
        endpoint="https://fcm.googleapis.com/fcm/send/sample",
        keys=PushKeys(p256dh="a" * 87, auth="b" * 22),
    )

    # Act
    await subscribe(registration, 2, portal_session, settings)
    members = await SqlPortalRepository(portal_session).members(1)

    # Assert
    assert next(member for member in members if member.id == 2).notification_status == "enabled"
    with pytest.raises(HTTPException) as error:
        await subscribe(registration, 1, portal_session, settings)
    assert error.value.status_code == 409

    # Act
    await sync_push_state(
        PushState(endpoint=registration.endpoint, permission="denied"), 2, portal_session
    )
    members = await SqlPortalRepository(portal_session).members(1)

    # Assert
    assert next(member for member in members if member.id == 2).notification_status == "needs_setup"


async def test_accounts_cannot_be_created_without_self_registration(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.post(
        "/api/v1/portal/ministries/1/members",
        json={"name": "New", "surname": "Participant", "role_ids": [1]},
    )
    count = await portal_session.scalar(select(func.count()).select_from(UserRecord))

    # Assert
    assert response.status_code == 405
    assert count == 2


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://localhost/push",
        "https://127.0.0.1/push",
        "https://fcm.googleapis.com.evil.example/push",
        "http://fcm.googleapis.com/push",
        "https://fcm.googleapis.com:bad/push",
        "https://user:password@fcm.googleapis.com/push",
    ],
)
def test_push_endpoint_rejects_arbitrary_destinations(endpoint: str) -> None:
    # Arrange
    from worship_bot.infrastructure.push_sender import valid_push_endpoint

    # Act
    valid = valid_push_endpoint(endpoint)

    # Assert
    assert not valid


async def test_web_push_worker_retries_without_duplicating_success(
    portal_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    from contextlib import asynccontextmanager
    from unittest.mock import Mock

    import worship_bot.push_worker as worker
    from worship_bot.infrastructure.models.web_push import (
        PushDeliveryRecord,
        PushSubscriptionRecord,
    )

    now = datetime.now(UTC)
    event = EventRecord(
        event_name="Service", event_date=now + timedelta(days=1), church_id=1, church_ministry_id=1
    )
    portal_session.add(event)
    await portal_session.flush()
    portal_session.add(
        PushSubscriptionRecord(
            user_id=2,
            endpoint="https://fcm.googleapis.com/fcm/send/sample",
            p256dh="a" * 87,
            auth="b" * 22,
            created_at=now - timedelta(days=1),
        )
    )
    portal_session.add(
        NotificationJobRecord(
            event_id=event.id,
            user_id=2,
            notification_type="event",
            scheduled_at=now - timedelta(seconds=1),
            payload={"event_name": "Service"},
            deduplication_key="push-check",
        )
    )
    await portal_session.commit()

    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        yield portal_session

    sender = Mock(side_effect=["retry", "sent"])
    monkeypatch.setattr(worker, "session_factory", sessions)
    monkeypatch.setattr(worker, "send_push", sender)
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: Settings(vapid_private_key=SecretStr("fake"), vapid_public_key="fake"),
    )

    # Act
    await worker.deliver_pending()
    delivery = await portal_session.scalar(select(PushDeliveryRecord))

    # Assert
    assert delivery is not None and delivery.attempts == 1 and delivery.status == "pending"
    assert sender.call_count == 1

    # Arrange
    delivery.retry_at = now - timedelta(seconds=1)
    await portal_session.commit()

    # Act
    await worker.deliver_pending()
    await worker.deliver_pending()

    # Assert
    assert delivery.status == "sent"
    assert sender.call_count == 2


async def test_templates_are_scoped_and_admin_managed(portal_session: AsyncSession) -> None:
    # Arrange
    from fastapi import HTTPException
    from worship_bot.api.routers.event_templates import (
        create_template,
        list_templates,
        update_template,
    )
    from worship_bot.api.schemas import EventRoleSlotCreate
    from worship_bot.api.template_schemas import EventTemplateData

    payload = EventTemplateData(
        name="  Evening  ",
        rehearsal_offset_minutes=120,
        additional_info="Song one\n\nSong two 🎵",
        role_slots=[EventRoleSlotCreate(ministry_role_id=1, user_ministry_role_id=1)],
    )

    # Act
    saved = await create_template(1, payload, 1, portal_session)
    templates = await list_templates(1, 2, portal_session)

    # Assert
    assert len(templates) == 5
    assert saved.name == "Evening"
    assert templates[-1].additional_info == "Song one\n\nSong two 🎵"
    assert templates[-1].role_slots[0].user_ministry_role_id == 1
    with pytest.raises(HTTPException) as error:
        await create_template(1, payload, 2, portal_session)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException):
        await update_template(2, saved.id, payload, 1, portal_session)


async def test_template_rejects_foreign_roles(portal_session: AsyncSession) -> None:
    # Arrange
    from fastapi import HTTPException
    from worship_bot.api.routers.event_templates import create_template
    from worship_bot.api.schemas import EventRoleSlotCreate
    from worship_bot.api.template_schemas import EventTemplateData

    payload = EventTemplateData(
        name="Invalid", role_slots=[EventRoleSlotCreate(ministry_role_id=999)]
    )

    # Act / Assert
    with pytest.raises(HTTPException) as error:
        await create_template(1, payload, 1, portal_session)
    assert error.value.status_code == 422


async def test_create_event_preserves_notes_rehearsal_and_assignments(
    portal_session: AsyncSession,
) -> None:
    # Arrange
    from worship_bot.api.routers.portal import create_calendar_event
    from worship_bot.api.schemas import EventRoleSlotCreate, EventSeriesCreate

    starts_at = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=5)
    notes = "Song one F\n\nSong two G 🎵\nC: G Em D | |"
    payload = EventSeriesCreate(
        event_name="Evening",
        starts_at=starts_at,
        rehearsal_at=starts_at - timedelta(hours=2),
        reminders_enabled=True,
        additional_info=notes,
        role_slots=[EventRoleSlotCreate(ministry_role_id=1, user_ministry_role_id=1)],
    )

    # Act
    created = await create_calendar_event(1, payload, 1, portal_session)

    # Assert
    assert len(created) == 1
    assert created[0].additional_info == notes
    assert created[0].rehearsal_at is not None
    assert created[0].rehearsal_at == starts_at - timedelta(hours=2)
    assert created[0].role_slots[0].user_ministry_role_id == 1
    jobs = list(await portal_session.scalars(select(NotificationJobRecord)))
    assert {job.notification_type for job in jobs} == {
        "event",
        "event_2h",
        "rehearsal",
        "rehearsal_2h",
    }


def test_event_rejects_rehearsal_after_start() -> None:
    # Arrange
    from pydantic import ValidationError
    from worship_bot.api.schemas import EventSeriesCreate

    starts_at = datetime(2026, 11, 1, tzinfo=UTC)

    # Act / Assert
    with pytest.raises(ValidationError):
        EventSeriesCreate(
            event_name="Service", starts_at=starts_at, rehearsal_at=starts_at + timedelta(hours=1)
        )


async def test_password_login_preserves_existing_identity(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    from worship_bot.infrastructure.models import WebCredentialRecord
    from worship_bot.infrastructure.passwords import verify_password

    payload = {"login": "Admin.Person", "password": "a-long-local-password-42"}
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    configured = await portal_http.put("/api/v1/auth/credentials", json=payload)
    await portal_http.post("/api/v1/auth/logout")
    wrong = await portal_http.post("/api/v1/auth/login", json={**payload, "password": "wrong"})
    login = await portal_http.post("/api/v1/auth/login", json=payload)
    profile = await portal_http.get("/api/v1/portal/me")
    record = await portal_session.get(WebCredentialRecord, 1)

    # Assert
    assert configured.status_code == 200
    assert configured.json()["login"] == "admin.person"
    assert wrong.status_code == 401
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]
    assert profile.json()["id"] == 1
    assert profile.json()["ministries"][0]["access_level"] == "admin"
    assert await portal_session.scalar(select(func.count()).select_from(UserRecord)) == 2
    assert record is not None and record.password_hash != payload["password"]
    assert verify_password(payload["password"], record.password_hash)


async def test_credentials_require_login_and_current_password(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    payload = {"login": "admin.person", "password": "a-long-local-password-42"}

    # Act
    anonymous = await portal_http.put("/api/v1/auth/credentials", json=payload)
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    await portal_http.put("/api/v1/auth/credentials", json=payload)
    change = await portal_http.put(
        "/api/v1/auth/credentials", json={**payload, "password": "a-new-local-password-43"}
    )

    # Assert
    assert anonymous.status_code == 401
    assert change.status_code == 403


async def test_password_login_throttles_repeated_failures(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    from worship_bot.infrastructure.models import WebCredentialRecord

    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    payload = {"login": "admin.person", "password": "a-long-local-password-42"}
    await portal_http.put("/api/v1/auth/credentials", json=payload)
    await portal_http.post("/api/v1/auth/logout")

    # Act
    for attempt in range(5):
        response = await portal_http.post(
            "/api/v1/auth/login", json={**payload, "password": "wrong"}
        )
        assert response.status_code == 401, f"Failed attempt {attempt + 1}"
    blocked = await portal_http.post("/api/v1/auth/login", json=payload)

    # Assert
    assert blocked.status_code == 429

    # Arrange
    record = await portal_session.get(WebCredentialRecord, 1)
    assert record is not None
    record.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await portal_session.commit()

    # Act
    success = await portal_http.post("/api/v1/auth/login", json=payload)

    # Assert
    assert success.status_code == 200
    assert record.failed_attempts == 0


async def test_login_is_unique_between_accounts(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    payload = {"login": "same-login", "password": "a-long-local-password-42"}
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    await portal_http.put("/api/v1/auth/credentials", json=payload)
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    duplicate = await portal_http.put("/api/v1/auth/credentials", json=payload)

    # Assert
    assert duplicate.status_code == 409
    assert (await portal_http.get("/api/v1/portal/me")).json()["id"] == 2


def test_password_hashes_use_distinct_salts() -> None:
    # Arrange
    from worship_bot.infrastructure.passwords import hash_password, verify_password

    password = "another-long-local-password"

    # Act
    first, second = hash_password(password), hash_password(password)

    # Assert
    assert first != second
    assert verify_password(password, first)
    assert not verify_password("incorrect", first)
    assert not verify_password(password, None)


async def test_site_registration_does_not_join_a_church(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    payload = {
        "name": "New",
        "surname": "Person",
        "login": "new.person",
        "password": "a-long-local-password-42",
        "consent_approved": True,
        "church_id": 1,
        "system_role": "developer",
    }

    # Act
    response = await portal_http.post("/api/v1/auth/register", json=payload)
    profile = await portal_http.get("/api/v1/portal/me")
    duplicate = await portal_http.post("/api/v1/auth/register", json=payload)
    user = await portal_session.get(UserRecord, profile.json()["id"])

    # Assert
    assert response.status_code == 201
    assert profile.json()["ministries"] == []
    assert user is not None and user.church_id is None and user.system_role == "member"
    assert duplicate.status_code == 409
    assert await portal_session.scalar(select(func.count()).select_from(UserRecord)) == 3


async def test_membership_requires_admin_approval(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    payload = {
        "name": "New",
        "surname": "Person",
        "login": "new.person",
        "password": "a-long-local-password-42",
        "consent_approved": True,
    }
    await portal_http.post("/api/v1/auth/register", json=payload)
    user_id = (await portal_http.get("/api/v1/portal/me")).json()["id"]

    # Act
    applied = await portal_http.post(
        "/api/v1/portal/ministries/1/applications",
        json={"role_ids": [1], "message": "I serve here"},
    )
    hidden = await portal_http.get("/api/v1/portal/ministries/1/members")
    listed = (await portal_http.get("/api/v1/portal/directory")).json()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    requests = (await portal_http.get("/api/v1/portal/ministries/1/applications")).json()
    decided = await portal_http.put(
        f"/api/v1/portal/ministries/1/applications/{requests[0]['id']}",
        json={"approve": True, "role_ids": [1], "access_level": "admin"},
    )
    await portal_http.post(
        "/api/v1/auth/login", json={"login": payload["login"], "password": payload["password"]}
    )
    profile = (await portal_http.get("/api/v1/portal/me")).json()
    people = (await portal_http.get("/api/v1/portal/ministries/1/members")).json()

    # Assert
    assert applied.status_code == 204
    assert hidden.status_code == 403
    assert listed[0]["teams"][0]["status"] == "pending"
    assert requests[0]["user_id"] == user_id
    assert decided.status_code == 204
    assert profile["id"] == user_id and profile["ministries"][0]["access_level"] == "member"
    assert next(person for person in people if person["id"] == user_id)["roles"][0]["id"] == 1
    assert (await portal_http.get("/api/v1/portal/ministries/1/applications")).status_code == 403


async def test_application_rejects_foreign_roles(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    response = await portal_http.post(
        "/api/v1/portal/ministries/999/applications", json={"role_ids": [1]}
    )
    cross_scope = await portal_http.get("/api/v1/portal/ministries/999/applications")

    # Assert
    assert response.status_code == 404
    assert cross_scope.status_code == 403


async def test_telegram_link_is_one_use_and_preserves_account(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    from urllib.parse import parse_qs, urlsplit

    from worship_bot.infrastructure.models import AccountLinkRecord

    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    issued = (await portal_http.post("/api/v1/portal/me/telegram-link")).json()
    code = parse_qs(urlsplit(issued["url"]).query)["start"][0].removeprefix("link_")
    payload = {
        "provider": "telegram",
        "external_user_id": "555",
        "username": "person",
        "code": code,
    }
    headers = {"Authorization": "Bearer unit-only-bot-service-token"}

    # Act
    linked = await portal_http.post("/api/v1/internal/bot/link", json=payload, headers=headers)
    replay = await portal_http.post("/api/v1/internal/bot/link", json=payload, headers=headers)
    state = (await portal_http.get("/api/v1/portal/me/accounts")).json()
    owner = await SqlPortalRepository(portal_session).external_user("telegram", "555")
    record = await portal_session.scalar(select(AccountLinkRecord))

    # Assert
    assert linked.status_code == 200 and "#code=" in linked.json()["url"]
    assert replay.status_code == 409
    assert state["telegram_linked"] is True
    assert owner == 1
    assert record is not None and code != record.code_hash and record.used_at is not None
    assert await portal_session.scalar(select(func.count()).select_from(UserRecord)) == 2


async def test_link_cannot_take_another_users_telegram(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
) -> None:
    # Arrange
    from urllib.parse import parse_qs, urlsplit

    portal_session.add(
        ExternalAccountRecord(
            user_id=2, provider="telegram", external_user_id="555", verified_at=datetime.now(UTC)
        )
    )
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    issued = (await portal_http.post("/api/v1/portal/me/telegram-link")).json()
    code = parse_qs(urlsplit(issued["url"]).query)["start"][0].removeprefix("link_")

    # Act
    result = await portal_http.post(
        "/api/v1/internal/bot/link",
        json={"provider": "telegram", "external_user_id": "555", "code": code},
        headers={"Authorization": "Bearer unit-only-bot-service-token"},
    )

    # Assert
    assert result.status_code == 409
    assert await SqlPortalRepository(portal_session).external_user("telegram", "555") == 2


async def test_admin_can_extend_roles_but_member_cannot(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    created = await portal_http.post("/api/v1/portal/ministries/1/roles", json={"name": "Танцы"})
    duplicate = await portal_http.post("/api/v1/portal/ministries/1/roles", json={"name": "Танцы"})
    catalog = await portal_http.get("/api/v1/portal/ministries/1/roles")
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    forbidden = await portal_http.post("/api/v1/portal/ministries/1/roles", json={"name": "Свет"})

    # Assert
    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert any(role["name"] == "Танцы" for role in catalog.json())
    assert forbidden.status_code == 403


async def test_bot_application_uses_linked_account_and_validates_roles(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    user = UserRecord(name="Applicant", surname="New", church_id=None)
    portal_session.add(user)
    await portal_session.flush()
    user_id = user.id
    portal_session.add(
        ExternalAccountRecord(
            user_id=user_id,
            provider="telegram",
            external_user_id="777",
            verified_at=datetime.now(UTC),
        )
    )
    await portal_session.commit()
    headers = {"Authorization": "Bearer unit-only-bot-service-token"}
    payload = {"provider": "telegram", "external_user_id": "777", "church_ministry_id": 1}

    # Act
    invalid = await portal_http.post(
        "/api/v1/internal/bot/applications", headers=headers, json={**payload, "role_ids": [999]}
    )
    valid = await portal_http.post(
        "/api/v1/internal/bot/applications",
        headers=headers,
        json={**payload, "role_ids": [1], "user_id": 1},
    )
    from worship_bot.infrastructure.models import MembershipRequestRecord

    request = await portal_session.scalar(select(MembershipRequestRecord))
    membership = await portal_session.scalar(
        select(MinistryMembershipRecord).where(MinistryMembershipRecord.user_id == user_id)
    )

    # Assert
    assert invalid.status_code == 422
    assert valid.status_code == 204
    assert request is not None and request.user_id == user_id and request.role_ids == [1]
    assert membership is None


async def test_admin_adds_first_event_participant_and_notification(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    event = EventRecord(
        event_name="Service",
        event_date=datetime.now(UTC) + timedelta(days=2),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.commit()
    event_id = event.id
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    created = await portal_http.post(
        f"/api/v1/portal/events/{event_id}/role-slots",
        json={"ministry_role_id": 1, "user_ministry_role_id": 1},
    )
    duplicate = await portal_http.post(
        f"/api/v1/portal/events/{event_id}/role-slots",
        json={"ministry_role_id": 1, "user_ministry_role_id": 1},
    )
    slots = list(
        await portal_session.scalars(
            select(EventRoleSlotRecord).where(EventRoleSlotRecord.event_id == event_id)
        )
    )
    notifications = list(
        await portal_session.scalars(
            select(NotificationJobRecord).where(NotificationJobRecord.event_id == event_id)
        )
    )

    # Assert
    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert len(slots) == 1 and slots[0].user_ministry_role_id == 1
    assert any(job.user_id == 2 and job.notification_type == "assignment" for job in notifications)


async def test_participant_assignment_rejects_unauthorized_and_foreign_roles(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    event = EventRecord(
        event_name="Service",
        event_date=datetime.now(UTC) + timedelta(days=2),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.commit()
    event_id = event.id
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    denied = await portal_http.post(
        f"/api/v1/portal/events/{event_id}/role-slots",
        json={"ministry_role_id": 1, "user_ministry_role_id": 1},
    )
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    invalid = await portal_http.post(
        f"/api/v1/portal/events/{event_id}/role-slots",
        json={"ministry_role_id": 999, "user_ministry_role_id": 1},
    )
    count = await portal_session.scalar(
        select(func.count())
        .select_from(EventRoleSlotRecord)
        .where(EventRoleSlotRecord.event_id == event_id)
    )

    # Assert
    assert denied.status_code == 403
    assert invalid.status_code == 422
    assert count == 0


async def test_assignments_confirm_in_telegram_and_request_replacement_on_website(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    event = EventRecord(
        event_name="Service",
        event_date=datetime.now(UTC) + timedelta(days=2),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    slot = EventRoleSlotRecord(event_id=event.id, ministry_role_id=1, user_ministry_role_id=1)
    portal_session.add_all(
        [
            slot,
            ExternalAccountRecord(
                user_id=2, provider="telegram", external_user_id="42", verified_at=datetime.now(UTC)
            ),
        ]
    )
    await portal_session.commit()
    slot_id = slot.id
    ticket = await SqlPortalRepository(portal_session).issue_login(2)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    listed = (await portal_http.get("/api/v1/portal/me/assignments")).json()
    stale = await portal_http.put(
        f"/api/v1/portal/me/assignments/{slot_id}", json={"accept": True, "revision": "0" * 20}
    )
    accepted = await portal_http.post(
        "/api/v1/internal/bot/assignments/respond",
        headers={"Authorization": "Bearer unit-only-bot-service-token"},
        json={
            "provider": "telegram",
            "external_user_id": "42",
            "slot_id": slot_id,
            "accept": True,
            "revision": listed[0]["revision"],
        },
    )
    updated = (await portal_http.get("/api/v1/portal/me/assignments")).json()
    declined = await portal_http.put(
        f"/api/v1/portal/me/assignments/{slot_id}",
        json={"accept": False, "revision": updated[0]["revision"]},
    )
    remaining = (await portal_http.get("/api/v1/portal/me/assignments")).json()

    # Assert
    assert listed[0]["role_name"] == "Vocal" and listed[0]["status"] == "pending"
    assert stale.status_code == 409
    assert accepted.status_code == 204 and updated[0]["status"] == "confirmed"
    assert declined.status_code == 204 and remaining[0]["status"] == "replacement"
    assert slot.user_ministry_role_id == 1


async def test_my_events_cannot_respond_for_another_person(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    from worship_bot.domain.notifications import assignment_revision

    event = EventRecord(
        event_name="Service",
        event_date=datetime.now(UTC) + timedelta(days=2),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    slot = EventRoleSlotRecord(event_id=event.id, ministry_role_id=1, user_ministry_role_id=1)
    portal_session.add(slot)
    await portal_session.commit()
    slot_id = slot.id
    revision = assignment_revision(slot.updated_at)
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    listed = await portal_http.get("/api/v1/portal/me/assignments")
    response = await portal_http.put(
        f"/api/v1/portal/me/assignments/{slot_id}", json={"accept": True, "revision": revision}
    )

    # Assert
    assert listed.json() == []
    assert response.status_code == 404
    assert slot.confirmation_status == "pending"


async def test_assignment_notification_contains_response_buttons_and_local_date(
    portal_http: AsyncClient, portal_session: AsyncSession
) -> None:
    # Arrange
    event = EventRecord(
        event_name="Service",
        event_date=datetime(2026, 11, 4, 6, tzinfo=UTC),
        church_id=1,
        church_ministry_id=1,
    )
    portal_session.add(event)
    await portal_session.flush()
    portal_session.add(
        ExternalAccountRecord(
            user_id=2, provider="telegram", external_user_id="42", verified_at=datetime.now(UTC)
        )
    )
    await portal_session.commit()
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})

    # Act
    created = await portal_http.post(
        f"/api/v1/portal/events/{event.id}/role-slots",
        json={"ministry_role_id": 1, "user_ministry_role_id": 1},
    )
    jobs = await claim_notifications(portal_session)

    # Assert
    assert created.status_code == 201
    assert jobs[0].assignment_slot_id == created.json()["id"]
    assert jobs[0].assignment_revision and len(jobs[0].assignment_revision) == 20
    assert "4 ноября 2026, 10:00" in jobs[0].text
    assert "T06:00" not in jobs[0].text and "Ваша роль: Vocal" in jobs[0].text


async def test_assistant_shows_provider_error_without_losing_chat(
    portal_http: AsyncClient,
    portal_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    from worship_bot.application.exceptions import PlanningProviderError
    from worship_bot.infrastructure.models.portal import AssistantSessionRecord

    async def unavailable(*args: Any, **kwargs: Any) -> None:
        raise PlanningProviderError("Достигнут временный лимит OpenAI", "rate_limit_exceeded")

    monkeypatch.setattr("worship_bot.api.routers.planning.generate_proposal", unavailable)
    ticket = await SqlPortalRepository(portal_session).issue_login(1)
    await portal_http.post("/api/v1/auth/exchange", json={"code": ticket.code})
    created = await portal_http.post(
        "/api/v1/portal/assistant/sessions", json={"ministry_id": 1, "month": "2026-11"}
    )
    session_id = created.json()["id"]

    # Act
    response = await portal_http.post(
        f"/api/v1/portal/assistant/sessions/{session_id}/messages",
        json={"message": "Составь расписание"},
    )
    record = await portal_session.get(AssistantSessionRecord, session_id)

    # Assert
    assert response.status_code == 503
    assert "временный лимит" in response.json()["detail"]
    assert record is not None and record.messages == [] and record.proposal is None
