from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import BetCreate, BetOut
from app.services.betting import BettingError, list_user_bets, place_bet
from app.api.deps import get_current_user

router = APIRouter(prefix="/bets", tags=["bets"])


@router.post("", response_model=BetOut, status_code=201)
async def create_bet(
    payload: BetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        bet = await place_bet(db, current_user, payload.selection_id, payload.amount)
    except BettingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return bet


@router.get("", response_model=list[BetOut])
async def my_bets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_user_bets(db, current_user.id)
