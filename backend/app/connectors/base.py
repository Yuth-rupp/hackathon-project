"""
FloodPulse AI - Base Connector Abstract Class
Robust, asynchronous HTTP connector framework with exponential backoff,
rate-limit detection (HTTP 429), status auditing, and error resilience.
"""

import abc
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

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

    def __init__(
        self,
        name: str,
        source_id: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ):
        self.name = name
        self.source_id = source_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.last_successful_fetch: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.status: str = "unknown"

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
        Returns parsed JSON or text response.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}" if endpoint else self.base_url
        headers = headers or {}
        headers.setdefault("User-Agent", "FloodPulse-AI/1.0 (Tonle Sap Lake Monitoring Platform; Cambodia)")

        client_timeout = httpx.Timeout(self.timeout, connect=10.0)

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=client_timeout, follow_redirects=True) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, params=params, headers=headers)
                    elif method.upper() == "POST":
                        response = await client.post(url, params=params, json=json_body, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    # Handle Rate Limiting (HTTP 429)
                    if response.status_code == 429:
                        retry_after_str = response.headers.get("Retry-After", "60")
                        try:
                            retry_after = int(retry_after_str)
                        except ValueError:
                            retry_after = 60

                        logger.warning(
                            f"[{self.name}] Rate limited by API (429). Retry-After: {retry_after}s. "
                            f"Attempt {attempt}/{self.max_retries}"
                        )
                        if attempt == self.max_retries:
                            raise RateLimitError(
                                f"Rate limit exceeded on {self.name} after {self.max_retries} attempts.",
                                retry_after=retry_after
                            )
                        await asyncio.sleep(min(retry_after, 10))  # Cap wait to 10s for responsiveness
                        continue

                    # Handle 5xx server errors with backoff
                    if response.status_code >= 500:
                        logger.warning(
                            f"[{self.name}] Server returned {response.status_code}. "
                            f"Attempt {attempt}/{self.max_retries}"
                        )
                        if attempt == self.max_retries:
                            response.raise_for_status()
                        delay = self.backoff_factor ** attempt
                        await asyncio.sleep(delay)
                        continue

                    # Raise for client errors (4xx other than 429)
                    response.raise_for_status()

                    # Success!
                    self.last_successful_fetch = datetime.now(timezone.utc)
                    self.status = "active"
                    self.last_error = None
                    await self.update_source_status(status="active", error=None)

                    # Return JSON if content-type indicates, or text
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type or "geo+json" in content_type:
                        return response.json()
                    return response.text

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                err_msg = f"HTTP Error on [{self.name}]: {str(exc)}"
                logger.error(err_msg)
                if attempt == self.max_retries:
                    self.last_error = err_msg
                    self.last_error_time = datetime.now(timezone.utc)
                    self.status = "error"
                    await self.update_source_status(status="error", error=err_msg)
                    raise ConnectorError(err_msg) from exc
                delay = self.backoff_factor ** attempt
                await asyncio.sleep(delay)

            except Exception as exc:
                err_msg = f"Unexpected failure on [{self.name}]: {str(exc)}"
                logger.error(err_msg)
                self.last_error = err_msg
                self.last_error_time = datetime.now(timezone.utc)
                self.status = "error"
                await self.update_source_status(status="error", error=err_msg)
                raise ConnectorError(err_msg) from exc

        raise ConnectorError(f"[{self.name}] Exhausted {self.max_retries} retries without success.")

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
            raise ConnectorError(f"Validation failed for data from {self.name}")
        normalized = self.normalize(raw)
        records_saved = await self.store(normalized)
        return {
            "connector": self.name,
            "status": "success",
            "records_stored": records_saved,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_status(self) -> Dict[str, Any]:
        """Get live status and last sync metrics."""
        db_record = await fetch_one("SELECT * FROM data_sources WHERE name LIKE ?", (f"%{self.name}%",))
        return {
            "name": self.name,
            "source_id": self.source_id,
            "status": self.status if not db_record else db_record.get("status", self.status),
            "last_successful_fetch": self.last_successful_fetch.isoformat() if self.last_successful_fetch else (
                db_record.get("last_successful_fetch") if db_record else None
            ),
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
