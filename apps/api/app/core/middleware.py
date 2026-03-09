from uuid import uuid4

import structlog
from fastapi import Request
from starlette.responses import JSONResponse, Response

from app.schemas.common import ErrorCode
from app.utils.rate_limit import SlidingWindowRateLimiter

logger = structlog.get_logger(__name__)
rate_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)


async def correlation_and_rate_limit_middleware(request: Request, call_next) -> Response:
    correlation_id = request.headers.get("x-correlation-id") or str(uuid4())
    request.state.correlation_id = correlation_id

    if request.url.path in {"/upload/init", "/upload/confirm", "/search", "/chat"}:
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{request.url.path}"
        if not rate_limiter.allow(key):
            logger.warning(
                "rate_limit_exceeded",
                path=request.url.path,
                ip=ip,
                correlation_id=correlation_id,
            )
            return JSONResponse(
                status_code=429,
                content={"code": ErrorCode.RATE_LIMITED.value, "message": "Rate limit exceeded"},
                headers={"x-correlation-id": correlation_id},
            )

    response = await call_next(request)
    response.headers["x-correlation-id"] = correlation_id
    return response
