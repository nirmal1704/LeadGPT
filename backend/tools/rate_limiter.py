from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiolimiter import AsyncLimiter

from config import settings

smart_request_limiter = AsyncLimiter(max_rate=settings.GROQ_SMART_RPM, time_period=60)
smart_token_limiter = AsyncLimiter(max_rate=settings.GROQ_SMART_TPM, time_period=60)

fast_request_limiter = AsyncLimiter(max_rate=settings.GROQ_FAST_RPM, time_period=60)
fast_token_limiter = AsyncLimiter(max_rate=settings.GROQ_FAST_TPM, time_period=60)

@asynccontextmanager
async def acquire_groq_slot(estimated_tokens: int = 500, model_tier: str = "smart") -> AsyncGenerator[None, None]:
    req_limiter = fast_request_limiter if model_tier == "fast" else smart_request_limiter
    tok_limiter = fast_token_limiter if model_tier == "fast" else smart_token_limiter
    
    async with req_limiter:
        async with tok_limiter:
            yield
