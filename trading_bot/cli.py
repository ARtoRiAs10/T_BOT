#!/usr/bin/env python3
"""
Binance Futures Testnet Trading Bot — CLI entry point.

── Standard mode (argparse flags) ───────────────────────────────────────────
    python cli.py --symbol BTCUSDT --side BUY  --type MARKET   --quantity 0.001
    python cli.py --symbol BTCUSDT --side BUY  --type LIMIT    --quantity 0.001 --price 30000
    python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 28000

── Chat / NLP mode (OpenRouter LLM) ─────────────────────────────────────────
    python cli.py --chat
    > buy 0.001 BTC at market
    > limit sell 0.5 ETH at 2000
    > stop market sell 0.002 BTCUSDT if price drops to 28000
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from bot.client import BinanceFuturesClient
from bot.logging_config import setup_logging
from bot.orders import dispatch_order
from bot.validators import validate_inputs

load_dotenv()


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description=(
            "Place Market / Limit / Stop-Market orders on Binance Futures Testnet.\n"
            "Use --chat for natural-language mode powered by OpenRouter LLM."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── NLP / chat mode ───────────────────────────────────────────────────────
    parser.add_argument(
        "--chat", action="store_true",
        help=(
            "Natural-language mode: describe your order in plain English. "
            "Requires OPENROUTER_API_KEY in .env. "
            "Example: 'buy 0.001 BTC at market'"
        ),
    )

    # ── Standard mode flags ───────────────────────────────────────────────────
    parser.add_argument("--symbol",   help="Trading pair, e.g. BTCUSDT")
    parser.add_argument(
        "--side",   choices=["BUY", "SELL", "buy", "sell"],
        help="Order side"
    )
    parser.add_argument(
        "--type", dest="order_type",
        choices=["MARKET", "LIMIT", "STOP_MARKET", "market", "limit", "stop_market"],
        help="Order type"
    )
    parser.add_argument("--quantity",   help="Order quantity, e.g. 0.001")
    parser.add_argument("--price",      default=None, help="Limit price (LIMIT orders)")
    parser.add_argument(
        "--stop-price", dest="stop_price", default=None,
        help="Stop trigger price (STOP_MARKET orders)"
    )
    return parser


# ── Pretty-print helpers ──────────────────────────────────────────────────────

def print_summary(validated: dict, source: str = "args") -> None:
    label = "NLP → Validated" if source == "llm" else "Order Request"
    print(f"\n┌── {label} Summary " + "─" * 32)
    for key, val in validated.items():
        print(f"│  {key:<15}: {val}")
    print("└" + "─" * 54 + "\n")


def print_response(response: dict) -> None:
    FIELDS = [
        "orderId", "symbol", "status", "side", "type",
        "origQty", "executedQty", "avgPrice", "price", "stopPrice",
    ]
    print("┌── Order Response " + "─" * 36)
    for field in FIELDS:
        if field in response:
            print(f"│  {field:<15}: {response[field]}")
    print("└" + "─" * 54 + "\n")


# ── Validation helper ─────────────────────────────────────────────────────────

def get_validated(args, logger, source: str = "args") -> dict:
    """Run validate_inputs and exit cleanly on failure."""
    try:
        return validate_inputs(
            symbol=args.symbol or "",
            side=args.side or "",
            order_type=args.order_type or "",
            quantity=args.quantity or "",
            price=args.price,
            stop_price=args.stop_price,
        )
    except ValueError as exc:
        logger.error(f"Input validation failed ({source}): {exc}")
        print(f"\n[ERROR] {exc}\n")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger = setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    # ── Load Binance credentials ──────────────────────────────────────────────
    api_key    = os.getenv("BINANCE_API_KEY",    "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        logger.error("BINANCE_API_KEY / BINANCE_API_SECRET missing from .env.")
        print("\n[ERROR] Missing Binance credentials. Check your .env file.\n")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # CHAT / NLP MODE  (--chat)
    # ─────────────────────────────────────────────────────────────────────────
    if args.chat:
        from bot.llm_parser import parse_natural_language_order, llm_params_to_cli_kwargs
        from openai import OpenAIError

        print("\n🤖  NLP mode (OpenRouter · openai/gpt-oss-120b:free)")
        print("    Type your order in plain English. Ctrl+C to quit.\n")

        while True:
            try:
                user_input = input("Order ❯ ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye.")
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit", "q"}:
                print("Goodbye.")
                break

            # Step 1 — LLM extracts raw params
            try:
                raw_params = parse_natural_language_order(user_input)
            except ValueError as exc:
                print(f"[LLM ERROR] {exc}\n")
                continue
            except OpenAIError as exc:
                logger.error(f"OpenRouter error: {exc}")
                print(f"[API ERROR] OpenRouter request failed: {exc}\n")
                continue

            # Step 2 — Convert to string kwargs and validate
            kwargs = llm_params_to_cli_kwargs(raw_params)
            try:
                validated = validate_inputs(**kwargs)
            except ValueError as exc:
                logger.error(f"Validation of LLM params failed: {exc}")
                print(f"[VALIDATION ERROR] {exc}\n")
                continue

            print_summary(validated, source="llm")

            # Step 3 — Confirm before placing
            confirm = input("Confirm order? [y/N] ").strip().lower()
            if confirm not in {"y", "yes"}:
                print("Order cancelled.\n")
                continue

            # Step 4 — Place order
            try:
                client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
                response = dispatch_order(client, validated)
            except Exception as exc:
                logger.error(f"Order placement failed: {exc}")
                print(f"\n[FAILED] {exc}\n")
                continue

            print_response(response)
            logger.info(f"Order placed successfully | orderId={response.get('orderId')}")
            print("[SUCCESS] ✓ Order placed successfully.\n")

    # ─────────────────────────────────────────────────────────────────────────
    # STANDARD MODE  (argparse flags)
    # ─────────────────────────────────────────────────────────────────────────
    else:
        # Ensure required flags are present in standard mode
        missing = [f for f in ["symbol", "side", "order_type", "quantity"]
                   if not getattr(args, f if f != "order_type" else "order_type", None)]
        # argparse dest for --type is order_type
        required_flags = {"symbol": args.symbol, "side": args.side,
                          "type": args.order_type, "quantity": args.quantity}
        missing = [f"--{k}" for k, v in required_flags.items() if not v]
        if missing:
            parser.error(
                f"The following flags are required in standard mode: {', '.join(missing)}\n"
                "  Use --chat for natural-language input."
            )

        validated = get_validated(args, logger, source="args")
        print_summary(validated, source="args")

        try:
            client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
            response = dispatch_order(client, validated)
        except Exception as exc:
            logger.error(f"Order placement failed: {exc}")
            print(f"\n[FAILED] Could not place order: {exc}\n")
            sys.exit(1)

        print_response(response)
        logger.info(f"Order placed successfully | orderId={response.get('orderId')}")
        print("[SUCCESS] ✓ Order placed successfully.\n")


if __name__ == "__main__":
    main()
