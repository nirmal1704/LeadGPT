from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str
    REDIS_URL: str
    MONGO_URI: str = ""
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    GROQ_MODEL: str = "deepseek-r1-distill-llama-70b"
    GROQ_FAST_MODEL: str = "gemma2-9b-it"
    GROQ_SMART_RPM: int = 28
    GROQ_SMART_TPM: int = 6000
    GROQ_FAST_RPM: int = 28
    GROQ_FAST_TPM: int = 15000
    MEMORY_SIMILARITY_THRESHOLD: float = 0.85
    NOPECHA_EXTENSION_PATH: str = "/opt/extensions/nopecha.crx"
    CAPTCHA_TIMEOUT_SECONDS: int = 30
    MAX_CONCURRENT_PAGES: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
