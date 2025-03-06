# Initialize the module
"""
Data module for Elysium trading platform.

This module handles market data fetching, processing, storage,
and analysis for the Elysium trading platform.
"""

import json
import logging
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union

from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.utils.types import L2BookData

logger = logging.getLogger(__name__)


class MarketData:
    """Market data handler for Elysium."""

    def __init__(self, info: Info, data_dir: str = "data"):
        """
        Initialize market data handler.

        Args:
            info: Hyperliquid Info instance
            data_dir: Directory to store market data
        """
        self.info = info
        self.data_dir = data_dir
        self.book_cache: Dict[str, L2BookData] = {}
        self.midprice_cache: Dict[str, float] = {}
        self.last_update_time: Dict[str, int] = {}

        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, "trades"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "orderbooks"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "candles"), exist_ok=True)

        logger.info(f"Initialized market data handler with data directory: {data_dir}")

    def get_all_mids(self) -> Dict[str, float]:
        """
        Get midprices for all available markets.

        Returns:
            Dictionary of symbol to midprice mappings
        """
        try:
            all_mids = self.info.all_mids()
            # Convert string prices to float
            return {k: float(v) for k, v in all_mids.items()}
        except Exception as e:
            logger.error(f"Error fetching all mids: {str(e)}")
            return {}

    def get_orderbook(self, symbol: str, depth: int = 10, force_update: bool = False) -> Optional[L2BookData]:
        """
        Get orderbook for a specific symbol.

        Args:
            symbol: Trading symbol
            depth: Number of levels to return
            force_update: Force refresh from API instead of using cache

        Returns:
            L2BookData containing the orderbook
        """
        current_time = int(datetime.now().timestamp() * 1000)

        # Return cached data if it's less than 1 second old and force_update is False
        if (
                symbol in self.book_cache and
                symbol in self.last_update_time and
                current_time - self.last_update_time[symbol] < 1000 and
                not force_update
        ):
            return self.book_cache[symbol]

        try:
            book_data = self.info.l2_snapshot(symbol)
            if book_data:
                # Limit depth
                if "levels" in book_data and len(book_data["levels"]) >= 2:
                    bid_levels = book_data["levels"][0][:depth]
                    ask_levels = book_data["levels"][1][:depth]
                    book_data["levels"] = (bid_levels, ask_levels)

                # Update cache
                self.book_cache[symbol] = book_data
                self.last_update_time[symbol] = current_time

                # Also update midprice cache
                if len(book_data["levels"]) >= 2 and len(book_data["levels"][0]) > 0 and len(
                        book_data["levels"][1]) > 0:
                    best_bid = float(book_data["levels"][0][0]["px"])
                    best_ask = float(book_data["levels"][1][0]["px"])
                    self.midprice_cache[symbol] = (best_bid + best_ask) / 2

                return book_data
            return None
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {str(e)}")
            return None

    def get_best_bid_ask(self, symbol: str) -> Tuple[float, float]:
        """
        Get best bid and ask prices for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (best_bid, best_ask)
        """
        book_data = self.get_orderbook(symbol)
        if book_data and "levels" in book_data and len(book_data["levels"]) >= 2:
            if len(book_data["levels"][0]) > 0 and len(book_data["levels"][1]) > 0:
                best_bid = float(book_data["levels"][0][0]["px"])
                best_ask = float(book_data["levels"][1][0]["px"])
                return best_bid, best_ask

        # If we couldn't get from orderbook, try all_mids
        all_mids = self.get_all_mids()
        if symbol in all_mids:
            mid = all_mids[symbol]
            # Approximate bid/ask with a 0.1% spread
            return mid * 0.999, mid * 1.001

        logger.warning(f"Could not determine bid/ask for {symbol}")
        return 0.0, 0.0

    def get_candles(
            self,
            symbol: str,
            interval: str = "1h",
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
            limit: int = 100
    ) -> pd.DataFrame:
        """
        Get candlestick data for a symbol.

        Args:
            symbol: Trading symbol
            interval: Candle interval (e.g., "1m", "5m", "1h", "1d")
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            limit: Maximum number of candles to return

        Returns:
            DataFrame with candle data
        """
        if end_time is None:
            end_time = int(datetime.now().timestamp() * 1000)

        if start_time is None:
            # Default to looking back based on interval and limit
            if interval == "1m":
                start_time = end_time - (limit * 60 * 1000)
            elif interval == "5m":
                start_time = end_time - (limit * 5 * 60 * 1000)
            elif interval == "15m":
                start_time = end_time - (limit * 15 * 60 * 1000)
            elif interval == "1h":
                start_time = end_time - (limit * 60 * 60 * 1000)
            elif interval == "4h":
                start_time = end_time - (limit * 4 * 60 * 60 * 1000)
            elif interval == "1d":
                start_time = end_time - (limit * 24 * 60 * 60 * 1000)
            else:
                start_time = end_time - (limit * 60 * 60 * 1000)  # Default to 1h

        try:
            candles = self.info.candles_snapshot(symbol, interval, start_time, end_time)

            if not candles:
                logger.warning(f"No candle data found for {symbol} ({interval})")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(candles)

            if not df.empty:
                # Rename columns to more friendly names
                df = df.rename(columns={
                    "T": "timestamp",
                    "t": "timestamp_ms",
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                    "n": "trades_count",
                    "i": "interval",
                    "s": "symbol"
                })

                # Convert timestamp to datetime
                df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')

                # Convert string values to numeric
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col])

                # Sort by timestamp
                df = df.sort_values('timestamp').reset_index(drop=True)

                # Limit to requested number of candles
                if len(df) > limit:
                    df = df.tail(limit)

            return df

        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {str(e)}")
            return pd.DataFrame()

    def get_trades_history(self, address: str, limit: int = 50) -> pd.DataFrame:
        """
        Get trade history for an address.

        Args:
            address: Wallet address
            limit: Maximum number of trades to return

        Returns:
            DataFrame with trade history
        """
        try:
            # First try to read from fills file
            fills = []
            try:
                with open("fills", "r") as f:
                    for line in f:
                        fills.extend(json.loads(line.strip()))
            except FileNotFoundError:
                logger.warning("No local fills file found")
                # Try to get from API
                fills = self.info.user_fills(address)

            if not fills:
                logger.warning(f"No trade history found for {address}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(fills)

            if not df.empty:
                # Convert timestamp to datetime
                df['datetime'] = pd.to_datetime(df['time'], unit='ms')

                # Add additional columns
                df['size'] = df['sz'].astype(float)
                df['price'] = df['px'].astype(float)
                df['side'] = df['side'].apply(lambda x: "Buy" if x == "B" else "Sell")
                df['total_value'] = df['size'] * df['price']

                if 'closedPnl' in df.columns:
                    df['pnl'] = df['closedPnl'].astype(float)

                # Sort by timestamp and limit
                df = df.sort_values('time', ascending=False).reset_index(drop=True)
                if len(df) > limit:
                    df = df.head(limit)

            return df

        except Exception as e:
            logger.error(f"Error fetching trade history: {str(e)}")
            return pd.DataFrame()

    def save_trades_to_file(self, df: pd.DataFrame, symbol: Optional[str] = None) -> bool:
        """
        Save trades to CSV file.

        Args:
            df: DataFrame with trades
            symbol: Optional symbol to filter and name the file

        Returns:
            True if successful, False otherwise
        """
        try:
            if df.empty:
                logger.warning("No trades to save")
                return False

            # Filter by symbol if provided
            if symbol:
                df = df[df['coin'] == symbol]
                if df.empty:
                    logger.warning(f"No trades for {symbol}")
                    return False

            # Create filename with date
            date_str = datetime.now().strftime("%Y%m%d")
            symbol_str = f"_{symbol}" if symbol else ""
            filename = os.path.join(self.data_dir, "trades", f"trades{symbol_str}_{date_str}.csv")

            # Save to CSV
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(df)} trades to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving trades: {str(e)}")
            return False

    def calculate_vwap(self, symbol: str, lookback_hours: int = 24) -> float:
        """
        Calculate Volume Weighted Average Price for a symbol.

        Args:
            symbol: Trading symbol
            lookback_hours: Hours to look back for VWAP calculation

        Returns:
            VWAP price
        """
        try:
            # Get candle data
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (lookback_hours * 60 * 60 * 1000)
            df = self.get_candles(symbol, interval="1h", start_time=start_time, end_time=end_time)

            if df.empty:
                logger.warning(f"No data available for VWAP calculation for {symbol}")
                return 0.0

            # Calculate VWAP
            df['volume_x_price'] = df['volume'] * ((df['high'] + df['low'] + df['close']) / 3)
            vwap = df['volume_x_price'].sum() / df['volume'].sum() if df['volume'].sum() > 0 else 0

            return vwap

        except Exception as e:
            logger.error(f"Error calculating VWAP for {symbol}: {str(e)}")
            return 0.0