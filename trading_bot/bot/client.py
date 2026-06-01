"""Binance Futures Testnet REST API client."""

import hashlib
import hmac
import logging
import time
from typing import Any, Dict
from urllib.parse import urlencode

import requests

from .config import BASE_URL, DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger("trading_bot.client")


class BinanceFuturesClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Handles:
        - HMAC-SHA256 request signing
        - Session management with API-key header
        - Structured error logging
    """

    BASE_URL = BASE_URL

    def __init__(self, api_key: str, api_secret: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        if not api_key or not api_secret:
            raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must not be empty.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    # ── Internal helpers ─────────────────────────────────────────────────

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _build_signed_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        signed = {**params, "timestamp": self._timestamp()}
        signed["signature"] = self._sign(signed)
        return signed

    # ── Public API ───────────────────────────────────────────────────────

    def post(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a signed POST request and return the parsed JSON response."""
        url = f"{self.BASE_URL}{path}"
        signed_params = self._build_signed_params(params)

        logger.debug(f"POST {path} | raw params (excl. signature/timestamp): {params}")

        try:
            response = self.session.post(url, params=signed_params, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            body = response.text
            logger.error(
                f"HTTP {response.status_code} error on POST {path}: {body}"
            )
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"Network connection error: {exc}")
            raise
        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {self.timeout}s")
            raise

        data: Dict[str, Any] = response.json()
        logger.debug(f"Response from {path}: {data}")
        return data
