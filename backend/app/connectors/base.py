"""
FloodPulse AI - Base Connector Abstract Class
Robust, asynchronous HTTP connector framework with exponential backoff + jitter,
rate-limit detection (HTTP 429), status auditing, freshness reporting,
and error resilience.
"""

import abc
import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from app.database import execute_query, fetch_one

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    """Base exception for external connector failures."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class RateLimitError(ConnectorError):
    """Raised when an external API responds with HTTP 429 Too Many Requests."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class BaseConnector(abc.ABC):
    """
    Abstract Base Class for all real-time and catalog data connectors.
    Enforces standardized fetch -> validate -> normalize -> store lifecycle.
    """

    # Longest we will sleep inside one request when rate limited.
    # If the API asks for more, the scheduler should retry on its next cycle.
    MAX_RATE_LIMIT_WAIT: float = 10.0

    def __init__(
        self,
        name: str,
        source_id: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        update_interval_seconds: Optional[int] = None,
    ):
        self.name = name
        self.source_id = source_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        # How often the source is expected to produce new data (used for freshness).
        self.update_interval_seconds = update_interval_seconds

        self.last_successful_fetch: Optional[datetime] = None
        self.last_successful_sync: Optional[datetime] = None  # fetch AND store succeeded
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.status: str = "unknown"

        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------ #
    # HTTP client lifecycle
    # ------------------------------------------------------------------ #
    async def _get_client(self) -> httpx.AsyncClient:
        """Reuse one client (connection pooling) instead of one per attempt."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client. Call on application shutdown."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> int:
        try:
            return max(int(response.headers.get("Retry-After", "60")), 1)
        except ValueError:
            return 60

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with a little jitter to avoid synchronized retries."""
        return (self.backoff_factor ** attempt) + random.uniform(0, 0.5)

    async def _record_failure(self, message: str, status: str = "error") -> None:
        self.last_error = message
        self.last_error_time = datetime.now(timezone.utc)
        self.status = status
        await self.update_source_status(status=status, error=message)

    # ------------------------------------------------------------------ #
    # Fetch
    # ------------------------------------------------------------------ #
    async def fetch(
        self,
        endpoint: str = "",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "GET",
        json_body: Optional[Any] = None
    ) -> Any:
        """
        Execute resilient HTTP requests with exponential backoff and rate limit handling.
        - 429: waits (capped) and retries; raises RateLimitError when exhausted.
        - 5xx / network errors: retried with backoff.
        - Other 4xx: fail fast (retrying a 400/404 will never help).
        Returns parsed JSON or text response.
        """
        method = method.upper()
        if method not in ("GET", "POST"):
            raise ValueError(f"Unsupported HTTP method: {method}")

        url = f"{self.base_url}/{endpoint.lstrip('/')}" if endpoint else self.base_url
        request_headers = {
            "User-Agent": "FloodPulse-AI/1.0 (Tonle Sap Lake Monitoring Platform; Cambodia)",
            **(headers or {}),  # caller's dict is not mutated
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._get_client()
                if method == "GET":
                    response = await client.get(url, params=params, headers=request_headers)
                else:
                    response = await client.post(url, params=params, json=json_body, headers=request_headers)

                # ---- Rate limiting (429) ----
                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    logger.warning(
                        f"[{self.name}] Rate limited (429). Retry-After: {retry_after}s. "
                        f"Attempt {attempt}/{self.max_retries}"
                    )
                    if attempt == self.max_retries:
                        msg = f"Rate limit exceeded on {self.name} after {self.max_retries} attempts."
                        await self._record_failure(msg, status="rate_limited")
                        raise RateLimitError(msg, retry_after=retry_after)
                    await asyncio.sleep(min(retry_after, self.MAX_RATE_LIMIT_WAIT))
                    continue

                # ---- Server errors (5xx): retry ----
                if response.status_code >= 500:
                    logger.warning(
                        f"[{self.name}] Server returned {response.status_code}. "
                        f"Attempt {attempt}/{self.max_retries}"
                    )
                    if attempt == self.max_retries:
                        msg = f"Server error {response.status_code} on [{self.name}] after {self.max_retries} attempts."
                        await self._record_failure(msg)
                        raise ConnectorError(msg, status_code=response.status_code)
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue

                # ---- Client errors (other 4xx): fail fast ----
                if response.status_code >= 400:
                    msg = f"HTTP {response.status_code} on [{self.name}]: {response.text[:200]}"
                    await self._record_failure(msg)
                    raise ConnectorError(msg, status_code=response.status_code)

                # ---- Success: parse FIRST, then mark active ----
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type or "geo+json" in content_type:
                    payload: Any = response.json()
                else:
                    payload = response.text

                self.last_successful_fetch = datetime.now(timezone.utc)
                self.status = "active"
                self.last_error = None
                await self.update_source_status(status="active", error=None)
                return payload

            except ConnectorError:
                # Already recorded above; don't wrap or re-record (keeps RateLimitError type).
                raise

            except httpx.RequestError as exc:
                err_msg = f"Network error on [{self.name}]: {exc!r}"
                logger.error(err_msg)
                if attempt == self.max_retries:
                    await self._record_failure(err_msg)
                    raise ConnectorError(err_msg) from exc
                await asyncio.sleep(self._backoff_delay(attempt))

            except Exception as exc:
                err_msg = f"Unexpected failure on [{self.name}]: {exc!r}"
                logger.error(err_msg)
                await self._record_failure(err_msg)
                raise ConnectorError(err_msg) from exc

        raise ConnectorError(f"[{self.name}] Exhausted {self.max_retries} retries without success.")

    # ------------------------------------------------------------------ #
    # Lifecycle hooks
    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def validate(self, raw_data: Any) -> bool:
        """Validate structure and essential attributes of raw incoming payload."""
        pass

    @abc.abstractmethod
    def normalize(self, raw_data: Any) -> Any:
        """Convert raw external payload into normalized domain models or dictionaries."""
        pass

    @abc.abstractmethod
    async def store(self, normalized_data: Any) -> int:
        """Persist normalized data into the SQLite database. Returns count of inserted records."""
        pass

    async def sync(self, **kwargs) -> Dict[str, Any]:
        """
        Standard orchestrator lifecycle: fetch -> validate -> normalize -> store.
        """
        raw = await self.fetch(**kwargs)
        if not self.validate(raw):
            msg = f"Validation failed for data from {self.name}"
            await self._record_failure(msg)
            raise ConnectorError(msg)
        try:
            normalized = self.normalize(raw)
            records_saved = await self.store(normalized)
        except ConnectorError:
            raise
        except Exception as exc:
            msg = f"Normalize/store failed on [{self.name}]: {exc!r}"
            await self._record_failure(msg)
            raise ConnectorError(msg) from exc

        self.last_successful_sync = datetime.now(timezone.utc)
        return {
            "connector": self.name,
            "status": "success",
            "records_stored": records_saved,
            "timestamp": self.last_successful_sync.isoformat()
        }

    # ------------------------------------------------------------------ #
    # Status / audit
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_iso(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(value))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    async def get_status(self) -> Dict[str, Any]:
        """Get live status, last sync metrics, and data freshness."""
        db_record = await fetch_one("SELECT * FROM data_sources WHERE name LIKE ?", (f"%{self.name}%",))

        last_fetch_dt = self.last_successful_fetch or (
            self._parse_iso(db_record.get("last_successful_fetch")) if db_record else None
        )

        age_seconds: Optional[int] = None
        freshness = "unknown"
        if last_fetch_dt is not None:
            age_seconds = int((datetime.now(timezone.utc) - last_fetch_dt).total_seconds())
            if self.update_interval_seconds:
                # Fresh while within 2 expected update cycles
                freshness = "fresh" if age_seconds <= 2 * self.update_interval_seconds else "stale"
        elif self.update_interval_seconds:
            freshness = "never_fetched"

        return {
            "name": self.name,
            "source_id": self.source_id,
            "status": self.status if not db_record else db_record.get("status", self.status),
            "last_successful_fetch": last_fetch_dt.isoformat() if last_fetch_dt else None,
            "last_successful_sync": self.last_successful_sync.isoformat() if self.last_successful_sync else None,
            "data_age_seconds": age_seconds,
            "expected_interval_seconds": self.update_interval_seconds,
            "freshness": freshness,
            "last_error": self.last_error if not db_record else db_record.get("last_error"),
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else (
                db_record.get("last_error_time") if db_record else None
            )
        }

    async def update_source_status(self, status: str, error: Optional[str] = None) -> None:
        """Update connector status in data_sources audit table."""
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            if status == "active":
                await execute_query(
                    """
                    UPDATE data_sources
                    SET status = ?, last_successful_fetch = ?, last_error = NULL
                    WHERE name LIKE ?
                    """,
                    (status, now_iso, f"%{self.name}%")
                )
            else:
                await execute_query(
                    """
                    UPDATE data_sources
                    SET status = ?, last_error = ?, last_error_time = ?
                    WHERE name LIKE ?
                    """,
                    (status, error or "Unspecified error", now_iso, f"%{self.name}%")
                )
        except Exception as exc:
            logger.warning(f"Failed to update data_sources table for {self.name}: {exc}")