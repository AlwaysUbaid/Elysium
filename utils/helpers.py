# Helpers module
"""
Utility helper functions for the Elysium trading framework.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import eth_account
from eth_account.signers.local import LocalAccount

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants as hl_constants


def setup_exchange(
        secret_key: str,
        account_address: Optional[str] = None,
        base_url: str = hl_constants.MAINNET_API_URL
) -> Tuple[str, Info, Exchange]:
    """
    Set up Hyperliquid exchange connection.

    Args:
        secret_key: Private key for signing transactions
        account_address: Account address (if different from wallet)
        base_url: API URL

    Returns:
        Tuple of (address, info, exchange)
    """
    # Initialize wallet
    account: LocalAccount = eth_account.Account.from_key(secret_key)
    address = account_address or account.address

    # Initialize info and exchange
    info = Info(base_url=base_url)
    exchange = Exchange(account, base_url=base_url, account_address=address)

    logging.info(f"Exchange set up for account: {address}")

    return address, info, exchange


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error(f"Error loading config from {config_path}: {str(e)}")
        return {}


def save_config(config: Dict[str, Any], config_path: str) -> bool:
    """
    Save configuration to JSON file.

    Args:
        config: Configuration dictionary
        config_path: Path to config file

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving config to {config_path}: {str(e)}")
        return False


def format_price(price: float, tick_size: float = 0.0001) -> float:
    """
    Format price to respect tick size.

    Args:
        price: Raw price
        tick_size: Minimum price increment

    Returns:
        Formatted price
    """
    # Round to nearest tick
    return round(price / tick_size) * tick_size


def format_size(size: float, min_size: float = 0.001, step_size: float = 0.001) -> float:
    """
    Format order size to respect minimum and step size.

    Args:
        size: Raw size
        min_size: Minimum order size
        step_size: Size increment

    Returns:
        Formatted size
    """
    # Ensure minimum size
    size = max(size, min_size)

    # Round to nearest step
    return round(size / step_size) * step_size


def calculate_vwap(trades: List[Dict[str, Any]]) -> float:
    """
    Calculate volume-weighted average price from trades.

    Args:
        trades: List of trades with 'price' and 'size' fields

    Returns:
        VWAP
    """
    if not trades:
        return 0.0

    total_volume = 0.0
    volume_price_sum = 0.0

    for trade in trades:
        size = float(trade['size']) if isinstance(trade['size'], str) else trade['size']
        price = float(trade['price']) if isinstance(trade['price'], str) else trade['price']

        total_volume += size
        volume_price_sum += size * price

    if total_volume == 0:
        return 0.0

    return volume_price_sum / total_volume


def calculate_order_book_imbalance(bids: List[Dict[str, Any]], asks: List[Dict[str, Any]], levels: int = 5) -> float:
    """
    Calculate order book imbalance (bid volume / total volume).

    Args:
        bids: List of bid levels with 'price' and 'size' fields
        asks: List of ask levels with 'price' and 'size' fields
        levels: Number of price levels to consider

    Returns:
        Imbalance ratio (0.5 = balanced, >0.5 = more bids, <0.5 = more asks)
    """
    bid_volume = 0.0
    ask_volume = 0.0

    # Sum bid volume
    for i, bid in enumerate(bids):
        if i >= levels:
            break
        bid_volume += float(bid['size']) if isinstance(bid['size'], str) else bid['size']

    # Sum ask volume
    for i, ask in enumerate(asks):
        if i >= levels:
            break
        ask_volume += float(ask['size']) if isinstance(ask['size'], str) else ask['size']

    total_volume = bid_volume + ask_volume

    if total_volume == 0:
        return 0.5  # Balanced if no volume

    return bid_volume / total_volume


def retry_api_call(func, *args, max_attempts: int = 3, backoff_factor: float = 2.0, **kwargs):
    """
    Retry an API call with exponential backoff.

    Args:
        func: Function to call
        *args: Positional arguments for the function
        max_attempts: Maximum number of retry attempts
        backoff_factor: Factor to increase wait time between retries
        **kwargs: Keyword arguments for the function

    Returns:
        Function result

    Raises:
        Exception: If all retry attempts fail
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt < max_attempts:
                # Calculate wait time with exponential backoff
                wait_time = backoff_factor ** (attempt - 1)
                logging.warning(
                    f"API call failed (attempt {attempt}/{max_attempts}), retrying in {wait_time:.1f}s: {str(e)}")
                time.sleep(wait_time)

    # If we get here, all retry attempts failed
    raise last_exception