from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db, redis_client
from app.core.password import hash_password, verify_password
from app.models.business_auth import CompanyBase, CompanySignin, Company
import uuid
from app.core import token
router = APIRouter()


@router.post("/auth/sign-up",
             tags=["Регистрация новой компании"],
             description="Регистрирует новую компанию и возвращает токен доступа.")
async def sign_up(company: CompanyBase, db: Session = Depends(get_db)):
    db_company = db.query(Company).filter(Company.email == company.email).first()
    if db_company:
        return JSONResponse(
            status_code=409,
            content={
                "status": "error",
                "message": "Такой email уже зарегистрирован."})
    hashed_password = hash_password(company.password)
    new_company = Company(
        company_id=uuid.uuid4(),
        email=company.email,
        name=company.name,
        password=hashed_password
    )
    print(new_company.company_id, uuid.uuid4())
    token_context = token.generate_company_token(new_company)
    redis_key = f"company_token:{new_company.company_id}"
    redis_client.setex(redis_key, 3600*24, token_context)

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    return {
        "token": token_context,
        "company_id": new_company.company_id
    }


@router.post("/auth/sign-in",
             tags=["Аутентификация компании"],
             description="Вход компании по email и паролю для получения токена доступа."
                         " Успешная аутентификация инвалидирует ранее выданные токены (запросы по ним станут невозможны). HardPa$$w0rd!iamthewinner")
async def sign_in(company: CompanySignin, db: Session = Depends(get_db)):
    exist_company = db.query(Company).filter(Company.email == company.email).first()
    if exist_company and verify_password(company.password, exist_company.password):
        company_id = str(exist_company.company_id)
        redis_client.delete(f"company_token:{company_id}")
        token_context = token.generate_company_token(exist_company)
        redis_key = f"company_token:{exist_company.company_id}"
        redis_client.setex(redis_key, 3600 * 24, token_context)
        return {"token": token_context, "id": company_id}
    else:
        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "message": "Неверный email или пароль."
            }
        )
