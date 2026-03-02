"""Cloudflare API client with retry logic, rate-limit handling, and error checking."""

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger("cf_migrator")

DEFAULT_BASE_URL = "https://api.cloudflare.com/client/v4"
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubled each retry
RATE_LIMIT_SLEEP = 5  # seconds to sleep on 429


class CloudflareAPIError(Exception):
    """Raised when a Cloudflare API call fails after retries."""

    def __init__(self, message: str, status_code: int = 0, errors: Optional[list] = None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []


class CloudflareClient:
    """Thin wrapper around the Cloudflare REST API with robust error handling."""

    def __init__(self, api_token: str, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict | list] = None,
    ) -> dict[str, Any]:
        """Execute an API request with retry and rate-limit handling.

        Returns the full JSON response body on success.
        Raises CloudflareAPIError on failure after retries.
        """
        url = f"{self.base_url}{path}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(
                    "API %s %s (attempt %d/%d)", method, path, attempt, MAX_RETRIES
                )
                resp = self.session.request(
                    method, url, params=params, json=json_body, timeout=30
                )

                if resp.status_code == 429:
                    wait = RATE_LIMIT_SLEEP * attempt
                    logger.warning("Rate limited — sleeping %ds before retry", wait)
                    time.sleep(wait)
                    continue

                body = resp.json()

                if not body.get("success", False):
                    errors = body.get("errors", [])
                    msg = "; ".join(e.get("message", str(e)) for e in errors) or resp.text
                    raise CloudflareAPIError(
                        f"API error on {method} {path}: {msg}",
                        status_code=resp.status_code,
                        errors=errors,
                    )

                return body

            except CloudflareAPIError:
                raise
            except requests.RequestException as exc:
                last_exc = exc
                wait = RETRY_BACKOFF * attempt
                logger.warning(
                    "Request failed (%s) — retrying in %ds", exc, wait
                )
                time.sleep(wait)

        raise CloudflareAPIError(
            f"Request to {path} failed after {MAX_RETRIES} retries: {last_exc}"
        )

    def get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, json_body: Optional[dict | list] = None) -> dict[str, Any]:
        return self._request("POST", path, json_body=json_body)

    def put(self, path: str, json_body: Optional[dict | list] = None) -> dict[str, Any]:
        return self._request("PUT", path, json_body=json_body)

    def patch(self, path: str, json_body: Optional[dict | list] = None) -> dict[str, Any]:
        return self._request("PATCH", path, json_body=json_body)

    def delete(self, path: str) -> dict[str, Any]:
        return self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def get_all_pages(self, path: str, params: Optional[dict] = None) -> list[dict]:
        """Fetch all pages of a paginated Cloudflare endpoint.

        Returns the combined list of result items.
        """
        params = dict(params or {})
        params.setdefault("per_page", 50)
        params.setdefault("page", 1)
        all_items: list[dict] = []

        while True:
            body = self.get(path, params=params)
            result = body.get("result")
            if result is None:
                break
            if isinstance(result, list):
                all_items.extend(result)
            else:
                all_items.append(result)

            result_info = body.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            current_page = result_info.get("page", params["page"])

            if current_page >= total_pages:
                break
            params["page"] = current_page + 1

        return all_items

    # ------------------------------------------------------------------
    # Account / zone helpers
    # ------------------------------------------------------------------

    def list_zones(self, account_id: Optional[str] = None) -> list[dict]:
        """Return all zones, optionally filtered by account ID."""
        params: dict[str, Any] = {}
        if account_id:
            params["account.id"] = account_id
        return self.get_all_pages("/zones", params=params)

    def verify_token(self) -> bool:
        """Return True if the current token is valid."""
        try:
            body = self.get("/user/tokens/verify")
            status = body.get("result", {}).get("status", "")
            return status == "active"
        except CloudflareAPIError:
            return False
