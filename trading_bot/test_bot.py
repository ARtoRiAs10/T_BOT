#!/usr/bin/env python3
"""
test_bot.py — offline integration test for the trading bot.

Mocks the BinanceFuturesClient.post() method so you can verify the
full CLI ➜ validator ➜ orders pipeline without real API credentials.

Run with:
    python test_bot.py
"""

import sys
import json
import unittest
from unittest.mock import MagicMock, patch

# ── Make sure local modules are importable ─────────────────────────────────────
sys.path.insert(0, ".")

from bot.validators import validate_inputs
from bot.orders import (
    place_market_order,
    place_limit_order,
    place_stop_market_order,
    dispatch_order,
)

# ── Fake API responses (mirror real Binance Futures testnet shape) ─────────────
MOCK_MARKET_RESPONSE = {
    "orderId": 3951475001,
    "symbol": "BTCUSDT",
    "status": "FILLED",
    "side": "BUY",
    "type": "MARKET",
    "origQty": "0.001",
    "executedQty": "0.001",
    "avgPrice": "43210.50",
    "price": "0",
    "timeInForce": "GTC",
    "updateTime": 1717238400000,
}

MOCK_LIMIT_RESPONSE = {
    "orderId": 3951475002,
    "symbol": "BTCUSDT",
    "status": "NEW",
    "side": "BUY",
    "type": "LIMIT",
    "origQty": "0.001",
    "executedQty": "0",
    "avgPrice": "0.00",
    "price": "30000.00",
    "timeInForce": "GTC",
    "updateTime": 1717238500000,
}

MOCK_STOP_RESPONSE = {
    "orderId": 3951475003,
    "symbol": "BTCUSDT",
    "status": "NEW",
    "side": "SELL",
    "type": "STOP_MARKET",
    "origQty": "0.001",
    "executedQty": "0",
    "stopPrice": "28000.00",
    "updateTime": 1717238600000,
}


# ── Helper ─────────────────────────────────────────────────────────────────────
def make_mock_client(response: dict):
    client = MagicMock()
    client.post.return_value = response
    return client


# ── Test cases ─────────────────────────────────────────────────────────────────
class TestValidators(unittest.TestCase):

    def test_market_order_valid(self):
        v = validate_inputs("BTCUSDT", "BUY", "MARKET", "0.001")
        self.assertEqual(v["symbol"], "BTCUSDT")
        self.assertEqual(v["side"], "BUY")
        self.assertEqual(v["order_type"], "MARKET")
        self.assertAlmostEqual(v["quantity"], 0.001)

    def test_limit_order_valid(self):
        v = validate_inputs("ETHUSDT", "SELL", "LIMIT", "0.01", price="2000")
        self.assertAlmostEqual(v["price"], 2000.0)

    def test_limit_order_missing_price(self):
        with self.assertRaises(ValueError):
            validate_inputs("BTCUSDT", "BUY", "LIMIT", "0.001")

    def test_stop_market_missing_stop_price(self):
        with self.assertRaises(ValueError):
            validate_inputs("BTCUSDT", "SELL", "STOP_MARKET", "0.001")

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            validate_inputs("BTCUSDT", "HOLD", "MARKET", "0.001")

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            validate_inputs("BTCUSDT", "BUY", "MARKET", "-1")

    def test_zero_quantity(self):
        with self.assertRaises(ValueError):
            validate_inputs("BTCUSDT", "BUY", "MARKET", "0")

    def test_symbol_normalised_to_uppercase(self):
        v = validate_inputs("btcusdt", "buy", "market", "0.001")
        self.assertEqual(v["symbol"], "BTCUSDT")
        self.assertEqual(v["side"], "BUY")


class TestOrders(unittest.TestCase):

    def test_place_market_order(self):
        client = make_mock_client(MOCK_MARKET_RESPONSE)
        resp = place_market_order(client, "BTCUSDT", "BUY", 0.001)
        self.assertEqual(resp["orderId"], 3951475001)
        self.assertEqual(resp["status"], "FILLED")
        client.post.assert_called_once()

    def test_place_limit_order(self):
        client = make_mock_client(MOCK_LIMIT_RESPONSE)
        resp = place_limit_order(client, "BTCUSDT", "BUY", 0.001, 30000.0)
        self.assertEqual(resp["orderId"], 3951475002)
        self.assertEqual(resp["status"], "NEW")
        client.post.assert_called_once()

    def test_place_stop_market_order(self):
        client = make_mock_client(MOCK_STOP_RESPONSE)
        resp = place_stop_market_order(client, "BTCUSDT", "SELL", 0.001, 28000.0)
        self.assertEqual(resp["orderId"], 3951475003)
        self.assertEqual(resp["type"], "STOP_MARKET")
        client.post.assert_called_once()


class TestDispatch(unittest.TestCase):

    def test_dispatch_market(self):
        client = make_mock_client(MOCK_MARKET_RESPONSE)
        validated = {"symbol": "BTCUSDT", "side": "BUY", "order_type": "MARKET", "quantity": 0.001}
        resp = dispatch_order(client, validated)
        self.assertEqual(resp["type"], "MARKET")

    def test_dispatch_limit(self):
        client = make_mock_client(MOCK_LIMIT_RESPONSE)
        validated = {
            "symbol": "BTCUSDT", "side": "BUY",
            "order_type": "LIMIT", "quantity": 0.001, "price": 30000.0,
        }
        resp = dispatch_order(client, validated)
        self.assertEqual(resp["type"], "LIMIT")

    def test_dispatch_stop_market(self):
        client = make_mock_client(MOCK_STOP_RESPONSE)
        validated = {
            "symbol": "BTCUSDT", "side": "SELL",
            "order_type": "STOP_MARKET", "quantity": 0.001, "stop_price": 28000.0,
        }
        resp = dispatch_order(client, validated)
        self.assertEqual(resp["type"], "STOP_MARKET")

    def test_dispatch_unknown_type(self):
        client = make_mock_client({})
        with self.assertRaises(ValueError):
            dispatch_order(client, {
                "symbol": "BTCUSDT", "side": "BUY",
                "order_type": "ICEBERG", "quantity": 0.001,
            })


class TestLLMParser(unittest.TestCase):
    """Tests for bot.llm_parser — mocks the OpenRouter API entirely."""

    def _mock_llm_response(self, json_payload: dict):
        """Return a mock OpenAI response whose first choice contains json_payload."""
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(json_payload)
        return mock_resp

    @patch("bot.llm_parser.get_llm_client")
    def test_parse_market_order(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_llm_response(
            {"symbol": "BTCUSDT", "side": "BUY", "order_type": "MARKET", "quantity": 0.001}
        )
        mock_get_client.return_value = mock_client

        from bot.llm_parser import parse_natural_language_order
        result = parse_natural_language_order("buy 0.001 BTC at market")
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["order_type"], "MARKET")

    @patch("bot.llm_parser.get_llm_client")
    def test_parse_limit_order(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_llm_response(
            {"symbol": "ETHUSDT", "side": "BUY", "order_type": "LIMIT",
             "quantity": 0.01, "price": 2000}
        )
        mock_get_client.return_value = mock_client

        from bot.llm_parser import parse_natural_language_order
        result = parse_natural_language_order("limit buy 0.01 ETH at 2000")
        self.assertEqual(result["price"], 2000)

    @patch("bot.llm_parser.get_llm_client")
    def test_parse_stop_market_order(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_llm_response(
            {"symbol": "BTCUSDT", "side": "SELL", "order_type": "STOP_MARKET",
             "quantity": 0.002, "stop_price": 28000}
        )
        mock_get_client.return_value = mock_client

        from bot.llm_parser import parse_natural_language_order
        result = parse_natural_language_order("stop market sell 0.002 BTCUSDT at 28000")
        self.assertEqual(result["stop_price"], 28000)

    @patch("bot.llm_parser.get_llm_client")
    def test_llm_error_payload_raises(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_llm_response(
            {"error": "cannot determine side or quantity"}
        )
        mock_get_client.return_value = mock_client

        from bot.llm_parser import parse_natural_language_order
        with self.assertRaises(ValueError):
            parse_natural_language_order("do something with crypto please")

    @patch("bot.llm_parser.get_llm_client")
    def test_llm_strips_markdown_fences(self, mock_get_client):
        """LLM sometimes wraps JSON in ```json ... ``` — parser must handle it."""
        mock_client = MagicMock()
        raw = MagicMock()
        raw.choices[0].message.content = (
            "```json\n"
            '{"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.001}\n'
            "```"
        )
        mock_client.chat.completions.create.return_value = raw
        mock_get_client.return_value = mock_client

        from bot.llm_parser import parse_natural_language_order
        result = parse_natural_language_order("buy 0.001 BTC at market")
        self.assertEqual(result["symbol"], "BTCUSDT")

    def test_llm_params_to_cli_kwargs_market(self):
        from bot.llm_parser import llm_params_to_cli_kwargs
        kwargs = llm_params_to_cli_kwargs(
            {"symbol": "BTCUSDT", "side": "BUY", "order_type": "MARKET", "quantity": 0.001}
        )
        self.assertEqual(kwargs["quantity"], "0.001")
        self.assertIsNone(kwargs["price"])
        self.assertIsNone(kwargs["stop_price"])

    def test_llm_params_to_cli_kwargs_limit(self):
        from bot.llm_parser import llm_params_to_cli_kwargs
        kwargs = llm_params_to_cli_kwargs(
            {"symbol": "ETHUSDT", "side": "BUY", "order_type": "LIMIT",
             "quantity": 0.01, "price": 2000}
        )
        self.assertEqual(kwargs["price"], "2000")
        self.assertIsNone(kwargs["stop_price"])


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Trading Bot — Offline Unit Tests")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestValidators, TestOrders, TestDispatch, TestLLMParser]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
