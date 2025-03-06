import os
import uuid
from fastapi import APIRouter, Depends, Security, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, cast, func
from sqlalchemy.orm import Session
from app.core import token
from app.core.password import hash_password, verify_password
from app.db.session import get_db, redis_client
from app.models.user_auth import UserBase, User, UserSignin

router = APIRouter()


@router.post("/auth/sign-up",
             tags=["Регистрация нового пользователя"],
             description="Регистрирует нового пользователя и возвращает токен доступа.")
async def sign_up(user: UserBase, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        return JSONResponse(
            status_code=409,
            content={
                "status": "error",
                "message": "Такой email уже зарегистрирован."})
    hashed_password = hash_password(user.password)
    new_user = User(
        user_id=uuid.uuid4(),
        password=hashed_password,
        name=user.name,
        surname=user.surname,
        email=user.email,
        avatar_url=str(user.avatar_url),
        other=user.other.dict()
    )
    token_context = token.generate_user_token(new_user)
    redis_key = f"user_token:{new_user.user_id}"
    redis_client.setex(redis_key, 3600 * 24, token_context)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "token": token_context
    }

@router.post("/auth/sign-in",
             tags=["Аутентификация пользователя"],
             description="Вход пользователя по email и паролю для получения токена доступа."
                         " Успешная аутентификация инвалидирует ранее выданные токены (запросы по ним станут невозможны). HardPa$$w0rd!iamthewinner")
async def sign_in(user: UserSignin, db: Session = Depends(get_db)):
    exist_user = db.query(User).filter(User.email == user.email).first()
    if exist_user and verify_password(user.password, exist_user.password):
        company_id = str(exist_user.user_id)
        redis_client.delete(f"user_token:{company_id}")
        token_context = token.generate_user_token(exist_user)
        redis_key = f"user_token:{exist_user.user_id}"
        redis_client.setex(redis_key, 3600 * 24, token_context)
        return {"token": token_context}
    else:
        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "message": "Неверный email или пароль."
            }
        )