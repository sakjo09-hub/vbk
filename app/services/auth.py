from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User, Transaction
from app.services.security import hash_password, verify_password


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def register_user(db: AsyncSession, username: str, email: str, password: str) -> User:
    starting_balance = settings.VIRTUAL_STARTING_BALANCE
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        balance=starting_balance,
    )
    db.add(user)
    await db.flush()

    tx = Transaction(
        user_id=user.id,
        type="bonus",
        amount=starting_balance,
        balance_after=starting_balance,
        reference="starting_balance",
    )
    db.add(tx)
    await db.commit()
    await db.refresh(user)
    return user
