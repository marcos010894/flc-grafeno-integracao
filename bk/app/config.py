"""
FLC Bank - Configurações da Aplicação
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Configurações do sistema carregadas do ambiente"""
    
    # Database
    DB_HOST: str = "193.203.175.123" ####NUNCA USE ISSO EM PRODUCAO
    DB_PORT: int = 3306
    DB_NAME: str = "u580641237_flc"
    DB_USER: str = "u580641237_flc"
    DB_PASSWORD: str = "Mito010894!!"
    
    # JWT
    JWT_SECRET_KEY: str = "flc-bank-secret-key-change-in-production-2024"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173,http://127.0.0.1:3000,https://flc-bank.fly.dev,https://flc-bank-api.fly.dev,https://flc-bank-web.fly.dev,https://grafeno-portal.fly.dev"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    @property
    def DATABASE_URL(self) -> str:
        """URL de conexão com o banco de dados"""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """URL de conexão assíncrona com o banco de dados"""
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Lista de origens CORS permitidas"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações"""
    return Settings()


settings = get_settings()
