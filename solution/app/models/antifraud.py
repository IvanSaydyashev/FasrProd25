from pydantic import BaseModel

class AntifraudRequest(BaseModel):
    user_email: str
    password: str
