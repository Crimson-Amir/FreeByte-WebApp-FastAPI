from pydantic import BaseSettings

class Settings(BaseSettings):
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str
    EMAIL_FROM: str

    class Config: env_file = ".env"

settings = Settings()
