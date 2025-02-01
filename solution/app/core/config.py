import os

from pydantic_settings import BaseSettings
from typing import ClassVar

class Settings(BaseSettings):
    username: ClassVar[str] = os.getenv('POSTGRES_USERNAME', 'postgres')
    password: ClassVar[str] = os.getenv('POSTGRES_PASSWORD', 'admin')
    host: ClassVar[str] = os.getenv('POSTGRES_HOST', 'localhost')
    port: ClassVar[str] = os.getenv('POSTGRES_PORT', '5432')
    dbname: ClassVar[str] = os.getenv('POSTGRES_DATABASE', 'postgres')
    DATABASE_URL: str = f'postgresql://{username}:{password}@{host}:{port}/{dbname}'


settings = Settings()
