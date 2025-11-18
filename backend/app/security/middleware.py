"""Security middleware for headers and rate limiting."""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

from backend.app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            f"connect-src 'self' {self.settings.ui_origin}",
            "img-src 'self' data:",
            "style-src 'self' 'unsafe-inline'",  # Needed for Streamlit
            "script-src 'self' 'unsafe-eval'",   # Needed for Streamlit
            "font-src 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # HSTS (only in production)
        if not self.settings.ui_origin.startswith("http://localhost"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis token bucket."""
    
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        
        # Rate limit configurations
        self.rate_limits = {
            "/auth/login": (10, 60),      # 10 requests per minute
            "/auth/refresh": (20, 60),    # 20 requests per minute  
            "/auth/logout": (30, 60),     # 30 requests per minute
            "/plan": (5, 60),             # 5 requests per minute for agent
            "/destinations": (60, 60),    # 60 requests per minute for CRUD
            "/knowledge": (30, 60),       # 30 requests per minute
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits and continue or return 429."""
        # Extract path and user identifier
        path = request.url.path
        client_ip = self._get_client_ip(request)
        user_id = await self._extract_user_id(request)
        
        # Determine rate limit for this path
        rate_limit = self._get_rate_limit_for_path(path)
        if not rate_limit:
            # No rate limit configured, continue
            return await call_next(request)
        
        limit, window = rate_limit
        
        # Create rate limit key (prefer user_id, fallback to IP)
        limit_key = f"rate_limit:{user_id or client_ip}:{path}"
        
        # Check rate limit
        allowed, retry_after = await self._check_rate_limit(limit_key, limit, window)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {limit} requests per {window} seconds",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check X-Forwarded-For header (from reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        return request.client.host if request.client else "unknown"
    
    async def _extract_user_id(self, request: Request) -> str | None:
        """Extract user ID from JWT token if present."""
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            
            # Import here to avoid circular imports
            from backend.app.security.jwt import verify_access_token
            payload = verify_access_token(token)
            return str(payload.user_id)
            
        except Exception:
            # Invalid/expired token, use IP-based rate limiting
            return None
    
    def _get_rate_limit_for_path(self, path: str) -> tuple[int, int] | None:
        """Get rate limit configuration for path."""
        # Exact match first
        if path in self.rate_limits:
            return self.rate_limits[path]
        
        # Prefix matching for dynamic paths
        for prefix, limit in self.rate_limits.items():
            if path.startswith(prefix):
                return limit
        
        return None
    
    async def _check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check rate limit using Redis token bucket algorithm.
        
        Returns:
            (allowed, retry_after_seconds)
        """
        try:
            import redis.asyncio as redis
            client = redis.from_url(self.settings.redis_url)
            
            try:
                # Use Lua script for atomic token bucket check
                lua_script = """
                local key = KEYS[1]
                local limit = tonumber(ARGV[1])
                local window = tonumber(ARGV[2])
                local now = tonumber(ARGV[3])
                
                -- Get current bucket state
                local current = redis.call('HMGET', key, 'tokens', 'last_refill')
                local tokens = tonumber(current[1]) or limit
                local last_refill = tonumber(current[2]) or now
                
                -- Calculate tokens to add based on time passed
                local time_passed = now - last_refill
                local tokens_to_add = math.floor(time_passed * limit / window)
                tokens = math.min(limit, tokens + tokens_to_add)
                
                if tokens >= 1 then
                    -- Allow request, consume 1 token
                    tokens = tokens - 1
                    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                    redis.call('EXPIRE', key, window)
                    return {1, 0}  -- allowed, no retry_after
                else
                    -- Deny request, calculate retry_after
                    local retry_after = math.ceil((1 - tokens) * window / limit)
                    return {0, retry_after}  -- not allowed, retry_after
                end
                """
                
                import time
                result = await client.eval(
                    lua_script, 
                    1, 
                    key, 
                    str(limit), 
                    str(window), 
                    str(int(time.time()))
                )
                
                allowed = bool(result[0])
                retry_after = int(result[1])
                
                return allowed, retry_after
                
            finally:
                await client.aclose()
                
        except Exception as e:
            # If rate limiting fails, allow request (fail open)
            print(f"Rate limiting error for {key}: {e}")
            return True, 0
