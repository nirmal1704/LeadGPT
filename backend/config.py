from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str
    REDIS_URL: str
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    CAPSOLVER_API_KEY: str = ""
    GROQ_REQUESTS_PER_MINUTE: int = 28
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TOKENS_PER_MINUTE: int = 7500
    MEMORY_SIMILARITY_THRESHOLD: float = 0.85
    NOPECHA_EXTENSION_PATH: str = "/opt/extensions/nopecha.crx"
    CAPTCHA_TIMEOUT_SECONDS: int = 30
    MAX_CONCURRENT_PAGES: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
