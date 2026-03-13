from __future__ import annotations

import json
import os
import random
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 20
_WARNED: set[str] = set()
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def _warn_once(kind: str, message: str) -> None:
    if os.getenv("ZOTERO_SEARCH_HTTP_WARN", "1").strip() in {"0", "false", "False"}:
        return
    key = f"{kind}:{message}"
    if key in _WARNED:
        return
    _WARNED.add(key)
    print(f"[search/http] {message}", file=sys.stderr)


def _get_retry_after_seconds(headers: Any) -> float | None:
    if not headers:
        return None
    try:
        raw = headers.get("Retry-After")
        if raw is None:
            return None
        return float(str(raw).strip())
    except Exception:
        return None


def _backoff_seconds(attempt_index: int, *, base: float, cap: float, retry_after: float | None = None) -> float:
    if retry_after is not None and retry_after > 0:
        return min(cap, retry_after)
    exp = base * (2 ** attempt_index)
    jitter = random.uniform(0, base)
    return min(cap, exp + jitter)


def build_url(base: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return base
    filtered = {k: v for k, v in params.items() if v is not None and v != ""}
    return f"{base}?{urlencode(filtered)}"


def json_get(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int | None = None,
) -> dict[str, Any] | list[Any] | None:
    retry_count = retries if retries is not None else int(os.getenv("ZOTERO_SEARCH_HTTP_RETRIES", "2"))
    backoff_base = float(os.getenv("ZOTERO_SEARCH_HTTP_BACKOFF_BASE", "0.8"))
    backoff_cap = float(os.getenv("ZOTERO_SEARCH_HTTP_BACKOFF_CAP", "8.0"))

    merged_headers = {
        "Accept": "application/json",
        "User-Agent": os.getenv("ZOTERO_SEARCH_USER_AGENT", "myocean-zotero-search/0.1"),
    }
    if headers:
        merged_headers.update(headers)

    for attempt in range(retry_count + 1):
        request = Request(url=url, headers=merged_headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:  # nosec B310
                content = response.read().decode("utf-8")
                if not content:
                    return None
                return json.loads(content)
        except HTTPError as e:
            if e.code in RETRYABLE_HTTP_CODES and attempt < retry_count:
                retry_after = _get_retry_after_seconds(e.headers)
                sleep_for = _backoff_seconds(attempt, base=backoff_base, cap=backoff_cap, retry_after=retry_after)
                _warn_once("http_get_retry", f"GET retry ({e.code}) url={url} sleep={sleep_for:.2f}s")
                time.sleep(sleep_for)
                continue
            _warn_once("http_get", f"GET failed ({e.code}) url={url}")
            return None
        except URLError as e:
            if attempt < retry_count:
                sleep_for = _backoff_seconds(attempt, base=backoff_base, cap=backoff_cap)
                _warn_once(
                    "http_get_retry",
                    f"GET network retry url={url} reason={getattr(e, 'reason', e)} sleep={sleep_for:.2f}s",
                )
                time.sleep(sleep_for)
                continue
            _warn_once("http_get", f"GET network error url={url} reason={getattr(e, 'reason', e)}")
            return None
        except TimeoutError:
            if attempt < retry_count:
                sleep_for = _backoff_seconds(attempt, base=backoff_base, cap=backoff_cap)
                _warn_once("http_get_retry", f"GET timeout retry url={url} sleep={sleep_for:.2f}s")
                time.sleep(sleep_for)
                continue
            _warn_once("http_get", f"GET timeout url={url}")
            return None
        except json.JSONDecodeError:
            _warn_once("http_get", f"GET invalid JSON url={url}")
            return None
    return None


def json_post(
    url: str,
    payload: Any,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int | None = None,
) -> dict[str, Any] | list[Any] | None:
    retry_count = retries if retries is not None else int(os.getenv("ZOTERO_SEARCH_HTTP_POST_RETRIES", "0"))
    backoff_base = float(os.getenv("ZOTERO_SEARCH_HTTP_BACKOFF_BASE", "0.8"))
    backoff_cap = float(os.getenv("ZOTERO_SEARCH_HTTP_BACKOFF_CAP", "8.0"))

    merged_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": os.getenv("ZOTERO_SEARCH_USER_AGENT", "myocean-zotero-search/0.1"),
    }
    if headers:
        merged_headers.update(headers)
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(retry_count + 1):
        request = Request(url=url, headers=merged_headers, data=body, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:  # nosec B310
                content = response.read().decode("utf-8")
                if not content:
                    return {}
                return json.loads(content)
        except HTTPError as e:
            if e.code in RETRYABLE_HTTP_CODES and attempt < retry_count:
                retry_after = _get_retry_after_seconds(e.headers)
                sleep_for = _backoff_seconds(attempt, base=backoff_base, cap=backoff_cap, retry_after=retry_after)
                _warn_once("http_post_retry", f"POST retry ({e.code}) url={url} sleep={sleep_for:.2f}s")
                time.sleep(sleep_for)
                continue
            _warn_once("http_post", f"POST failed ({e.code}) url={url}")
            try:
                content = e.read().decode("utf-8")
                return json.loads(content) if content else None
            except Exception:
                return None
        except URLError as e:
            if attempt < retry_count:
                sleep_for = _backoff_seconds(attempt, base=backoff_base, cap=backoff_cap)
                _warn_once(
                    "http_post_retry",
                    f"POST network retry url={url} reason={getattr(e, 'reason', e)} sleep={sleep_for:.2f}s",
                )
                time.sleep(sleep_for)
                continue
            _warn_once("http_post", f"POST network error url={url} reason={getattr(e, 'reason', e)}")
            return None
        except TimeoutError:
            if attempt < retry_count:
                sleep_for = _backoff_seconds(attempt, base=backoff_base, cap=backoff_cap)
                _warn_once("http_post_retry", f"POST timeout retry url={url} sleep={sleep_for:.2f}s")
                time.sleep(sleep_for)
                continue
            _warn_once("http_post", f"POST timeout url={url}")
            return None
        except json.JSONDecodeError:
            _warn_once("http_post", f"POST invalid JSON url={url}")
            return None
    return None
