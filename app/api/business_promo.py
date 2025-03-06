import uuid
from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, Security, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from app.core import token
from app.db.session import get_db
from app.models.business_promo import PromoCode, PromoCodeCreate, PromoCodeBase, PromoCodeStatistics, \
    PatchPromoCode

router = APIRouter()


@router.post("/promo",
             tags=["Создание нового промокода"],
             description="Создает новый промокод для компании с настройкой таргетинга и типа промокодов.")
async def create_promo_code(promo_data: PromoCodeCreate,
                            token_context: str = Depends(token.get_token),
                            db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса. token"
        })
    if not token.check_valid_company_token(token_context):
        return JSONResponse(status_code=401, content={
            "status": "error",
            "message": "Пользователь не авторизован."
        })
    if promo_data.mode not in {"COMMON", "UNIQUE"}:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса. promo_data.mode not 'COMMON' or 'UNIQUE'."
        })
    if promo_data.mode == "COMMON" and not promo_data.promo_common:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса. COMMON promo_data.promo_common not set"
        })
    if promo_data.mode == "UNIQUE" and (not promo_data.promo_unique or promo_data.max_count != 1):
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса. UNIQUE promo_data.promo_unique not set"
        })
    promo_target = {key: value for key, value in promo_data.target.dict().items() if value is not None}
    if promo_data.active_until in ["None", None]:
        active_until = date.max
    else:
        active_until = date.fromisoformat(str(promo_data.active_until))
    if promo_data.active_from in ["None", None]:
        active_from = date.min
    else:
        active_from = date.fromisoformat(str(promo_data.active_from))
    if promo_data.max_count != 0 and active_from <= date.today() <= active_until:
        active = True
    else:
        active = False

    new_promo_code = PromoCode(
        promo_id=uuid.uuid4(),
        company_id=token.get_token_info(token_context, "_id"),
        company_name=token.get_token_info(token_context, "_name"),
        like_count=0,
        comment_count=0,
        used_count=0,
        active=active,
        mode=promo_data.mode,
        promo_common=promo_data.promo_common,
        promo_unique=promo_data.promo_unique,
        description=promo_data.description,
        image_url=str(promo_data.image_url),
        target=promo_target,
        max_count=promo_data.max_count,
        active_from=promo_data.active_from,
        active_until=promo_data.active_until,
        created=datetime.today(),
    )

    try:
        promo_country = new_promo_code.target["country"]
    except:
        promo_country = "UNKNOWN"

    new_promo_code_statistics = PromoCodeStatistics(
        promo_id=new_promo_code.promo_id,
        country=promo_country,
        activations_count=0
    )

    db.add(new_promo_code)
    db.commit()
    db.refresh(new_promo_code)

    db.add(new_promo_code_statistics)
    db.commit()
    db.refresh(new_promo_code_statistics)

    return JSONResponse(status_code=201,
                        content={"id": str(new_promo_code.promo_id)
                                 })


@router.get("/promo",
            tags=["Получить список промокодов"],
            description="Возвращает список промокодов компании с возможностью фильтрации, сортировки и пагинации.")
async def list_promo_code(limit: int = 10,
                          offset: int = 0,
                          sort_by: Optional[str] = Query("created", enum=["active_from", "active_until"]),
                          country: Optional[List[str]] = Query(None),
                          token_context: str = Depends(token.get_token),
                          db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса."
        })
    if not token.check_valid_company_token(token_context):
        return JSONResponse(status_code=401, content={
            "status": "error",
            "message": "Пользователь не авторизован."
        })
    company_id = token.get_token_info(token_context, "_id")
    query = db.query(PromoCode).filter_by(company_id=company_id)
    country_filter = set()
    if country:
        for c in country:
            country_filter.update(c.lower().split(","))

        query = query.filter(
            or_(func.jsonb_extract_path_text(cast(PromoCode.target, JSONB), 'country').in_(country_filter),
                func.jsonb_extract_path_text(cast(PromoCode.target, JSONB), 'country').is_(None)))

    if sort_by == "active_from":
        query = query.order_by(desc(PromoCode.active_from))
        promo_codes = query.offset(offset).limit(limit).all()
    elif sort_by == "active_until":
        query = query.order_by(desc(PromoCode.active_until))
        promo_codes = query.offset(offset).limit(limit).all()
    else:
        query = query.order_by(PromoCode.created)
        promo_codes = query.all()
        promo_codes.reverse()
        promo_codes = promo_codes[offset:offset + limit]

    total_count = query.count()

    headers = {"x-total-count": str(total_count)}

    return JSONResponse(content=[promo_code.to_dict() for promo_code in promo_codes], headers=headers)


@router.get("/promo/{promo_id}",
            tags=["Получения промокода"],
            description="Получает данные промокода по его ID. С помощью этого эндпоинта компания может получить только свои промокоды.")
async def get_promo_code(promo_id: str,
                         token_context: str = Depends(token.get_token),
                         db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=401, content={
                "status": "error",
                "message": "Пользователь не авторизован."
            })
    promo = db.query(PromoCode).get(promo_id)
    if not promo:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": "Промокод не найден."
        })

    if token.get_token_info(token_context, "_id") != str(promo.company_id):
        return JSONResponse(status_code=403, content={
            "status": "error",
            "message": "Промокод не принадлежит этой компании."
        })
    return JSONResponse(content=promo.to_dict())


@router.patch("/promo/{promo_id}",
              tags=["Редактирование промокода"],
              description="Редактирует данные промокода по его ID.")
async def patch_promo_code(patch_data: PatchPromoCode,
                           promo_id: str,
                           token_context: str = Depends(token.get_token),
                           db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса."
        })
    promo = db.query(PromoCode).get(promo_id)
    if not promo:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": "Промокод не найден."
        })
    if token.get_token_info(token_context, "_id") != str(promo.company_id):
        return JSONResponse(status_code=403, content={
            "status": "error",
            "message": "Промокод не принадлежит этой компании."
        })
    if promo.mode == "UNIQUE" and patch_data.max_count is not None and patch_data.max_count != 1:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса."
        })
    update_data = {key: value for key, value in patch_data.dict().items() if value is not None}
    for key, value in update_data.items():
        setattr(promo, key, value)
    if promo.active_until in ["None", None]:
        active_until = date.max
    else:
        active_until = date.fromisoformat(str(promo.active_until))
    if promo.active_from in ["None", None]:
        active_from = date.min
    else:
        active_from = date.fromisoformat(str(promo.active_from))
    if promo.max_count != 0 and active_from <= date.today() <= active_until:
        active = True
    else:
        active = False
    setattr(promo, "active", active)
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return JSONResponse(content=promo.to_dict())


@router.get("/promo/{promo_id}/stat",
            tags=["Получить статистику по промокоду"],
            description="Возвращает статистику использования промокода по его ID.")
async def promo_stat(promo_id: str,
                     token_context: str = Depends(token.get_token),
                     db: Session = Depends(get_db)):
    if not token_context:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Ошибка в данных запроса."
        })
    promo = db.query(PromoCode).get(promo_id)
    if not promo:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": "Промокод не найден."
        })

    if token.get_token_info(token_context, "_id") != str(promo.company_id):
        return JSONResponse(status_code=403, content={
            "status": "error",
            "message": "Промокод не принадлежит этой компании."
        })
    stats = db.query(PromoCodeStatistics).filter(PromoCodeStatistics.promo_id == promo_id).all()
    if not stats:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": "Промокод не найден."
        })
    activations_count = sum(stat.activations_count for stat in stats)
    countries = [{"country": stat.country, "activations_count": stat.activations_count} for stat in stats]
    return {"activations_count": activations_count, "countries": countries}
