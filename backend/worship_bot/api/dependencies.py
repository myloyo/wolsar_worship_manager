from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.services import (
    ChurchService,
    EventCalendarService,
    MinistryService,
    ParticipantService,
    RegistrationService,
    ScheduleService,
)
from worship_bot.application.services.events import EventLifecycleService
from worship_bot.config import Settings, get_settings
from worship_bot.infrastructure.database import get_session
from worship_bot.infrastructure.repositories.churches import SqlChurchRepository
from worship_bot.infrastructure.repositories.event_lifecycle import SqlEventLifecycleRepository
from worship_bot.infrastructure.repositories.events import (
    SqlEventCalendarRepository,
    SqlScheduleRepository,
)
from worship_bot.infrastructure.repositories.identity import SqlIdentityRepository
from worship_bot.infrastructure.repositories.ministries import SqlMinistryRepository
from worship_bot.infrastructure.repositories.participants import SqlParticipantRepository


async def get_event_lifecycle_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventLifecycleService:
    return EventLifecycleService(
        SqlEventLifecycleRepository(session), SqlMinistryRepository(session)
    )


async def get_services(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[tuple[ChurchService, ParticipantService, ScheduleService]]:
    church_repository = SqlChurchRepository(session)
    yield (
        ChurchService(church_repository),
        ParticipantService(SqlParticipantRepository(session), church_repository),
        ScheduleService(SqlScheduleRepository(session), church_repository),
    )


async def get_event_calendar_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventCalendarService:
    return EventCalendarService(SqlEventCalendarRepository(session))


async def get_registration_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegistrationService:
    draft_lifetime = timedelta(minutes=settings.registration_draft_lifetime_minutes)
    identity_repository = SqlIdentityRepository(
        session,
        draft_lifetime,
        settings.initial_developer_provider,
        settings.initial_developer_external_user_id,
    )
    return RegistrationService(
        identity_repository,
        SqlMinistryRepository(session),
        SqlChurchRepository(session),
        settings.registration_consent_version,
        draft_lifetime,
    )


async def get_ministry_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MinistryService:
    return MinistryService(SqlMinistryRepository(session), SqlChurchRepository(session))
