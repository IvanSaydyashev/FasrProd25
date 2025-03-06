import os
from fastapi import FastAPI, Request
import uvicorn
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from starlette import status

from app.api import ping, business_auth, business_promo, user_auth, profile, user_promo
from app.db.session import init_db


app = FastAPI()
app.include_router(ping.router, prefix='/api')
app.include_router(business_auth.router, prefix='/api/business')
app.include_router(business_promo.router, prefix='/api/business')
app.include_router(user_auth.router, prefix='/api/user')
app.include_router(profile.router, prefix='/api/user')
app.include_router(user_promo.router, prefix='/api/user')
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        # Преобразуем ctx, если он содержит ValueError
        if "ctx" in error and isinstance(error["ctx"].get("error"), ValueError):
            error["ctx"]["error"] = str(error["ctx"]["error"])
        errors.append(error)

    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "message": "Ошибка в данных запроса.",
            "details": errors
        },
    )

@app.exception_handler(HTTPException)
async def custom_not_authenticated_handler(request: Request, exc: HTTPException):
    # Проверяем, если detail содержит "Not authenticated"
    if exc.detail == "Not authenticated":
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "status": "error",
                "message": "Пользователь не авторизован."
            }
        )
    # В остальных случаях возвращаем стандартное поведение
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

if __name__ == "__main__":
    init_db()
    server_address = os.getenv("SERVER_ADDRESS", "localhost:8080")
    host, port = server_address.split(":")
    uvicorn.run(app, host=host, port=int(port))
