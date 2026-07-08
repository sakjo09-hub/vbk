from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, DateTime, Integer, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TZDateTime


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    bets: Mapped[list["Bet"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_event_id: Mapped[str] = mapped_column(String(128), index=True)
    tournament: Mapped[str] = mapped_column(String(255), default="")
    home_team: Mapped[str] = mapped_column(String(255))
    away_team: Mapped[str] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(TZDateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default="upcoming", index=True)
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())

    markets: Mapped[list["Market"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))

    event: Mapped["Event"] = relationship(back_populates="markets")
    selections: Mapped[list["Selection"]] = relationship(back_populates="market", cascade="all, delete-orphan")


class Selection(Base):
    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), index=True)
    outcome: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    odds: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    status: Mapped[str] = mapped_column(String(16), default="open")

    market: Mapped["Market"] = relationship(back_populates="selections")
    bets: Mapped[list["Bet"]] = relationship(back_populates="selection")


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    odds: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    potential_payout: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    payout: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="bets")
    selection: Mapped["Selection"] = relationship(back_populates="bets")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")
