from typing import Annotated
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select

from worship_bot.api.routers.portal import (
    Configuration,
    CurrentUser,
    Session,
    require_portal_permission,
)
from worship_bot.api.schemas import ApplyProposal, AssistantChat, AssistantCreate, AssistantRead
from worship_bot.application.exceptions import PlanningProviderError
from worship_bot.application.services.planning import validate_proposal
from worship_bot.infrastructure.history_files import MAX_UPLOAD_BYTES, history_content
from worship_bot.infrastructure.models.portal import AssistantSessionRecord
from worship_bot.infrastructure.openai_planner import generate_proposal
from worship_bot.infrastructure.repositories.planning import SqlPlanningRepository

router = APIRouter(prefix="/portal/assistant", tags=["scheduling assistant"])


def assistant_read(record: AssistantSessionRecord) -> AssistantRead:
    return AssistantRead(
        id=record.id,
        month=record.month,
        messages=record.messages,
        proposal=record.proposal,
        revision=record.revision,
        attachment_count=len(record.attachments),
    )


@router.post("/sessions", response_model=AssistantRead)
async def create_session(
    payload: AssistantCreate, user_id: CurrentUser, session: Session
) -> AssistantRead:
    await require_portal_permission(session, user_id, payload.ministry_id, "use_assistant")
    record = await SqlPlanningRepository(session).create(
        user_id, payload.ministry_id, payload.month
    )
    return assistant_read(record)


@router.post("/sessions/{session_id}/files", response_model=AssistantRead)
async def upload_history(
    session_id: str, user_id: CurrentUser, session: Session, file: Annotated[UploadFile, File()]
) -> AssistantRead:
    try:
        record = await SqlPlanningRepository(session).get(session_id, user_id)
        await require_portal_permission(
            session, user_id, record.church_ministry_id, "use_assistant"
        )
        if len(record.attachments) >= 4:
            raise ValueError("Не более четырёх файлов в диалоге")
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        record.attachments = [*record.attachments, history_content(file.filename or "", content)]
        record.proposal = None
        record.revision += 1
        await session.commit()
        return assistant_read(record)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except (ValueError, OSError, BadZipFile, InvalidFileException, ParseError) as error:
        await session.rollback()
        raise HTTPException(422, "Не удалось прочитать файл. Проверьте формат и размер") from error
    finally:
        await file.close()


@router.post("/sessions/{session_id}/messages", response_model=AssistantRead)
async def chat(
    session_id: str,
    payload: AssistantChat,
    user_id: CurrentUser,
    session: Session,
    settings: Configuration,
) -> AssistantRead:
    repository = SqlPlanningRepository(session)
    try:
        record = await repository.get(session_id, user_id)
        await require_portal_permission(
            session, user_id, record.church_ministry_id, "use_assistant"
        )
        if len(record.messages) >= 40:
            raise ValueError("Диалог слишком длинный. Начните новый")
        context = await repository.context(record.church_ministry_id, record.month)
        messages: list[dict[str, object]] = [
            *record.messages,
            {"role": "user", "content": payload.message},
        ]
        proposal = await generate_proposal(settings, context, messages, record.attachments)
        validate_proposal(proposal, record.month, context["members"], context["events"])
        record.messages = [*messages, {"role": "assistant", "content": proposal.model_dump_json()}]
        record.proposal = proposal.model_dump(mode="json")
        record.revision += 1
        await session.commit()
        return assistant_read(record)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PlanningProviderError as error:
        await session.rollback()
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        await session.rollback()
        raise HTTPException(422, str(error)) from error
    except (httpx.HTTPError, RuntimeError) as error:
        await session.rollback()
        raise HTTPException(
            502, "Модель недоступна. Проверьте OPENAI_MODEL, новый API-ключ и доступ проекта"
        ) from error


@router.post("/sessions/{session_id}/apply")
async def apply(
    session_id: str, payload: ApplyProposal, user_id: CurrentUser, session: Session
) -> dict[str, list[int]]:
    repository = SqlPlanningRepository(session)
    try:
        record = await repository.get(session_id, user_id)
        await require_portal_permission(
            session, user_id, record.church_ministry_id, "use_assistant"
        )
        return {"event_ids": await repository.apply(record, payload.revision)}
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error


@router.get("/sessions", response_model=AssistantRead | None)
async def latest_session(
    user_id: CurrentUser,
    session: Session,
    ministry_id: int,
    month: Annotated[str, Query(pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")],
) -> AssistantRead | None:
    await require_portal_permission(session, user_id, ministry_id, "use_assistant")
    record = await session.scalar(
        select(AssistantSessionRecord)
        .where(
            AssistantSessionRecord.user_id == user_id,
            AssistantSessionRecord.church_ministry_id == ministry_id,
            AssistantSessionRecord.month == month,
            AssistantSessionRecord.applied_at.is_(None),
        )
        .order_by(AssistantSessionRecord.created_at.desc())
        .limit(1)
    )
    return assistant_read(record) if record is not None else None
