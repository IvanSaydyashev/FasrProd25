from fastapi import APIRouter, Depends, Security
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core import token
from app.core.password import hash_password, verify_password
from app.db.session import get_db, redis_client
from app.models.user_auth import UserBase, User, UserSignin, UserPatch

router = APIRouter()


@router.get("/profile",
            tags=["Получение профиля пользователя"],
            description="Возвращает данные профиля текущего пользователя.")
async def profile(token_context: str = Security(token.get_token),
                  db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса."
        })
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={
            "status": "error",
            "message": "Пользователь не авторизован."
        })
    user_id = token.get_token_info(token_context, "_id")
    user = db.query(User).filter(User.user_id == user_id).first()
    return JSONResponse(content=user.to_dict())


@router.patch("/profile",
              tags=["Изменение настроек пользователя"],
              description="Обновляет настройки текущего пользователя. Если указан новый пароль,"
                          " следующие попытки аутентификации должны учитывать обновленное значение."
                          " Смена пароля не инвалидирует токен. Если значение поля не было передано (или передан null), не обновляйте данное поле.")
async def patch_profile(patch_data: UserPatch,
                 token_context: str = Security(token.get_token),
                 db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса."
        })
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={
            "status": "error",
            "message": "Пользователь не авторизован."
        })
    user = db.query(User).get(token.get_token_info(token_context, "_id"))
    print(patch_data)
    update_data = {key: value for key, value in patch_data.dict().items() if value is not None}
    if "password" in update_data:
        update_data["password"] = hash_password(update_data["password"])
    for key, value in update_data.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return JSONResponse(content=user.to_dict())
