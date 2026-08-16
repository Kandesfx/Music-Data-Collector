"""
Music Data Collector - Retry Handler
Provides retry logic with exponential backoff for transient failures.
"""

import time
import functools
from typing import Callable, Tuple, Type

import requests
from src.utils.logger import get_logger

logger = get_logger(__name__)


def retry_on_failure(
    max_retries: int = 3,
    backoff_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError,
    ),
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
):
    """
    Decorator that retries a function on transient failures with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        backoff_base: Base for exponential backoff (delay = base^attempt).
        retryable_exceptions: Exception types that trigger a retry.
        retryable_status_codes: HTTP status codes that trigger a retry.

    Usage:
        @retry_on_failure(max_retries=3)
        def fetch_data(url):
            resp = requests.get(url)
            resp.raise_for_status()
            return resp.json()
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Check if result is a Response with retryable status
                    if isinstance(result, requests.Response):
                        if result.status_code in retryable_status_codes:
                            if attempt < max_retries:
                                delay = backoff_base ** attempt
                                logger.warning(
                                    f"[Retry] {func.__name__} returned status "
                                    f"{result.status_code}, attempt {attempt + 1}/"
                                    f"{max_retries + 1}, waiting {delay:.1f}s..."
                                )
                                time.sleep(delay)
                                continue
                            else:
                                result.raise_for_status()

                    return result

                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = backoff_base ** attempt
                        logger.warning(
                            f"[Retry] {func.__name__} failed with {type(e).__name__}: "
                            f"{e}, attempt {attempt + 1}/{max_retries + 1}, "
                            f"waiting {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} failed after "
                            f"{max_retries + 1} attempts: {e}"
                        )
                        raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def retry_download(
    func: Callable,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> Callable:
    """
    Wrapper specifically for download operations with resume support.

    Args:
        func: The download function to wrap.
        max_retries: Maximum retry attempts.
        backoff_base: Base for exponential backoff.

    Returns:
        Wrapped function with retry logic.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
                IOError,
            ) as e:
                if attempt < max_retries:
                    delay = backoff_base ** attempt
                    logger.warning(
                        f"[Download Retry] Attempt {attempt + 1}/{max_retries + 1} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[Download Retry] All {max_retries + 1} attempts failed: {e}"
                    )
                    raise

    return wrapper
