from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, User


async def debit(db: AsyncSession, user: User, amount: Decimal, reference: str | None = None) -> Transaction:
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    if user.balance < amount:
        raise ValueError("Недостаточно виртуальной валюты")
    user.balance -= amount
    tx = Transaction(
        user_id=user.id,
        type="bet",
        amount=-amount,
        balance_after=user.balance,
        reference=reference,
    )
    db.add(tx)
    await db.flush()
    return tx


async def credit(db: AsyncSession, user: User, amount: Decimal, tx_type: str = "payout", reference: str | None = None) -> Transaction:
    if amount < 0:
        raise ValueError("Сумма не может быть отрицательной")
    user.balance += amount
    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        balance_after=user.balance,
        reference=reference,
    )
    db.add(tx)
    await db.flush()
    return tx


async def list_transactions(db: AsyncSession, user_id: int, limit: int = 50) -> list[Transaction]:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
