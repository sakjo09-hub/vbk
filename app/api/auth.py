from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.services import auth
from app.services.security import create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    if await auth.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    if await auth.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Имя пользователя занято")
    user = await auth.register_user(db, payload.username, payload.email, payload.password)
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await auth.authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    token = create_access_token(str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
