import functools
import time


def retry_on_exception(max_retries=3, base_delay=2.0, exceptions=(Exception,)):
    """Decorator: retries a function on specified exceptions with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {exc}")
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
