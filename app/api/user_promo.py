from datetime import timezone, datetime
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.core import token
from app.db.session import get_db, redis_client
from app.models.business_promo import PromoCode, Target, PromoComments, PromoCommentBase, PromoActions, \
    PromoCodeStatistics
from app.models.user_auth import User
from app.api.antifraud import call_antifraud
router = APIRouter()


@router.get("/feed",
            tags=["Получение ленты промокодов"],
            description="Возвращает ленту промокодов с поддержкой пагинации, фильтрации и сортировки."
                        " Возвращаются промокоды, которые соответствуют настройкам таргетинга. Промокоды отсортированы по убыванию даты создания.")
async def get_feed(
        category: Optional[str] = Query(None, description="Категория промокодов"),
        active: Optional[bool] = Query(None, description="Фильтрация по активности"),
        limit: int = Query(10, ge=0, description="Максимальное количество записей"),
        offset: int = Query(0, ge=0, description="Сдвиг от начала выборки"),
        token_context: str = Depends(token.get_token),
        db: Session = Depends(get_db)
):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    user = db.query(User).get(token.get_token_info(token_context, "_id"))

    promo_query = db.query(PromoCode)

    if active is not None:
        promo_query = promo_query.filter(PromoCode.active == active)

    filtered_promo_codes = []
    promo_codes = reversed(promo_query.all())

    for promo in promo_codes:
        target = promo.target

        age_from = target.get("age_from", 0)
        age_until = target.get("age_until", 100)
        country = target.get("country", "")
        categories = target.get("categories", [])

        if age_from <= user.other["age"] <= age_until and (
                country.lower() == user.other["country"].lower() or country == ""):
            if category:
                for cat in categories:
                    if cat.lower() == category.lower():
                        filtered_promo_codes.append(promo)
            else:
                filtered_promo_codes.append(promo)

    user_promo_actions = db.query(PromoActions).filter(PromoActions.user_id == user.user_id).all()
    promo_actions = {pa.promo_id: pa for pa in user_promo_actions}

    paginated_promo_codes = filtered_promo_codes[offset:offset + limit]

    total_count = len(filtered_promo_codes)
    headers = {"x-total-count": str(total_count)}
    response = []
    for promo in paginated_promo_codes:
        new_dict = {
            "promo_id": str(promo.promo_id),
            "company_id": str(promo.company_id),
            "company_name": promo.company_name,
            "description": promo.description,
            "image_url": promo.image_url,
            "active": promo.active,
            "is_activated_by_user": promo_actions.get(promo.promo_id,
                                                      PromoActions()).is_activated_by_user if promo_actions.get(
                promo.promo_id) else False,
            "like_count": promo.like_count,
            "is_liked_by_user": promo_actions.get(promo.promo_id,
                                                  PromoActions()).is_liked_by_user if promo_actions.get(
                promo.promo_id) else False,
            "comment_count": promo.comment_count,
        }
        new_dict = delete_none(new_dict)
        response.append(new_dict)

    return JSONResponse(content=response, headers=headers)


@router.get("/promo/{id}", tags=["Просмотр промокода по id"], description="Возвращает промокод с этим id")
async def get_promo(
        id: str,
        token_context: str = Depends(token.get_token),
        db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})

    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    promo = db.query(PromoCode).filter(PromoCode.promo_id == id).first()
    if not promo:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Промокод не найден."})

    user_id = token.get_token_info(token_context, "_id")
    user_promo_actions = db.query(PromoActions).filter_by(user_id=user_id, promo_id=promo.promo_id).first()

    is_activated_by_user = user_promo_actions.is_activated_by_user if user_promo_actions else False
    is_liked_by_user = user_promo_actions.is_liked_by_user if user_promo_actions else False

    response = {
        "promo_id": str(promo.promo_id),
        "company_id": str(promo.company_id),
        "company_name": promo.company_name,
        "description": promo.description,
        "image_url": promo.image_url,
        "active": promo.active,
        "is_activated_by_user": is_activated_by_user,
        "like_count": promo.like_count,
        "is_liked_by_user": is_liked_by_user,
        "comment_count": promo.comment_count,
    }

    return JSONResponse(content=delete_none(response))


@router.post("/promo/{id}/like",
             tags=["Добавить лайк к промокоду"],
             description="Добавляет лайк к указанному промокоду. Повторный лайк не изменяет состояния, возвращается успешный ответ.")
def like_promo(id: str,
               token_context: str = Depends(token.get_token),
               db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    promo = db.query(PromoCode).get(id)
    if not promo:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Промокод не найден."})
    user = db.query(User).filter(User.user_id == token.get_token_info(token_context, "_id")).first()
    promo_action = db.query(PromoActions).filter(PromoActions.user_id == user.user_id).first()

    if not promo_action:
        new_promo_action = PromoActions(
            promo_id=id,
            user_id=user.user_id,
            is_activated_by_user=False,
            is_liked_by_user=True
        )
        setattr(promo, "like_count", promo.like_count + 1)

        db.add(new_promo_action)
        db.commit()
        db.refresh(new_promo_action)

        db.add(promo)
        db.commit()
        db.refresh(promo)
    elif not promo_action.is_liked_by_user:
        setattr(promo_action, "is_liked_by_user", True)
        setattr(promo, "like_count", promo.like_count + 1)

        db.add(promo)
        db.commit()
        db.refresh(promo)

        db.add(promo_action)
        db.commit()
        db.refresh(promo_action)

    return JSONResponse(content={"status": "ok"})


@router.delete("/promo/{id}/like",
               tags=["Удалить лайк с промокода"],
               description="Удаляет лайк с указанного промокода. Если лайк не стоит, возвращается успешный ответ.")
async def dislike_promo(id: str,
                        token_context: str = Depends(token.get_token),
                        db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    promo = db.query(PromoCode).get(id)
    if not promo:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Промокод не найден."})
    user = db.query(User).filter(User.user_id == token.get_token_info(token_context, "_id")).first()
    promo_action = db.query(PromoActions).filter(PromoActions.user_id == user.user_id).first()

    if not promo_action:
        new_promo_action = PromoActions(
            promo_id=id,
            user_id=user.user_id,
            is_activated_by_user=False,
            is_liked_by_user=False
        )

        db.add(new_promo_action)
        db.commit()
        db.refresh(new_promo_action)
    elif promo_action.is_liked_by_user:
        setattr(promo_action, "is_liked_by_user", False)
        setattr(promo, "like_count", promo.like_count - 1)

        db.add(promo)
        db.commit()
        db.refresh(promo)

        db.add(promo_action)
        db.commit()
        db.refresh(promo_action)

    return JSONResponse(content={"status": "ok"})


@router.post("/promo/{id}/comments",
             tags=["Добавить комментарий к промокоду"],
             description="Добавляет комментарий к указанному промокоду."
                         " Пользователь может оставить несколько комментариев к одному и тому же промокоду.")
async def comment_promo(id: str,
                        PromoComment: PromoCommentBase,
                        token_context: str = Depends(token.get_token),
                        db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    promo = db.query(PromoCode).get(id)
    if not promo:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Промокод не найден."})
    user = db.query(User).filter(User.user_id == token.get_token_info(token_context, "_id")).first()

    promo_action = db.query(PromoActions).filter(PromoActions.user_id == user.user_id).first()

    if not promo_action:
        new_promo_action = PromoActions(
            promo_id=str(id),
            user_id=str(user.user_id),
            is_activated_by_user=False,
            is_liked_by_user=False
        )
        promo_action = new_promo_action
        db.add(promo_action)
        db.commit()
        db.refresh(promo_action)

    author = {
        "name": user.name,
        "surname": user.surname,
        "avatar_url": user.avatar_url
    }

    new_promo_comment = PromoComments(
        promo_id=str(id),
        user_id=str(user.user_id),
        text=PromoComment.text,
        author=author,
    )

    setattr(promo, "comment_count", promo.comment_count + 1)

    db.add(promo)
    db.commit()
    db.refresh(promo)

    db.add(new_promo_comment)
    db.commit()
    db.refresh(new_promo_comment)

    response = {
        "id": str(new_promo_comment.comment_id),
        "text": str(new_promo_comment.text),
        "date": str(new_promo_comment.comment_date) + ":00",
        "author": new_promo_comment.author,
    }

    return JSONResponse(status_code=201, content=delete_none(response))


@router.get("/promo/{id}/comments",
            tags=["Получить комментарии к промокоду"],
            description="Возвращает список комментариев к указанному промокоду."
                        " Комментарии отсортированы по убыванию даты публикации.")
async def comment_promo_id(id: str,
                           limit: int = 10,
                           offset: int = 0,
                           token_context: str = Depends(token.get_token),
                           db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    promo = db.query(PromoCode).get(id)
    if not promo:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Промокод не найден."})

    query = db.query(PromoComments).filter(PromoComments.promo_id == id)

    comments = query.order_by(desc("comment_date")).offset(offset).limit(limit).all()

    response = []
    for comment in comments:
        author = {
            "name": comment.author.get("name"),
            "surname": comment.author.get("surname"),
            "avatar_url": comment.author.get("avatar_url") if comment.author.get("avatar_url") else None,
        }
        author = delete_none(author)
        resp = {
            "id": str(comment.comment_id),
            "text": str(comment.text),
            "date": str(comment.comment_date) + ":00",
            "author": author,
        }
        resp = delete_none(resp)
        response.append(resp)
    total_count = query.count()

    headers = {"x-total-count": str(total_count)}
    return JSONResponse(status_code=200, content=response, headers=headers)


@router.get("/promo/{id}/comments/{comment_id}",
            tags=["Получить комментарий к промокоду"],
            description="Возвращает комментарий с данным ID.")
async def comment_id_promo_id(id: str,
                              comment_id: str,
                              token_context: str = Depends(token.get_token),
                              db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    comment = db.query(PromoComments).filter_by(comment_id=comment_id, promo_id=id).first()
    if not comment:
        return JSONResponse(status_code=404,
                            content={"status": "error", "message": "Такого промокода или комментария не существует."})

    response = {
        "id": str(comment.comment_id),
        "text": str(comment.text),
        "date": str(comment.comment_date) + ":00",
        "author": comment.author
    }

    return JSONResponse(content=delete_none(response))


@router.put("/promo/{id}/comments/{comment_id}",
            tags=["Получить комментарий к промокоду"],
            description="Возвращает комментарий с данным ID.")
async def comment_id_promo_id(id: str,
                              comment_id: str,
                              new_comment_text: PromoCommentBase,
                              token_context: str = Depends(token.get_token),
                              db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})

    comment = db.query(PromoComments).filter_by(comment_id=comment_id, promo_id=id).first()
    if not comment:
        return JSONResponse(status_code=404,
                            content={"status": "error", "message": "Такого промокода или комментария не существует."})

    user_id = token.get_token_info(token_context, "_id")
    comment_user_id = str(comment.user_id)
    if user_id != comment_user_id:
        return JSONResponse(status_code=403,
                            content={"status": "error", "message": "Комментарий не принадлежит пользователю."})

    setattr(comment, "text", new_comment_text.text)

    db.add(comment)
    db.commit()
    db.refresh(comment)

    response = {
        "id": str(comment.comment_id),
        "text": str(comment.text),
        "date": str(comment.comment_date) + ":00",
        "author": comment.author
    }

    return JSONResponse(content=delete_none(response))


@router.delete("/promo/{id}/comments/{comment_id}",
               tags=["Удалить комментарий"],
               description="Удалить комментарий с данным ID.")
async def delete_comment_promo_id(id: str,
                                  comment_id: str,
                                  token_context: str = Depends(token.get_token),
                                  db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})
    promo = db.query(PromoCode).filter_by(promo_id=id).first()
    comment = db.query(PromoComments).filter_by(comment_id=comment_id, promo_id=id).first()
    if not comment:
        return JSONResponse(status_code=404,
                            content={"status": "error", "message": "Такого промокода или комментария не существует."})

    user_id = token.get_token_info(token_context, "_id")
    comment_user_id = str(comment.user_id)
    if user_id != comment_user_id:
        return JSONResponse(status_code=403,
                            content={"status": "error", "message": "Комментарий не принадлежит пользователю."})
    setattr(promo, "comment_count", promo.comment_count - 1)

    db.add(promo)
    db.commit()
    db.refresh(promo)

    db.delete(comment)
    db.commit()

    return {"status": "ok"}

@router.post("/promo/{id}/activate")
async def promo_activate(id: str,
                         token_context: str = Depends(token.get_token),
                         db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Ошибка в данных запроса."})
    if not token.check_valid_user_token(token_context):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Пользователь не авторизован."})
    promo = db.query(PromoCode).filter_by(promo_id=id).first()
    if not promo:
        return JSONResponse(status_code=404,
                            content={"status": "error", "message": "Промокод не найден."})

    user_id = token.get_token_info(token_context, "_id")
    user = db.query(User).filter_by(user_id=user_id).first()
    user_email = user.email
    promo_id = id

    # cache_data = redis_client.get(f"antifraud:promo:{promo_id}:user:{user_id}")
    # if not cache_data["ok"]:
    #     antifraud_data = await call_antifraud({"user_email": user_email, "promo_id": promo_id})
    # else:
    #     antifraud_data = cache_data["data"]
    # if not antifraud_data:
    #     return JSONResponse(status_code=403,
    #                         content={"message": "Вы не можете использовать этот промокод."})
    #
    # cache_until = antifraud_data.get("cache_until", datetime.now(timezone.utc))
    # if cache_until > datetime.now(timezone.utc):
    # redis_client.setex(f"antifraud:promo:{promo_id}:user:{user_id}", cache_until, 3600)

    return JSONResponse(content=antifraud_data)

def delete_none(data):
    data = {key: value for key, value in data.items() if value not in [None, "None"]}
    return data

