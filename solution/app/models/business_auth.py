import uuid
from sqlalchemy import Column, VARCHAR, UUID
from app.db.base import Base
from pydantic import BaseModel, EmailStr, Field, field_validator



class Company(Base):
    __tablename__ = 'company'
    company_id = Column(UUID(as_uuid=True), primary_key=True, unique=True, nullable=False, default=uuid.uuid4)
    name = Column(VARCHAR(50), nullable=False)
    email = Column(VARCHAR(120), unique=True, nullable=False)
    password = Column(VARCHAR(128), nullable=False)


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=5, max_length=50, description="Имя компании")
    email: EmailStr = Field(..., min_length=8, max_length=120, description="Email компании")
    password: str = Field(..., min_length=8, max_length=60, pattern=r"^[A-Za-z\d@$!%*?&]{8,}$")

    @field_validator('password')
    def validate_password_complexity(cls, password):
        if (not any(c.islower() for c in password) or
                not any(c.isupper() for c in password) or
                not any(c.isdigit() for c in password) or
                not any(c in "@$!%*?&" for c in password)):
            raise ValueError(
                "Пароль пользователя/компании. Должен содержать латинские буквы, хотя бы одну заглавную, одну строчную, одну цифру и специальные символы.")
        return password

    class Config:
        from_attributes = True


class CompanySignin(BaseModel):
    email: EmailStr = Field(..., min_length=8, max_length=120, description="Email компании")
    password: str = Field(..., min_length=8, max_length=60, pattern=r"^[A-Za-z\d@$!%*?&]{8,}$")

    class Config:
        from_attributes = True
