# Market Data module
"""
Market data fetching and processing functionality.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import threading
import pandas as pd

from hyperliquid.info import Info


class MarketData:
    """
    Handles fetching and processing market data from exchanges.
    """

    def __init__(self,
                 info: Info,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize market data handler.

        Args:
            info: Hyperliquid Info client
            logger: Optional logger instance
        """
        self.info = info
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Cache for market data
        self.orderbook_cache: Dict[str, Dict[str, Any]] = {}
        self.mid_price_cache: Dict[str, float] = {}
        self.candle_cache: Dict[str, Dict[str, pd.DataFrame]] = {}

        # Last update timestamps
        self.last_update_time: Dict[str, float] = {}

        # Setup data subscriptions
        self.active_subscriptions: Dict[str, int] = {}

    def subscribe_to_orderbook(self, coin: str, callback=None) -> int:
        """
        Subscribe to order book updates for a coin.

        Args:
            coin: Coin symbol
            callback: Optional callback for updates

        Returns:
            Subscription ID
        """
        try:
            if callback:
                sub_id = self.info.subscribe(
                    {"type": "l2Book", "coin": coin},
                    lambda data: self._handle_orderbook_update(coin, data, callback)
                )
                self.active_subscriptions[f"orderbook_{coin}"] = sub_id
                self.logger.info(f"Subscribed to orderbook for {coin}")
                return sub_id
            else:
                sub_id = self.info.subscribe(
                    {"type": "l2Book", "coin": coin},
                    lambda data: self._update_orderbook_cache(coin, data)
                )
                self.active_subscriptions[f"orderbook_{coin}"] = sub_id
                self.logger.info(f"Subscribed to orderbook for {coin} (cache only)")
                return sub_id
        except Exception as e:
            self.logger.error(f"Error subscribing to orderbook for {coin}: {str(e)}")
            return -1

    def _update_orderbook_cache(self, coin: str, data: Dict[str, Any]):
        """
        Update the orderbook cache with new data.

        Args:
            coin: Coin symbol
            data: Orderbook data
        """
        try:
            if "data" in data:
                self.orderbook_cache[coin] = data["data"]
                self.last_update_time[f"orderbook_{coin}"] = time.time()

                # Update mid price if we have both bids and asks
                if "levels" in data["data"] and len(data["data"]["levels"]) >= 2:
                    bid_levels = data["data"]["levels"][0]
                    ask_levels = data["data"]["levels"][1]

                    if bid_levels and ask_levels:
                        best_bid = float(bid_levels[0]["px"])
                        best_ask = float(ask_levels[0]["px"])
                        self.mid_price_cache[coin] = (best_bid + best_ask) / 2
        except Exception as e:
            self.logger.error(f"Error updating orderbook cache for {coin}: {str(e)}")

    def _handle_orderbook_update(self, coin: str, data: Dict[str, Any], callback):
        """
        Handle orderbook update and invoke callback.

        Args:
            coin: Coin symbol
            data: Orderbook data
            callback: Function to call with processed data
        """
        # First update the cache
        self._update_orderbook_cache(coin, data)

        # Then invoke the callback with the processed data
        try:
            if callback and "data" in data:
                callback(data["data"])
        except Exception as e:
            self.logger.error(f"Error in orderbook callback for {coin}: {str(e)}")

    def get_orderbook(self, coin: str,
                      max_age_seconds: float = 5.0,
                      force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get the latest orderbook for a coin.

        Args:
            coin: Coin symbol
            max_age_seconds: Maximum age of cached data in seconds
            force_refresh: Whether to force a refresh regardless of cache

        Returns:
            Orderbook data
        """
        # Check if we need to refresh
        current_time = time.time()
        cache_key = f"orderbook_{coin}"

        if (force_refresh or
                coin not in self.orderbook_cache or
                cache_key not in self.last_update_time or
                current_time - self.last_update_time.get(cache_key, 0) > max_age_seconds):

            try:
                # Get fresh data
                data = self.info.l2_snapshot(coin)
                self.orderbook_cache[coin] = data
                self.last_update_time[cache_key] = current_time

                # Update mid price
                if "levels" in data and len(data["levels"]) >= 2:
                    bid_levels = data["levels"][0]
                    ask_levels = data["levels"][1]

                    if bid_levels and ask_levels:
                        best_bid = float(bid_levels[0]["px"])
                        best_ask = float(ask_levels[0]["px"])
                        self.mid_price_cache[coin] = (best_bid + best_ask) / 2

            except Exception as e:
                self.logger.error(f"Error fetching orderbook for {coin}: {str(e)}")
                # Return cached data if available, otherwise empty dict
                return self.orderbook_cache.get(coin, {})

        return self.orderbook_cache.get(coin, {})

    def get_best_bid_ask(self, coin: str) -> Tuple[float, float]:
        """
        Get best bid and ask prices for a coin.

        Args:
            coin: Coin symbol

        Returns:
            Tuple of (best_bid, best_ask) prices
        """
        orderbook = self.get_orderbook(coin)

        if "levels" in orderbook and len(orderbook["levels"]) >= 2:
            bid_levels = orderbook["levels"][0]
            ask_levels = orderbook["levels"][1]

            if bid_levels and ask_levels:
                best_bid = float(bid_levels[0]["px"])
                best_ask = float(ask_levels[0]["px"])
                return best_bid, best_ask

        # If we couldn't get the bid/ask from orderbook, try all_mids
        try:
            all_mids = self.info.all_mids()
            if coin in all_mids:
                mid_price = float(all_mids[coin])
                # Approximate bid/ask with a small spread
                return mid_price * 0.9995, mid_price * 1.0005
        except Exception as e:
            self.logger.error(f"Error getting mid price for {coin}: {str(e)}")

        # Return zeros if all methods fail
        return 0.0, 0.0

    def get_mid_price(self, coin: str, force_refresh: bool = False) -> float:
        """
        Get mid price for a coin.

        Args:
            coin: Coin symbol
            force_refresh: Whether to force a refresh

        Returns:
            Mid price
        """
        if force_refresh or coin not in self.mid_price_cache:
            try:
                all_mids = self.info.all_mids()
                if coin in all_mids:
                    self.mid_price_cache[coin] = float(all_mids[coin])
                    self.last_update_time[f"mid_{coin}"] = time.time()
            except Exception as e:
                self.logger.error(f"Error fetching mid price for {coin}: {str(e)}")

                # Try to get from orderbook as fallback
                bid, ask = self.get_best_bid_ask(coin)
                if bid > 0 and ask > 0:
                    self.mid_price_cache[coin] = (bid + ask) / 2

        return self.mid_price_cache.get(coin, 0.0)

    def get_candles(self,
                    coin: str,
                    interval: str = "1m",
                    lookback_periods: int = 100) -> pd.DataFrame:
        """
        Get candlestick data for a symbol.

        Args:
            coin: Coin symbol
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            lookback_periods: Number of periods to look back

        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Calculate time range
            end_time = int(time.time() * 1000)

            # Convert interval to milliseconds
            ms_multiplier = {
                "1m": 60 * 1000,
                "5m": 5 * 60 * 1000,
                "15m": 15 * 60 * 1000,
                "1h": 60 * 60 * 1000,
                "4h": 4 * 60 * 60 * 1000,
                "1d": 24 * 60 * 60 * 1000
            }

            if interval not in ms_multiplier:
                self.logger.error(f"Invalid interval: {interval}")
                return pd.DataFrame()

            interval_ms = ms_multiplier[interval]
            start_time = end_time - (lookback_periods * interval_ms)

            # Fetch candles
            candles = self.info.candles_snapshot(coin, interval, start_time, end_time)

            if not candles:
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(candles)

            # Rename columns to standard OHLCV
            df = df.rename(columns={
                "t": "timestamp",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume"
            })

            # Convert timestamp to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            # Convert numeric columns
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col])

            # Sort by timestamp
            df = df.sort_values("timestamp")

            # Cache the result
            if coin not in self.candle_cache:
                self.candle_cache[coin] = {}
            self.candle_cache[coin][interval] = df

            return df

        except Exception as e:
            self.logger.error(f"Error fetching candles for {coin}: {str(e)}")

            # Return cached data if available
            if coin in self.candle_cache and interval in self.candle_cache[coin]:
                return self.candle_cache[coin][interval]

            return pd.DataFrame()