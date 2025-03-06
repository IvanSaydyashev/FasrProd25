import logging
import uuid
from typing import Optional

import pycountry
from sqlalchemy import Column, VARCHAR, UUID, JSON
from app.db.base import Base
from pydantic import BaseModel, EmailStr, Field, field_validator, HttpUrl, StrictStr, StrictInt

class UrlModel(BaseModel):
    url: HttpUrl

class User(Base):
    __tablename__ = 'user'

    user_id = Column(UUID(as_uuid=True), primary_key=True, unique=True, nullable=False, default=uuid.uuid4)
    password = Column(VARCHAR(128), nullable=False)
    name = Column(VARCHAR(100), nullable=False)
    surname = Column(VARCHAR(120), nullable=False)
    email = Column(VARCHAR(120), unique=True, nullable=False)
    avatar_url = Column(VARCHAR(350), nullable=False)
    other = Column(JSON, nullable=False)

    def to_dict(self):
        new_dict = {
            'name': self.name,
            'surname': self.surname,
            'email': self.email,
            'avatar_url': self.avatar_url,
            'other': self.other,
        }
        new_dict = {key: value for key, value in new_dict.items() if value is not None}
        return new_dict


class Other(BaseModel):
    age: StrictInt = Field(..., gt=0, le=100)
    country: StrictStr = Field(...)

    @field_validator("country", mode="before")
    def validate_country(cls, value):
        if value and not any(str(c.alpha_2).lower() == str(value).lower() for c in pycountry.countries):
            raise ValueError(f"Invalid country code: {value}. Must be a valid ISO 3166-1 alpha-2 code.")
        return value

class UserBase(BaseModel):
    password: StrictStr = Field(..., min_length=8, max_length=60, pattern=r"^[A-Za-z\d@$!%*?&]{8,}$")
    name: StrictStr = Field(..., min_length=1, max_length=100, description="Имя пользователя")
    surname: StrictStr = Field(..., min_length=1, max_length=120, description="Фамилия пользователя")
    email: EmailStr = Field(..., min_length=8, max_length=120, description="Email пользователя")
    avatar_url: Optional[HttpUrl] = Field(default=None, max_length=350)
    other: Other

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

class UserSignin(BaseModel):
    email: EmailStr = Field(..., min_length=8, max_length=120, description="Email пользователя")
    password: StrictStr = Field(..., min_length=8, max_length=60, pattern=r"^[A-Za-z\d@$!%*?&]{8,}$")

    class Config:
        from_attributes = True

class UserPatch(BaseModel):
    name: Optional[StrictStr] = Field(default=None, max_length=100, description="Имя пользователя")
    surname: Optional[StrictStr] = Field(default=None, max_length=120, description="Фамилия пользователя")
    avatar_url: Optional[HttpUrl] = Field(default=None, max_length=350)
    password: Optional[StrictStr] = Field(default=None, max_length=60)

    @field_validator('password')
    def validate_password_complexity(cls, password):
        if password != "":
            if (not any(c.islower() for c in password) or
                    not any(c.isupper() for c in password) or
                    not any(c.isdigit() for c in password) or
                    not any(c in "@$!%*?&" for c in password) or len(password) < 8):
                raise ValueError(
                    "Пароль пользователя/компании. Должен содержать латинские буквы, хотя бы одну заглавную, одну строчную, одну цифру и специальные символы.")
            return password
        return None

    @field_validator("name", mode="before")
    def validate_name(cls, value):
        if value == "":
            raise ValueError("name cannot be empty")
        return value

    @field_validator('surname', mode="before")
    def validate_surname(cls, value):
        if value == "":
            raise ValueError("surname cannot be empty")
        return value

    @field_validator('avatar_url', mode="before")
    def validate_email(cls, value):
        if value == "":
            raise ValueError("avatar_url cannot be empty")
        return str(value)

    class Config:
        from_attributes = True