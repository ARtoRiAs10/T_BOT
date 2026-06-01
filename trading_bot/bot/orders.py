"""Order placement logic for Binance Futures Testnet."""

import logging

from .client import BinanceFuturesClient
from .config import DEFAULT_TIME_IN_FORCE, ORDER_ENDPOINT

logger = logging.getLogger("trading_bot.orders")


def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
) -> dict:
    """Place a MARKET order on Binance Futures Testnet."""
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
    }
    logger.info(f"Placing MARKET order | symbol={symbol} side={side} qty={quantity}")
    return client.post(ORDER_ENDPOINT, params)


def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    time_in_force: str = DEFAULT_TIME_IN_FORCE,
) -> dict:
    """Place a LIMIT order on Binance Futures Testnet."""
    params = {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "quantity": quantity,
        "price": price,
        "timeInForce": time_in_force,
    }
    logger.info(
        f"Placing LIMIT order | symbol={symbol} side={side} "
        f"qty={quantity} price={price} tif={time_in_force}"
    )
    return client.post(ORDER_ENDPOINT, params)


def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
) -> dict:
    """Place a STOP_MARKET order on Binance Futures Testnet (bonus order type)."""
    params = {
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "quantity": quantity,
        "stopPrice": stop_price,
    }
    logger.info(
        f"Placing STOP_MARKET order | symbol={symbol} side={side} "
        f"qty={quantity} stopPrice={stop_price}"
    )
    return client.post(ORDER_ENDPOINT, params)


def dispatch_order(client: BinanceFuturesClient, validated: dict) -> dict:
    """Route to the correct order function based on validated inputs."""
    order_type = validated["order_type"]

    if order_type == "MARKET":
        return place_market_order(
            client,
            symbol=validated["symbol"],
            side=validated["side"],
            quantity=validated["quantity"],
        )
    if order_type == "LIMIT":
        return place_limit_order(
            client,
            symbol=validated["symbol"],
            side=validated["side"],
            quantity=validated["quantity"],
            price=validated["price"],
        )
    if order_type == "STOP_MARKET":
        return place_stop_market_order(
            client,
            symbol=validated["symbol"],
            side=validated["side"],
            quantity=validated["quantity"],
            stop_price=validated["stop_price"],
        )

    raise ValueError(f"Unsupported order type: {order_type}")
