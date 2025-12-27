"""Production utilities for reliability and monitoring."""

import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for handling upstream failures gracefully."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default"
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            name: Circuit breaker identifier for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False

    def record_success(self):
        """Record a successful call."""
        if self.failure_count > 0:
            logger.info(f"CircuitBreaker({self.name}): Success after {self.failure_count} failures, resetting")
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(f"CircuitBreaker({self.name}): Opening circuit after {self.failure_count} failures")

    def can_attempt(self) -> bool:
        """Check if we can attempt a call."""
        if not self.is_open:
            return True

        # Check if recovery timeout has passed
        if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout:
            logger.info(f"CircuitBreaker({self.name}): Attempting recovery")
            self.is_open = False
            self.failure_count = 0
            return True

        return False


class RateLimiter:
    """Simple rate limiter for controlling request volume."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window for rate limiting
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []

    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        now = time.time()
        window_start = now - self.window_seconds

        # Remove old requests outside the window
        self.requests = [t for t in self.requests if t > window_start]

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False

    def get_retry_after(self) -> int:
        """Get seconds to wait before retry."""
        if not self.requests:
            return 0
        try:
            # Filter to numeric values only, then find minimum
            numeric_requests = [r for r in self.requests if isinstance(r, (int, float))]
            if not numeric_requests:
                return 0
            oldest = min(numeric_requests)
            retry_after = int((oldest + self.window_seconds - time.time()) + 1)
            return max(1, retry_after)
        except Exception:
            return 0


def with_timeout(seconds: int):
    """Decorator to add timeout to a function (best effort, not guaranteed)."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                if elapsed > seconds:
                    logger.warning(
                        f"Function {func.__name__} exceeded timeout: {elapsed:.1f}s > {seconds}s"
                    )
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(
                    f"Function {func.__name__} failed after {elapsed:.1f}s: {str(e)}"
                )
                raise
        return wrapper
    return decorator


def with_retry(max_retries: int = 3, backoff_seconds: float = 1.0):
    """Decorator to retry a function with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"Function {func.__name__} attempt {attempt + 1} failed, "
                            f"retrying in {wait_time:.1f}s: {str(e)}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} attempts: {str(e)}"
                        )
            raise last_exception
        return wrapper
    return decorator


# Global circuit breaker for upstream API
upstream_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="upstream_api"
)

# Global rate limiter (per-process)
rate_limiter = RateLimiter(max_requests=1000, window_seconds=60)
