# Validators module
"""
Input validation utilities for the Elysium trading framework.
"""

import re
from typing import Dict, Any, List, Optional, Union, Tuple


def validate_symbol(symbol: str) -> bool:
    """
    Validate a trading symbol.

    Args:
        symbol: Symbol to validate

    Returns:
        True if valid, False otherwise
    """
    # Simple validation - allow alphanumeric, slash, hyphen, and @ symbol
    pattern = r'^[a-zA-Z0-9\-/\.@]+$'
    return bool(re.match(pattern, symbol))


def validate_price(price: float, min_price: float = 0.0, max_price: Optional[float] = None) -> bool:
    """
    Validate a price value.

    Args:
        price: Price to validate
        min_price: Minimum allowed price
        max_price: Maximum allowed price (optional)

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(price, (int, float)):
        return False

    if price < min_price:
        return False

    if max_price is not None and price > max_price:
        return False

    return True


def validate_size(size: float, min_size: float = 0.0) -> bool:
    """
    Validate an order size.

    Args:
        size: Size to validate
        min_size: Minimum allowed size

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(size, (int, float)):
        return False

    if size < min_size:
        return False

    return True


def validate_address(address: str) -> bool:
    """
    Validate an Ethereum address.

    Args:
        address: Address to validate

    Returns:
        True if valid, False otherwise
    """
    # Ethereum address pattern
    pattern = r'^0x[a-fA-F0-9]{40}$'
    return bool(re.match(pattern, address))


def validate_private_key(private_key: str) -> bool:
    """
    Validate a private key.

    Args:
        private_key: Private key to validate

    Returns:
        True if valid, False otherwise
    """
    # Private key pattern (0x followed by 64 hex chars)
    pattern = r'^0x[a-fA-F0-9]{64}$'
    return bool(re.match(pattern, private_key))


def validate_order_params(
        symbol: str,
        side: str,
        order_type: str,
        size: float,
        price: Optional[float] = None
) -> Tuple[bool, List[str]]:
    """
    Validate order parameters.

    Args:
        symbol: Trading symbol
        side: Order side ("buy" or "sell")
        order_type: Order type ("limit", "market", etc.)
        size: Order size
        price: Order price (optional for market orders)

    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []

    # Validate symbol
    if not validate_symbol(symbol):
        errors.append(f"Invalid symbol: {symbol}")

    # Validate side
    if side.lower() not in ["buy", "sell"]:
        errors.append(f"Invalid side: {side}. Must be 'buy' or 'sell'")

    # Validate order type
    if order_type.lower() not in ["limit", "market", "stop", "take_profit"]:
        errors.append(f"Invalid order type: {order_type}")

    # Validate size
    if not validate_size(size, min_size=0.001):
        errors.append(f"Invalid size: {size}. Must be >= 0.001")

    # Validate price for limit orders
    if order_type.lower() == "limit":
        if price is None:
            errors.append("Price is required for limit orders")
        elif not validate_price(price, min_price=0.00000001):
            errors.append(f"Invalid price: {price}")

    return len(errors) == 0, errors


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate configuration parameters.

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []

    # Validate required fields
    required_fields = ["exchange", "strategy"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required config field: {field}")

    # Validate exchange config
    if "exchange" in config:
        exchange_config = config["exchange"]

        # Validate API credentials
        if "account_address" in exchange_config:
            if not validate_address(exchange_config["account_address"]):
                errors.append("Invalid account address in config")

        if "private_key" in exchange_config:
            if not validate_private_key(exchange_config["private_key"]):
                errors.append("Invalid private key in config")

    # Validate strategy config
    if "strategy" in config:
        strategy_config = config["strategy"]

        # Validate strategy name
        if "name" not in strategy_config:
            errors.append("Missing strategy name in config")

    return len(errors) == 0, errors