"""
CL-BEDS Rate Limiter
In-memory sliding window rate limiter using asyncio — no Redis required.
"""

import time
import asyncio
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from app.config import get_settings

settings = get_settings()

# ip -> deque of request timestamps
_request_log: dict[str, deque] = defaultdict(deque)
_lock = asyncio.Lock()


async def rate_limit_middleware(request: Request, call_next):
    """
    Sliding window rate limiter.
    Allows RATE_LIMIT_REQUESTS per RATE_LIMIT_WINDOW seconds per IP.
    Skips rate limiting for WebSocket upgrade requests.
    """
    # Skip WebSocket upgrades
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = settings.RATE_LIMIT_WINDOW
    limit = settings.RATE_LIMIT_REQUESTS

    async with _lock:
        dq = _request_log[client_ip]
        # Remove timestamps outside the window
        while dq and dq[0] < now - window:
            dq.popleft()

        if len(dq) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} requests per {window}s",
            )
        dq.append(now)

    response = await call_next(request)
    return response
