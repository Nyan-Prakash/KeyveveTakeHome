# PR14: Authentication & Security Implementation

**Date:** November 17, 2025  
**Priority:** HIGH (Production Blocker)  
**Status:** Ready for Implementation  

## Objective

Complete the authentication and security implementation by adding JWT creation/verification logic, password hashing, and enabling rate limiting middleware.

## Changes Overview

### 1. JWT Authentication Flow
- Implement JWT creation and verification
- Add password hashing with Argon2id
- Complete login, refresh, and logout endpoints
- User lockout mechanism

### 2. Rate Limiting Activation
- Enable rate limiting middleware in FastAPI
- Configure per-user and per-endpoint limits
- Add Retry-After headers for 429 responses

### 3. Security Enhancements
- Add security headers middleware
- Implement proper CORS configuration
- Input validation and sanitization

## File Changes

### New Files
```
backend/app/security/
├── __init__.py
├── jwt.py (JWT creation/verification)
├── passwords.py (Argon2id hashing)
├── lockout.py (Account lockout logic)
└── middleware.py (Security headers)
```

### Modified Files
```
- backend/app/api/auth.py (implement JWT logic)
- backend/app/main.py (add middleware)
- backend/app/config.py (add security settings)
- pyproject.toml (add security dependencies)
- requirements.txt (update dependencies)
```

## Implementation Details

### JWT Implementation
```python
# backend/app/security/jwt.py
def create_access_token(user_id: UUID, org_id: UUID) -> str:
    """Create JWT access token with 15min expiry."""
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_private_key(), algorithm="RS256")

def verify_access_token(token: str) -> TokenPayload:
    """Verify and decode JWT access token."""
    try:
        payload = jwt.decode(token, get_jwt_public_key(), algorithms=["RS256"])
        return TokenPayload(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            token_type=payload["type"]
        )
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")
```

### Password Hashing
```python
# backend/app/security/passwords.py
import argon2

def hash_password(password: str) -> str:
    """Hash password with Argon2id."""
    ph = argon2.PasswordHasher(
        time_cost=3,      # 3 iterations
        memory_cost=65536, # 64 MB
        parallelism=1,    # Single thread
        hash_len=32,      # 32 byte hash
        salt_len=16       # 16 byte salt
    )
    return ph.hash(password)

def verify_password(password: str, hash: str) -> bool:
    """Verify password against Argon2id hash."""
    ph = argon2.PasswordHasher()
    try:
        ph.verify(hash, password)
        return True
    except argon2.exceptions.VerifyMismatchError:
        return False
```

### Account Lockout
```python
# backend/app/security/lockout.py
async def check_and_update_lockout(user_id: UUID, failed: bool) -> LockoutStatus:
    """Check and update user lockout status."""
    # Get current lockout info from Redis
    lockout_key = f"lockout:{user_id}"
    current = await redis.hgetall(lockout_key)
    
    if failed:
        attempts = int(current.get('attempts', 0)) + 1
        if attempts >= 5:  # Lock after 5 failures
            locked_until = datetime.utcnow() + timedelta(minutes=5)
            await redis.hset(lockout_key, {
                'attempts': attempts,
                'locked_until': locked_until.isoformat()
            })
            await redis.expire(lockout_key, 300)  # 5 min expiry
            return LockoutStatus(locked=True, locked_until=locked_until)
    else:
        # Success - clear lockout
        await redis.delete(lockout_key)
    
    return LockoutStatus(locked=False)
```

### Rate Limiting Middleware
```python
# backend/app/limits/middleware.py
class RateLimitMiddleware:
    def __init__(self, app: FastAPI):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        request = Request(scope, receive)
        
        # Extract user ID from JWT
        user_id = await self._extract_user_id(request)
        
        # Check rate limit
        limit_result = await self._check_rate_limit(request.url.path, user_id)
        
        if limit_result.exceeded:
            response = JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={"Retry-After": str(limit_result.retry_after)}
            )
            await response(scope, receive, send)
            return
            
        # Continue processing
        await self.app(scope, receive, send)
```

## Security Configuration

### JWT Keys
```python
# backend/app/config.py
class Settings(BaseSettings):
    # JWT Configuration
    jwt_private_key_pem: str = Field(
        description="RSA private key for JWT signing (PEM format)"
    )
    jwt_public_key_pem: str = Field(
        description="RSA public key for JWT verification (PEM format)"  
    )
    jwt_access_ttl_minutes: int = Field(
        default=15,
        description="JWT access token TTL in minutes"
    )
    jwt_refresh_ttl_days: int = Field(
        default=7, 
        description="JWT refresh token TTL in days"
    )
    
    # Security Settings
    password_min_length: int = Field(default=8)
    lockout_threshold: int = Field(default=5)
    lockout_duration_minutes: int = Field(default=5)
    
    # Rate Limits (requests per minute)
    rate_limit_auth: int = Field(default=10)
    rate_limit_crud: int = Field(default=60)  
    rate_limit_agent: int = Field(default=5)
```

### Security Headers
```python
# backend/app/security/middleware.py
class SecurityHeadersMiddleware:
    def __init__(self, app: FastAPI):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers.update({
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"same-origin", 
                    b"x-frame-options": b"DENY",
                    b"content-security-policy": b"default-src 'self'",
                    b"strict-transport-security": b"max-age=31536000; includeSubDomains"
                })
                message["headers"] = list(headers.items())
            await send(message)
            
        await self.app(scope, receive, send_with_headers)
```

## Testing Strategy

### Unit Tests
- JWT creation and verification
- Password hashing and verification  
- Account lockout logic
- Rate limiting algorithms

### Integration Tests
- Complete auth flow (login → access → refresh → logout)
- Rate limit enforcement across endpoints
- Security headers verification
- Account lockout end-to-end

### Security Tests
- JWT tampering attempts
- Password brute force protection
- Rate limit bypass attempts
- CORS policy validation

## Dependencies

### New Dependencies
```python
# pyproject.toml additions
"argon2-cffi>=23.1.0",     # Password hashing
"pyjwt[crypto]>=2.8.0",    # JWT with RSA support
"cryptography>=41.0.0",    # RSA key handling
"python-multipart>=0.0.6", # Form data parsing
```

## Migration Plan

### Phase 1: Core Authentication
1. Implement JWT creation/verification
2. Add password hashing
3. Update auth endpoints
4. Test auth flow

### Phase 2: Security Features  
1. Add account lockout
2. Implement rate limiting
3. Add security headers
4. Test security features

### Phase 3: Integration
1. Update existing auth stubs
2. Add middleware to main app
3. Update environment config
4. End-to-end testing

## Success Criteria

- [ ] JWT tokens created and verified correctly
- [ ] Passwords hashed with Argon2id
- [ ] Account lockout after 5 failed attempts
- [ ] Rate limiting enforced (429 responses)  
- [ ] Security headers added to all responses
- [ ] All auth endpoints functional
- [ ] No security header warnings
- [ ] Rate limits configurable per endpoint

## Risk Mitigation

1. **Breaking Changes**: Maintain backward compatibility during transition
2. **Performance Impact**: Rate limiting uses efficient Redis-based implementation
3. **Security Vulnerabilities**: Follow OWASP guidelines and security best practices
4. **Token Management**: Implement proper token rotation and revocation
