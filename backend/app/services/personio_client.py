"""Async Personio API client with TTL-based token caching.

This is the single integration point with the Personio API. Phase 13 (sync
service) depends on this module to fetch employees, attendances, and absences.

Decisions:
  D-09 / D-10: Custom exception hierarchy with user-facing error messages.
  D-12: Token cached in-memory (not persisted to DB) — lost on container restart.
  D-13: Proactive token refresh if <60 s remaining on current token.
"""
import time
import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERSONIO_BASE_URL = "https://api.personio.de/v1"
TOKEN_TTL_SECONDS = 86400   # 24 hours (Personio default)
TOKEN_REFRESH_BUFFER = 60   # Re-auth if <60s remaining (D-13)


# ---------------------------------------------------------------------------
# Exception hierarchy (D-09, D-10)
# ---------------------------------------------------------------------------


class PersonioAPIError(Exception):
    """Base class for all Personio client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PersonioAuthError(PersonioAPIError):
    """Raised on HTTP 401 — invalid or expired credentials."""


class PersonioRateLimitError(PersonioAPIError):
    """Raised on HTTP 429 — rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class PersonioNetworkError(PersonioAPIError):
    """Raised on timeout or connection failure — Personio unreachable."""


# ---------------------------------------------------------------------------
# PersonioClient
# ---------------------------------------------------------------------------


class PersonioClient:
    """Async HTTP client for the Personio v1 API.

    Usage:
        client = PersonioClient(client_id="...", client_secret="...")
        token = await client._get_valid_token()
        # ... make API calls using client._http with token in Authorization header
        await client.close()
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._http = httpx.AsyncClient(
            base_url=PERSONIO_BASE_URL,
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client. Call on app shutdown."""
        await self._http.aclose()

    async def authenticate(self) -> str:
        """POST /auth with credentials, cache and return the bearer token.

        Raises:
            PersonioAuthError: HTTP 401 — invalid credentials.
            PersonioRateLimitError: HTTP 429 — rate limited, with retry_after.
            PersonioNetworkError: Timeout or connection failure.
            PersonioAPIError: Any other non-success HTTP status.
        """
        try:
            resp = await self._http.post(
                "/auth",
                json={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        except httpx.TimeoutException as exc:
            raise PersonioNetworkError(
                f"Personio unreachable (timeout): {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise PersonioNetworkError(
                f"Personio unreachable: {exc}"
            ) from exc

        if resp.status_code == 401:
            raise PersonioAuthError("Invalid credentials", status_code=401)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            raise PersonioRateLimitError(
                f"Rate limited, retry in {retry_after}s",
                retry_after=retry_after,
            )

        if resp.is_error:
            raise PersonioAPIError(
                f"Personio auth failed with status {resp.status_code}",
                status_code=resp.status_code,
            )

        token: str = resp.json()["data"]["token"]
        self._token = token
        self._expires_at = time.monotonic() + TOKEN_TTL_SECONDS
        return token

    async def _get_valid_token(self) -> str:
        """Return a cached token, re-authenticating if missing or near expiry.

        Proactively refreshes when <TOKEN_REFRESH_BUFFER seconds remain (D-13).
        """
        if (
            self._token is None
            or time.monotonic() > self._expires_at - TOKEN_REFRESH_BUFFER
        ):
            await self.authenticate()

        # authenticate() always sets self._token; assertion for type narrowing
        assert self._token is not None
        return self._token

    async def fetch_employees(self) -> list[dict]:
        """Paginated GET /company/employees. Returns list of raw employee dicts.

        Uses offset-based pagination with limit=50. Loops until response is
        smaller than the limit (i.e., last page).
        """
        token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        results: list[dict] = []
        offset = 0
        limit = 50
        while True:
            try:
                resp = await self._http.get(
                    "/company/employees",
                    headers=headers,
                    params={"limit": limit, "offset": offset},
                )
            except httpx.TimeoutException as exc:
                raise PersonioNetworkError(f"Personio unreachable (timeout): {exc}") from exc
            except httpx.RequestError as exc:
                raise PersonioNetworkError(f"Personio unreachable: {exc}") from exc
            if resp.status_code == 401:
                raise PersonioAuthError("Invalid credentials", status_code=401)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "60"))
                raise PersonioRateLimitError(f"Rate limited, retry in {retry_after}s", retry_after=retry_after)
            if resp.is_error:
                raise PersonioAPIError(f"Personio API error {resp.status_code}", status_code=resp.status_code)
            data = resp.json()["data"]
            results.extend(data)
            if len(data) < limit:
                break
            offset += limit
        return results

    async def fetch_attendances(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Paginated GET /company/attendances. Returns list of raw attendance dicts.

        Personio requires start_date and end_date (YYYY-MM-DD). Callers (hr_sync)
        are expected to compute the window from DB state (earliest hire_date for
        full backfill, max(stored_date)-14d for incremental). As a safety net,
        falls back to a far-past epoch → today if either param is missing, so
        that a bare `fetch_attendances()` still returns all available data.

        429 responses are retried with exponential backoff (up to 3 attempts,
        starting at Retry-After seconds or 30s).
        """
        if not start_date or not end_date:
            from datetime import date
            end_date = date.today().isoformat()
            start_date = start_date or "2000-01-01"
        token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        results: list[dict] = []
        offset = 0
        limit = 50
        while True:
            resp = await self._get_with_backoff(
                "/company/attendances",
                headers=headers,
                params={
                    "limit": limit,
                    "offset": offset,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            data = resp.json()["data"]
            results.extend(data)
            if len(data) < limit:
                break
            offset += limit
        return results

    async def _get_with_backoff(
        self,
        path: str,
        *,
        headers: dict,
        params: dict,
        max_retries: int = 3,
    ):
        """GET with exponential backoff on 429. Other errors raise immediately.

        Delay = max(Retry-After, 2 ** attempt * 30s). Raises PersonioRateLimitError
        after exhausting retries so the caller can mark the sync as error.
        """
        import asyncio

        for attempt in range(max_retries + 1):
            try:
                resp = await self._http.get(path, headers=headers, params=params)
            except httpx.TimeoutException as exc:
                raise PersonioNetworkError(f"Personio unreachable (timeout): {exc}") from exc
            except httpx.RequestError as exc:
                raise PersonioNetworkError(f"Personio unreachable: {exc}") from exc
            if resp.status_code == 401:
                raise PersonioAuthError("Invalid credentials", status_code=401)
            if resp.status_code == 429:
                if attempt == max_retries:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    raise PersonioRateLimitError(
                        f"Rate limited after {max_retries} retries, retry in {retry_after}s",
                        retry_after=retry_after,
                    )
                retry_after = int(resp.headers.get("Retry-After", "30"))
                delay = max(retry_after, (2 ** attempt) * 30)
                await asyncio.sleep(delay)
                continue
            if resp.is_error:
                raise PersonioAPIError(
                    f"Personio API error {resp.status_code}",
                    status_code=resp.status_code,
                )
            return resp
        # unreachable — loop either returns or raises
        raise PersonioAPIError("unreachable: backoff loop exited without response")

    async def fetch_absences(self) -> list[dict]:
        """Paginated GET /company/absence-periods. Returns list of raw absence dicts."""
        token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        results: list[dict] = []
        offset = 0
        limit = 50
        while True:
            try:
                resp = await self._http.get(
                    "/company/absence-periods",
                    headers=headers,
                    params={"limit": limit, "offset": offset},
                )
            except httpx.TimeoutException as exc:
                raise PersonioNetworkError(f"Personio unreachable (timeout): {exc}") from exc
            except httpx.RequestError as exc:
                raise PersonioNetworkError(f"Personio unreachable: {exc}") from exc
            if resp.status_code == 401:
                raise PersonioAuthError("Invalid credentials", status_code=401)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "60"))
                raise PersonioRateLimitError(f"Rate limited, retry in {retry_after}s", retry_after=retry_after)
            if resp.is_error:
                raise PersonioAPIError(f"Personio API error {resp.status_code}", status_code=resp.status_code)
            data = resp.json()["data"]
            results.extend(data)
            if len(data) < limit:
                break
            offset += limit
        return results

    async def fetch_absence_types(self) -> list[dict]:
        """Paginated GET /company/time-off-types. Returns list of absence type dicts.

        Uses the correct v1 endpoint path (not /company/absence-types, which
        returns 404).
        """
        token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = await self._http.get(
                "/company/time-off-types",
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise PersonioNetworkError(f"Personio unreachable (timeout): {exc}") from exc
        except httpx.RequestError as exc:
            raise PersonioNetworkError(f"Personio unreachable: {exc}") from exc
        if resp.status_code == 401:
            raise PersonioAuthError("Invalid credentials", status_code=401)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            raise PersonioRateLimitError(f"Rate limited, retry in {retry_after}s", retry_after=retry_after)
        if resp.is_error:
            raise PersonioAPIError(f"Personio API error {resp.status_code}", status_code=resp.status_code)
        return resp.json()["data"]
