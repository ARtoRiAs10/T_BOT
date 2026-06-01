"""
bot/llm_parser.py

Uses OpenRouter (openai/gpt-oss-120b:free) to convert a plain-English
trade description into structured order parameters, which are then fed
into the standard validate_inputs → dispatch_order pipeline.

Example inputs the LLM understands:
    "buy 0.001 BTC at market"
    "sell 0.5 ETH with a limit at 2000"
    "place a stop market sell for 0.001 BTCUSDT if price drops to 28000"
"""

import json
import logging
import os
from typing import Optional

from openai import OpenAI, OpenAIError

from .config import LLM_MAX_TOKENS, LLM_TEMPERATURE, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger("trading_bot.llm_parser")

# ── System prompt ──────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """
You are a trading parameter extractor for Binance Futures (USDT-M pairs).

The user will describe a trade in natural language. Your job is to extract the
order parameters and return ONLY a valid JSON object — no markdown, no explanation.

Required fields (always present):
  symbol      : string  — trading pair, e.g. "BTCUSDT". Always UPPERCASE, always ends in "USDT".
  side        : string  — "BUY" or "SELL"
  order_type  : string  — "MARKET", "LIMIT", or "STOP_MARKET"
  quantity    : number  — positive float, e.g. 0.001

Conditional fields (include ONLY when applicable):
  price       : number  — required when order_type is "LIMIT"
  stop_price  : number  — required when order_type is "STOP_MARKET"

If you cannot extract all required fields, return:
  {"error": "<short reason>"}

Examples:

User: "buy 0.001 BTC at market"
Response: {"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.001}

User: "limit buy 0.01 ETH at 2000"
Response: {"symbol":"ETHUSDT","side":"BUY","order_type":"LIMIT","quantity":0.01,"price":2000}

User: "sell 0.002 BTCUSDT stop market if it drops to 28000"
Response: {"symbol":"BTCUSDT","side":"SELL","order_type":"STOP_MARKET","quantity":0.002,"stop_price":28000}

User: "do something with crypto"
Response: {"error":"cannot determine side, order type, or quantity"}
""".strip()


# ── Public API ─────────────────────────────────────────────────────────────────

def get_llm_client() -> OpenAI:
    """Build and return an OpenAI-compatible client pointed at OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file to use the natural-language (--chat) mode."
        )
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        default_headers={
            # Recommended by OpenRouter for usage tracking / leaderboard
            "HTTP-Referer": "https://github.com/trading-bot",
            "X-Title": "Binance Futures Trading Bot",
        },
    )


def parse_natural_language_order(user_input: str) -> dict:
    """
    Send a plain-English trade description to the OpenRouter LLM and return
    a dict of raw order parameters.

    The returned dict is *not* yet validated — always pass it through
    validate_inputs() before placing an order.

    Raises:
        ValueError   – LLM returned an error payload or non-parseable output.
        OpenAIError  – network / auth / quota failure from the OpenRouter API.
    """
    client = get_llm_client()
    logger.info(f"Sending to LLM ({OPENROUTER_MODEL}): {user_input!r}")

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_input},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
    except OpenAIError as exc:
        logger.error(f"OpenRouter API call failed: {exc}")
        raise

    raw: str = response.choices[0].message.content.strip()
    logger.debug(f"LLM raw response: {raw!r}")

    # Strip accidental markdown fences if the model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned non-JSON: {raw!r}")
        raise ValueError(f"LLM returned non-JSON output: {raw!r}") from exc

    if "error" in parsed:
        raise ValueError(f"LLM could not parse your order: {parsed['error']}")

    logger.info(f"LLM extracted params: {parsed}")
    return parsed


def llm_params_to_cli_kwargs(parsed: dict) -> dict:
    """
    Convert the raw LLM-parsed dict into keyword arguments compatible with
    validate_inputs().  Numeric values become strings as argparse would produce.
    """
    kwargs: dict = {
        "symbol":     str(parsed.get("symbol", "")),
        "side":       str(parsed.get("side", "")),
        "order_type": str(parsed.get("order_type", "")),
        "quantity":   str(parsed.get("quantity", "")),
        "price":      str(parsed["price"])      if "price"      in parsed else None,
        "stop_price": str(parsed["stop_price"]) if "stop_price" in parsed else None,
    }
    return kwargs
