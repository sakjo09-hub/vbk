from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import BalanceOut, TransactionOut
from app.services.wallet import list_transactions
from app.api.deps import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/balance", response_model=BalanceOut)
async def balance(current_user: User = Depends(get_current_user)):
    return BalanceOut(balance=current_user.balance, currency_code=settings.VIRTUAL_CURRENCY_CODE)


@router.get("/transactions", response_model=list[TransactionOut])
async def transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_transactions(db, current_user.id)
