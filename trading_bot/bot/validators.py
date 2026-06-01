"""Input validation helpers for CLI arguments."""

from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}

# Binance Futures minimum notional value (USD)
MIN_NOTIONAL = 50.0


def validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty.")
    if not symbol.isalnum():
        raise ValueError(f"Symbol must be alphanumeric. Got: '{symbol}'")
    return symbol


def validate_side(side: str) -> str:
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(f"Side must be one of {VALID_SIDES}. Got: '{side}'")
    return side


def validate_order_type(order_type: str) -> str:
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Order type must be one of {VALID_ORDER_TYPES}. Got: '{order_type}'"
        )
    return order_type


def validate_positive_float(value: str, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a positive number. Got: '{value}'")
    if result <= 0:
        raise ValueError(f"{name} must be positive. Got: {result}")
    return result


def validate_notional(quantity: float, price: float) -> None:
    """Reject orders whose notional value is below Binance's $50 minimum."""
    notional = quantity * price
    if notional < MIN_NOTIONAL:
        min_qty = MIN_NOTIONAL / price
        raise ValueError(
            f"Order notional (qty × price = {quantity} × {price} = ${notional:.2f}) "
            f"is below Binance's minimum of ${MIN_NOTIONAL:.0f}. "
            f"Use quantity ≥ {min_qty:.4f} at this price."
        )


def validate_inputs(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> dict:
    """Validate all inputs and return a clean dict of typed values."""
    validated = {
        "symbol":     validate_symbol(symbol),
        "side":       validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity":   validate_positive_float(quantity, "Quantity"),
    }

    if validated["order_type"] == "LIMIT":
        if price is None:
            raise ValueError("--price is required for LIMIT orders.")
        validated["price"] = validate_positive_float(str(price), "Price")
        # Notional check — catches low qty×price before the API call
        validate_notional(validated["quantity"], validated["price"])

    if validated["order_type"] == "STOP_MARKET":
        if stop_price is None:
            raise ValueError("--stop-price is required for STOP_MARKET orders.")
        validated["stop_price"] = validate_positive_float(str(stop_price), "Stop price")
        # Use stop_price as proxy for notional on stop orders
        validate_notional(validated["quantity"], validated["stop_price"])

    return validated