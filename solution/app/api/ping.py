from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", tags=["Проверка того, что ваше приложение работает"])
async def ping():
    return {"success": True}
