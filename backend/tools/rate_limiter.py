from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiolimiter import AsyncLimiter

from config import settings

request_limiter = AsyncLimiter(
    max_rate=settings.GROQ_REQUESTS_PER_MINUTE,
    time_period=60,
)

token_limiter = AsyncLimiter(
    max_rate=settings.GROQ_TOKENS_PER_MINUTE,
    time_period=60,
)


@asynccontextmanager
async def acquire_groq_slot(estimated_tokens: int = 500) -> AsyncGenerator[None, None]:
    async with request_limiter:
        async with token_limiter:
            yield
