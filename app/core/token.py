import os
import uuid
import jwt
from fastapi import Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.session import redis_client
from app.models.business_auth import CompanyBase, Company
from app.models.business_promo import PromoCodeCreate
from app.models.user_auth import UserBase, User

security = HTTPBearer()

SECRET_KEY = os.getenv("RANDOM_SECRET", "default_password")
ALGORITHM = "HS256"


def generate_company_token(company: Company) -> str:
    token_data = {
        "jti": str(uuid.uuid4()),
        "sub": str(company.company_id),
        "name": company.name,
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    return token


def generate_user_token(user: User) -> str:
    token_data = {
        "jti": str(uuid.uuid4()),
        "sub": str(user.user_id),
        "name": user.name
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> dict:
    return jwt.decode(token.encode("utf-8"), SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})


def get_token(Authorization: HTTPAuthorizationCredentials = Security(security)):
    if not Authorization.scheme.lower() == "bearer":
        return False
    token: str = Authorization.credentials
    return token


def check_valid_company_token(token: str) -> bool:
    decoded_token = decode_token(token)
    user_id = decoded_token.get("sub")
    client_token = redis_client.get(f"company_token:{user_id}").decode("utf-8")
    if token != client_token:
        return False
    return True


def check_valid_user_token(token: str) -> bool:
    decoded_token = decode_token(token)
    user_id = decoded_token.get("sub")
    try:
        client_token = redis_client.get(f"user_token:{user_id}").decode("utf-8")
    except:
        return False
    if token != client_token:
        return False
    return True


def get_token_info(token: str, value) -> str:
    decoded_token = decode_token(token)
    info = {"jti": decoded_token.get("jti"),
            "_id": decoded_token.get("sub"),
            "_name": decoded_token.get("name")}
    return info[value]
