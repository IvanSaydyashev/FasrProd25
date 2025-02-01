import enum
import uuid
from datetime import datetime, timezone, date
from typing import List, Optional

import pycountry
from sqlalchemy import Column, VARCHAR, UUID, Enum, JSON, Integer, Date, Boolean, String, DateTime

from app.db.base import Base
from pydantic import BaseModel, Field, field_validator, HttpUrl, model_validator, StrictStr, StrictInt


class UrlModel(BaseModel):
    url: HttpUrl


class PromoActions(Base):
    __tablename__ = 'promo_actions'

    action_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    promo_id = Column(UUID(as_uuid=True), nullable=False, unique=False)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=False)
    is_activated_by_user = Column(Boolean, nullable=False, default=False)
    is_liked_by_user = Column(Boolean, nullable=False, default=False)


class PromoComments(Base):
    __tablename__ = 'promo_comments'
    comment_id = Column(UUID(as_uuid=True), primary_key=True, unique=True, nullable=False, default=uuid.uuid4)
    promo_id = Column(UUID(as_uuid=True), nullable=False, unique=False)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=False)
    text = Column(VARCHAR, nullable=False)
    comment_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    author = Column(JSON, nullable=False)


class PromoCommentBase(BaseModel):
    text: str = Field(..., min_length=10, max_length=1000)


class PromoCodeStatistics(Base):
    __tablename__ = 'promo_code_statistics'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    promo_id = Column(UUID(as_uuid=True), nullable=False, unique=False)
    country = Column(String, nullable=False)
    activations_count = Column(Integer, default=0)


class PromoMode(str, enum.Enum):
    COMMON = "COMMON"
    UNIQUE = "UNIQUE"


class PromoCode(Base):
    __tablename__ = "promo_code"

    promo_id = Column(UUID(as_uuid=True), primary_key=True, unique=True, nullable=False, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False, unique=False)
    company_name = Column(VARCHAR, nullable=False)
    like_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    used_count = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    mode = Column(Enum(PromoMode), nullable=False)
    promo_common = Column(VARCHAR(30), nullable=True)
    promo_unique = Column(JSON, nullable=True)
    description = Column(VARCHAR(300), nullable=False)
    image_url = Column(VARCHAR(350), nullable=True)
    target = Column(JSON, nullable=False)
    max_count = Column(Integer, nullable=False)
    active_from = Column(Date, nullable=True)
    active_until = Column(Date, nullable=True)
    created = Column(Date, nullable=False, default=date.today())

    def to_dict(self):
        new_dict = {
            "promo_id": str(self.promo_id),
            "company_id": str(self.company_id),
            "company_name": self.company_name,
            "like_count": self.like_count,
            "used_count": self.used_count,
            "active": self.active,
            "description": self.description,
            "image_url": self.image_url,
            "target": self.target,
            "max_count": self.max_count,
            "active_from": str(self.active_from),
            "active_until": str(self.active_until),
            "mode": self.mode,
            "promo_common": self.promo_common,
            "promo_unique": self.promo_unique,
        }
        new_dict = {key: value for key, value in new_dict.items() if value not in [None, "None"]}
        return new_dict


class Target(BaseModel):
    age_from: Optional[StrictInt] = Field(default=None, ge=0, le=100)
    age_until: Optional[StrictInt] = Field(default=None, ge=0, le=100)
    country: Optional[StrictStr] = Field(default=None)
    categories: Optional[List[StrictStr]] = Field(default=None)

    @model_validator(mode="before")
    def validate_age_range(cls, values):
        age_from = values.get("age_from")
        age_until = values.get("age_until")

        if age_from is not None and age_until is not None:
            if not isinstance(age_from, int) or not isinstance(age_until, int):
                raise ValueError("age_from and age_until must be integers")
            if age_from > age_until:
                raise ValueError("age_from must be less than or equal to age_until")

        return values

    @field_validator("country")
    def validate_country(cls, value):
        if value is None:
            return value
        if value == "":
            raise ValueError("country cannot be empty")
        if not any(str(country.alpha_2).lower() == str(value).lower() for country in pycountry.countries):
            raise ValueError(f"Invalid country code: {value}. Must be a valid ISO 3166-1 alpha-2 code.")
        return value

    @field_validator("categories")
    def validate_categories(cls, categories):
        if categories is not None:
            if any(not category.strip() for category in categories):
                raise ValueError("Categories cannot be empty")
        return categories


class PromoCodeBase(BaseModel):
    description: StrictStr = Field(..., min_length=10, max_length=300)
    image_url: Optional[HttpUrl] = Field(default=None, max_length=350)
    target: Target
    max_count: StrictInt = Field(...)
    active_from: Optional[date] = Field(default=None)
    active_until: Optional[date] = Field(default=None)


class PatchPromoCode(BaseModel):
    description: Optional[StrictStr] = Field(default=None, min_length=10, max_length=300)
    image_url: Optional[HttpUrl] = Field(default=None, max_length=350)
    target: Optional[Target] = Field(default=None)
    max_count: Optional[StrictInt] = Field(default=None)
    active_from: Optional[date] = Field(default=None)
    active_until: Optional[date] = Field(default=None)

    @field_validator("description")
    def validate_description(cls, value):
        if value == "":
            raise ValueError("description cannot be empty")
        return value


class PromoCodeCreate(PromoCodeBase):
    mode: StrictStr
    promo_common: Optional[StrictStr] = Field(default=None, min_length=5, max_length=30)
    promo_unique: Optional[List[StrictStr]] = Field(default=None)

    @field_validator("promo_unique")
    def promo_unique_validator(cls, v):
        if len(v) < 1 or len(v) > 5000:
            raise ValueError("promo_unique must be between 1 and 5000 characters")
        return v
