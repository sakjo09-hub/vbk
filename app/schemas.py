from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr
    balance: Decimal
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SelectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    outcome: str
    label: str
    odds: Decimal
    status: str


class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    label: str
    selections: list[SelectionOut]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sport: str
    tournament: str = ""
    home_team: str
    away_team: str
    starts_at: datetime
    status: str
    result: Optional[str] = None
    markets: list[MarketOut] = []


class BetCreate(BaseModel):
    selection_id: int
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class BetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    selection_id: int
    amount: Decimal
    odds: Decimal
    status: str
    potential_payout: Decimal
    payout: Optional[Decimal] = None
    created_at: datetime
    settled_at: Optional[datetime] = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    amount: Decimal
    balance_after: Decimal
    reference: Optional[str] = None
    created_at: datetime


class BalanceOut(BaseModel):
    balance: Decimal
    currency_code: str


class MessageOut(BaseModel):
    detail: str
