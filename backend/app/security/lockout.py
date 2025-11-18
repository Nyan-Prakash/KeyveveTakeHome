"""Account lockout management using Redis."""

import redis.asyncio as redis
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from backend.app.config import get_settings


class LockoutStatus(BaseModel):
    """Account lockout status."""
    locked: bool
    locked_until: Optional[datetime] = None
    failed_attempts: int = 0
    remaining_attempts: int = 0


async def get_redis_client() -> redis.Redis:
    """Get Redis client for lockout storage."""
    settings = get_settings()
    return redis.from_url(settings.redis_url)


async def check_and_update_lockout(user_id: UUID, authentication_failed: bool) -> LockoutStatus:
    """Check and update user lockout status.
    
    Args:
        user_id: User UUID
        authentication_failed: True if authentication attempt failed
        
    Returns:
        LockoutStatus with current lockout information
    """
    settings = get_settings()
    client = await get_redis_client()
    
    lockout_key = f"lockout:{user_id}"
    
    try:
        # Get current lockout data
        current = await client.hgetall(lockout_key)
        
        # Check if user is currently locked
        if current and current.get(b'locked_until'):
            locked_until_str = current[b'locked_until'].decode()
            locked_until = datetime.fromisoformat(locked_until_str)
            
            if locked_until > datetime.now(timezone.utc):
                # Still locked
                attempts = int(current.get(b'attempts', b'0').decode())
                return LockoutStatus(
                    locked=True,
                    locked_until=locked_until,
                    failed_attempts=attempts,
                    remaining_attempts=0
                )
            else:
                # Lock expired, clear it
                await client.delete(lockout_key)
                current = {}
        
        # Handle authentication attempt
        if authentication_failed:
            # Increment failure count
            attempts = int(current.get(b'attempts', b'0').decode() if current.get(b'attempts') else '0') + 1
            
            if attempts >= settings.lockout_threshold:
                # Lock account
                locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.lockout_duration_minutes
                )
                
                await client.hset(lockout_key, {
                    'attempts': str(attempts),
                    'locked_until': locked_until.isoformat()
                })
                
                # Set expiry slightly longer than lockout duration
                await client.expire(
                    lockout_key, 
                    settings.lockout_duration_minutes * 60 + 60
                )
                
                return LockoutStatus(
                    locked=True,
                    locked_until=locked_until,
                    failed_attempts=attempts,
                    remaining_attempts=0
                )
            else:
                # Update failure count but don't lock yet
                await client.hset(lockout_key, {'attempts': str(attempts)})
                await client.expire(lockout_key, 300)  # 5 minute sliding window
                
                return LockoutStatus(
                    locked=False,
                    failed_attempts=attempts,
                    remaining_attempts=settings.lockout_threshold - attempts
                )
        else:
            # Authentication succeeded - clear any lockout data
            await client.delete(lockout_key)
            
            return LockoutStatus(
                locked=False,
                failed_attempts=0,
                remaining_attempts=settings.lockout_threshold
            )
            
    except Exception as e:
        # If Redis fails, don't block authentication but log the error
        # In production, you might want to fail closed instead
        print(f"Lockout check failed for user {user_id}: {e}")
        return LockoutStatus(
            locked=False,
            failed_attempts=0,
            remaining_attempts=settings.lockout_threshold
        )
    finally:
        await client.aclose()


async def clear_user_lockout(user_id: UUID) -> None:
    """Clear lockout for a specific user (admin function).
    
    Args:
        user_id: User UUID to unlock
    """
    client = await get_redis_client()
    
    try:
        lockout_key = f"lockout:{user_id}"
        await client.delete(lockout_key)
    finally:
        await client.aclose()


async def get_lockout_status(user_id: UUID) -> LockoutStatus:
    """Get current lockout status without updating it.
    
    Args:
        user_id: User UUID
        
    Returns:
        Current LockoutStatus
    """
    settings = get_settings()
    client = await get_redis_client()
    
    try:
        lockout_key = f"lockout:{user_id}"
        current = await client.hgetall(lockout_key)
        
        if not current:
            return LockoutStatus(
                locked=False,
                failed_attempts=0,
                remaining_attempts=settings.lockout_threshold
            )
        
        # Check if locked
        if current.get(b'locked_until'):
            locked_until_str = current[b'locked_until'].decode()
            locked_until = datetime.fromisoformat(locked_until_str)
            
            if locked_until > datetime.now(timezone.utc):
                attempts = int(current.get(b'attempts', 0))
                return LockoutStatus(
                    locked=True,
                    locked_until=locked_until,
                    failed_attempts=attempts,
                    remaining_attempts=0
                )
        
        # Not locked, return current attempt count
        attempts = int(current.get(b'attempts', 0))
        return LockoutStatus(
            locked=False,
            failed_attempts=attempts,
            remaining_attempts=settings.lockout_threshold - attempts
        )
        
    except Exception as e:
        print(f"Failed to get lockout status for user {user_id}: {e}")
        return LockoutStatus(
            locked=False,
            failed_attempts=0,
            remaining_attempts=settings.lockout_threshold
        )
    finally:
        await client.aclose()
