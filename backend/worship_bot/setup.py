import argparse
import asyncio
import secrets
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.config import get_settings
from worship_bot.domain.worship_roles import WORSHIP_ROLES
from worship_bot.infrastructure.database import engine, session_factory
from worship_bot.infrastructure.models import (
    ChurchMembershipRecord,
    ChurchMinistryRecord,
    ChurchRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    UserRecord,
)
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository


async def create_first_admin(
    session: AsyncSession,
    name: str,
    surname: str,
    church_name: str,
    ministry_name: str,
) -> int:
    await session.execute(select(func.pg_advisory_xact_lock(74180621)))
    if await session.scalar(select(UserRecord.id).limit(1)) is not None:
        raise ValueError(
            "Первоначальная настройка уже выполнена. Используйте --login ID для входа."
        )
    church = await session.scalar(select(ChurchRecord).where(ChurchRecord.name == church_name))
    if church is None:
        church = ChurchRecord(name=church_name)
        session.add(church)
        await session.flush()
    ministry_type = await session.scalar(
        select(MinistryTypeRecord).where(
            func.lower(MinistryTypeRecord.name) == ministry_name.casefold()
        )
    )
    if ministry_type is None:
        ministry_type = MinistryTypeRecord(code=secrets.token_hex(12), name=ministry_name)
        session.add(ministry_type)
        await session.flush()
    ministry = await session.scalar(
        select(ChurchMinistryRecord).where(
            ChurchMinistryRecord.church_id == church.id,
            ChurchMinistryRecord.ministry_type_id == ministry_type.id,
        )
    )
    if ministry is None:
        ministry = ChurchMinistryRecord(church_id=church.id, ministry_type_id=ministry_type.id)
        session.add(ministry)
        await session.flush()
    user = UserRecord(name=name, surname=surname, church_id=church.id, system_role="member")
    session.add(user)
    await session.flush()
    session.add(ChurchMembershipRecord(church_id=church.id, user_id=user.id, access_level="admin"))
    session.add(
        MinistryMembershipRecord(
            church_ministry_id=ministry.id,
            user_id=user.id,
            access_level="admin",
        )
    )
    existing_roles = set(
        await session.scalars(
            select(MinistryRoleRecord.name).where(
                MinistryRoleRecord.church_ministry_id == ministry.id
            )
        )
    )
    for code, role in WORSHIP_ROLES:
        if role in existing_roles:
            continue
        session.add(
            MinistryRoleRecord(
                church_ministry_id=ministry.id,
                code=code,
                name=role,
            )
        )
    await session.commit()
    return user.id


def ask(label: str, limit: int) -> str:
    value = input(label + ": ").strip()
    if not value or len(value) > limit:
        raise ValueError(f"Введите от 1 до {limit} символов")
    return value


async def run(user_id: int | None) -> None:
    try:
        async with session_factory() as session:
            if user_id is None:
                user_id = await create_first_admin(
                    session,
                    ask("Имя", 100),
                    ask("Фамилия", 100),
                    ask("Название церкви", 150),
                    ask("Название служения", 150),
                )
            if await session.get(UserRecord, user_id) is None:
                raise ValueError("Пользователь не найден")
            ticket = await SqlPortalRepository(session).issue_login(user_id)
            url = get_settings().web_url.rstrip("/") + "/#" + urlencode({"code": ticket.code})
            print(f"Пользователь № {user_id}. Одноразовая ссылка действует 5 минут:\n{url}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Первоначальная настройка и локальный вход")
    parser.add_argument("--login", type=int, help="Выдать ссылку существующему пользователю")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.login))
    except ValueError as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
