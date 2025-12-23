"""
API utilities with built-in resilience patterns.

Provides:
- Automatic retry with exponential backoff
- Rate limiting to respect API quotas
- Timeout handling
- Structured error responses
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, backoff_base: float = 2.0, 
               retryable_errors: tuple = (requests.HTTPError, requests.Timeout, requests.ConnectionError)):
    """
    Decorator for exponential backoff retry.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_base: Base for exponential backoff (wait = base^attempt)
        retryable_errors: Tuple of exception types to retry on
        
    Example:
        @with_retry(max_retries=5, backoff_base=2)
        def call_flaky_api():
            return requests.get("https://api.example.com/data")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retryable_errors as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                        raise
                    wait_time = backoff_base ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
            raise last_error
        return wrapper
    return decorator


def rate_limited(calls_per_minute: int = 60):
    """
    Decorator for rate limiting API calls.
    
    Args:
        calls_per_minute: Maximum calls allowed per minute
        
    Example:
        @rate_limited(calls_per_minute=30)
        def call_rate_limited_api():
            return requests.get("https://api.example.com/data")
    """
    min_interval = 60.0 / calls_per_minute
    last_call = [0.0]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            last_call[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


@with_retry(max_retries=3)
def api_call(
    url: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
    timeout: int = 30
) -> Dict:
    """
    Make an API call with retry and error handling built in.
    
    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: Optional request headers
        data: Optional JSON body data
        params: Optional query parameters
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response as dictionary
        
    Raises:
        requests.HTTPError: On 4xx/5xx responses after retries
        requests.Timeout: On timeout after retries
        
    Example:
        result = api_call(
            "https://api.example.com/users",
            method="POST",
            headers={"Authorization": "Bearer token"},
            data={"name": "John"}
        )
    """
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        params=params,
        timeout=timeout
    )
    response.raise_for_status()
    
    # Handle empty responses
    if response.status_code == 204 or not response.content:
        return {"status": "success", "data": None}
    
    return response.json()


def api_call_with_rate_limit(
    url: str,
    calls_per_minute: int = 60,
    **kwargs
) -> Dict:
    """
    Make a rate-limited API call.
    
    Wrapper around api_call that adds rate limiting.
    
    Args:
        url: API endpoint URL
        calls_per_minute: Rate limit for this endpoint
        **kwargs: Additional arguments passed to api_call
        
    Example:
        # Call API max 30 times per minute
        for item in items:
            result = api_call_with_rate_limit(
                f"https://api.example.com/items/{item}",
                calls_per_minute=30
            )
    """
    @rate_limited(calls_per_minute=calls_per_minute)
    def _call():
        return api_call(url, **kwargs)
    return _call()


def handle_api_error(response: requests.Response) -> Dict:
    """
    Convert API error response to structured format.
    
    Args:
        response: The error response from requests
        
    Returns:
        Structured error dict with status, code, message
    """
    try:
        error_body = response.json()
    except:
        error_body = {"raw": response.text}
    
    return {
        "status": "error",
        "http_code": response.status_code,
        "message": error_body.get("message", error_body.get("error", str(error_body))),
        "details": error_body
    }

