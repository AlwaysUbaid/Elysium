# Initialize the module
"""
Utilities module for Elysium trading platform.

This module provides utility functions for the Elysium platform,
including config management, logging, and helper functions.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union

import eth_account
import pandas as pd
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO, logfile: Optional[str] = "elysium.log") -> None:
    """
    Set up logging for the Elysium platform.

    Args:
        level: Logging level
        logfile: Log file path (or None for console only)
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logging.getLogger().addHandler(file_handler)

    logger.info(f"Logging initialized with level {level}")


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """
    Load configuration from file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        return {}

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        logger.info(f"Loaded configuration from {config_path}")
        return config

    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return {}


def save_config(config: Dict[str, Any], config_path: str = "config.json") -> bool:
    """
    Save configuration to file.

    Args:
        config: Configuration dictionary
        config_path: Path to configuration file

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Saved configuration to {config_path}")
        return True

    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        return False


def initialize_exchange(
        wallet_address: str,
        secret_key: str,
        use_testnet: bool = False
) -> Tuple[Exchange, Info]:
    """
    Initialize Hyperliquid exchange connection.

    Args:
        wallet_address: Wallet address
        secret_key: Private key
        use_testnet: Whether to use testnet

    Returns:
        Tuple of (Exchange, Info) instances
    """
    try:
        # Initialize wallet
        wallet: LocalAccount = eth_account.Account.from_key(secret_key)

        # Set API URL
        api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL

        # Initialize Exchange and Info
        exchange = Exchange(
            wallet,
            api_url,
            account_address=wallet_address
        )
        info = Info(api_url)

        logger.info(f"Initialized exchange connection for {wallet_address}")
        logger.info(f"Connected to {'testnet' if use_testnet else 'mainnet'}")

        return exchange, info

    except Exception as e:
        logger.error(f"Error initializing exchange: {str(e)}")
        raise


def retry_operation(
        operation,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        exception_types: Tuple = (Exception,)
):
    """
    Retry an operation with exponential backoff.

    Args:
        operation: Function to retry
        max_retries: Maximum number of retries
        retry_delay: Initial retry delay in seconds
        backoff_factor: Backoff factor for subsequent retries
        exception_types: Exception types to catch

    Returns:
        Result of the operation
    """
    retries = 0
    delay = retry_delay

    while retries < max_retries:
        try:
            return operation()

        except exception_types as e:
            retries += 1

            if retries >= max_retries:
                logger.error(f"Operation failed after {max_retries} retries: {str(e)}")
                raise

            logger.warning(f"Operation failed, retrying in {delay:.2f}s ({retries}/{max_retries}): {str(e)}")
            time.sleep(delay)
            delay *= backoff_factor


def calculate_vwap(
        df: pd.DataFrame,
        price_col: str = "close",
        volume_col: str = "volume",
        window: Optional[int] = None
) -> pd.Series:
    """
    Calculate Volume Weighted Average Price (VWAP).

    Args:
        df: DataFrame with price and volume data
        price_col: Column name for price
        volume_col: Column name for volume
        window: Rolling window size (or None for whole DataFrame)

    Returns:
        Series with VWAP values
    """
    if df.empty:
        return pd.Series()

    df = df.copy()

    # Calculate typical price
    if "high" in df.columns and "low" in df.columns:
        df["typical_price"] = (df["high"] + df["low"] + df[price_col]) / 3
    else:
        df["typical_price"] = df[price_col]

    # Calculate price * volume
    df["pv"] = df["typical_price"] * df[volume_col]

    if window:
        # Calculate rolling VWAP
        df["cumulative_pv"] = df["pv"].rolling(window=window).sum()
        df["cumulative_volume"] = df[volume_col].rolling(window=window).sum()
    else:
        # Calculate cumulative VWAP
        df["cumulative_pv"] = df["pv"].cumsum()
        df["cumulative_volume"] = df[volume_col].cumsum()

    # Calculate VWAP
    vwap = df["cumulative_pv"] / df["cumulative_volume"]

    return vwap


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).

    Args:
        df: DataFrame with OHLC data
        period: ATR period

    Returns:
        Series with ATR values
    """
    if df.empty or "high" not in df.columns or "low" not in df.columns or "close" not in df.columns:
        return pd.Series()

    # Calculate true range
    df = df.copy()
    df["tr0"] = df["high"] - df["low"]
    df["tr1"] = abs(df["high"] - df["close"].shift())
    df["tr2"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr0", "tr1", "tr2"]].max(axis=1)

    # Calculate ATR
    atr = df["tr"].rolling(window=period).mean()

    return atr


def format_price(price: float, symbol: str, tick_size: Optional[float] = None) -> float:
    """
    Format price according to exchange tick size.

    Args:
        price: Price to format
        symbol: Trading symbol
        tick_size: Tick size (or None to use default)

    Returns:
        Formatted price
    """
    if tick_size is None:
        # Default tick sizes
        if symbol.startswith(("BTC", "ETH")):
            # For major coins, use 1 decimal precision
            tick_size = 0.1
        elif "/" in symbol:
            # For spot markets, use 6 decimal precision
            tick_size = 0.000001
        else:
            # For other perps, use 4 decimal precision
            tick_size = 0.0001

    # Round to nearest tick
    return round(price / tick_size) * tick_size


def format_size(size: float, symbol: str, min_size: Optional[float] = None) -> float:
    """
    Format size according to exchange minimum size.

    Args:
        size: Size to format
        symbol: Trading symbol
        min_size: Minimum size (or None to use default)

    Returns:
        Formatted size
    """
    if min_size is None:
        # Default min sizes
        if symbol.startswith("BTC"):
            min_size = 0.001  # 0.001 BTC
        elif symbol.startswith("ETH"):
            min_size = 0.01  # 0.01 ETH
        elif "/" in symbol:
            # For spot markets
            base_symbol = symbol.split("/")[0]
            if base_symbol in ["BTC"]:
                min_size = 0.001
            elif base_symbol in ["ETH"]:
                min_size = 0.01
            else:
                min_size = 1.0
        else:
            min_size = 0.01  # 0.01 for other perps

    # Round to 8 decimal places
    size = round(size, 8)

    # Ensure minimum size
    return max(size, min_size)


def calculate_position_size(
        account_value: float,
        price: float,
        risk_percentage: float,
        stop_loss_percentage: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        max_position_size: Optional[float] = None
) -> float:
    """
    Calculate position size based on risk parameters.

    Args:
        account_value: Account value
        price: Current price
        risk_percentage: Percentage of account to risk
        stop_loss_percentage: Percentage for stop loss (or None if using stop_loss_price)
        stop_loss_price: Stop loss price (or None if using stop_loss_percentage)
        max_position_size: Maximum position size (or None for no limit)

    Returns:
        Position size
    """
    if account_value <= 0 or price <= 0:
        return 0

    # Calculate risk amount
    risk_amount = account_value * risk_percentage

    # Calculate position size
    if stop_loss_price is not None and stop_loss_price > 0:
        # Use stop loss price
        risk_per_unit = abs(price - stop_loss_price)
        if risk_per_unit <= 0:
            return 0

        position_size = risk_amount / risk_per_unit

    elif stop_loss_percentage is not None and stop_loss_percentage > 0:
        # Use stop loss percentage
        risk_per_unit = price * stop_loss_percentage
        if risk_per_unit <= 0:
            return 0

        position_size = risk_amount / risk_per_unit

    else:
        # Default to fixed percentage
        position_size = (account_value * risk_percentage) / price

    # Apply maximum position size if provided
    if max_position_size is not None:
        position_size = min(position_size, max_position_size)

    return position_size


def get_timestamp_ms() -> int:
    """
    Get current timestamp in milliseconds.

    Returns:
        Current timestamp in milliseconds
    """
    return int(time.time() * 1000)


def datetime_to_timestamp_ms(dt: datetime) -> int:
    """
    Convert datetime to timestamp in milliseconds.

    Args:
        dt: Datetime object

    Returns:
        Timestamp in milliseconds
    """
    return int(dt.timestamp() * 1000)


def timestamp_ms_to_datetime(timestamp_ms: int) -> datetime:
    """
    Convert timestamp in milliseconds to datetime.

    Args:
        timestamp_ms: Timestamp in milliseconds

    Returns:
        Datetime object
    """
    return datetime.fromtimestamp(timestamp_ms / 1000)


def create_data_directory(data_dir: str = "data") -> None:
    """
    Create data directory structure.

    Args:
        data_dir: Base data directory
    """
    dirs = [
        data_dir,
        os.path.join(data_dir, "trades"),
        os.path.join(data_dir, "orderbooks"),
        os.path.join(data_dir, "candles"),
        os.path.join(data_dir, "positions"),
        os.path.join(data_dir, "balances"),
        os.path.join(data_dir, "logs")
    ]

    for directory in dirs:
        os.makedirs(directory, exist_ok=True)

    logger.info(f"Created data directory structure in {data_dir}")