# User Data module
"""
User account data handling functionality.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd

from hyperliquid.info import Info


class UserData:
    """
    Handles fetching and tracking user account data.
    """

    def __init__(self,
                 info: Info,
                 user_address: str,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize user data handler.

        Args:
            info: Hyperliquid Info client
            user_address: User wallet address
            logger: Optional logger instance
        """
        self.info = info
        self.user_address = user_address
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Cache for user data
        self.user_state_cache = {}
        self.spot_state_cache = {}
        self.open_orders_cache = []
        self.fills_cache = []

        # Last update times
        self.last_update = {}

    def get_perpetual_state(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get user perpetual trading state.

        Args:
            force_refresh: Whether to force a refresh

        Returns:
            User perpetual state data
        """
        current_time = time.time()
        cache_key = "user_state"

        # Check if we need to refresh
        if (force_refresh or
                cache_key not in self.user_state_cache or
                cache_key not in self.last_update or
                current_time - self.last_update.get(cache_key, 0) > 5.0):  # Refresh every 5 seconds

            try:
                self.user_state_cache = self.info.user_state(self.user_address)
                self.last_update[cache_key] = current_time
                self.logger.debug(f"Refreshed user perpetual state for {self.user_address}")
            except Exception as e:
                self.logger.error(f"Error fetching user state: {str(e)}")

        return self.user_state_cache

    def get_spot_state(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get user spot trading state.

        Args:
            force_refresh: Whether to force a refresh

        Returns:
            User spot state data
        """
        current_time = time.time()
        cache_key = "spot_state"

        # Check if we need to refresh
        if (force_refresh or
                cache_key not in self.spot_state_cache or
                cache_key not in self.last_update or
                current_time - self.last_update.get(cache_key, 0) > 5.0):  # Refresh every 5 seconds

            try:
                self.spot_state_cache = self.info.spot_user_state(self.user_address)
                self.last_update[cache_key] = current_time
                self.logger.debug(f"Refreshed user spot state for {self.user_address}")
            except Exception as e:
                self.logger.error(f"Error fetching spot state: {str(e)}")

        return self.spot_state_cache

    def get_perpetual_positions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get current perpetual positions.

        Args:
            force_refresh: Whether to force a refresh

        Returns:
            List of position data
        """
        user_state = self.get_perpetual_state(force_refresh)
        positions = []

        try:
            for asset_position in user_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                if float(position.get("szi", 0)) != 0:
                    positions.append({
                        "symbol": position.get("coin", ""),
                        "size": float(position.get("szi", 0)),
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0)),
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0)),
                    })
        except Exception as e:
            self.logger.error(f"Error processing positions: {str(e)}")

        return positions

    def get_spot_balances(self, min_value: float = 0.0, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get spot balances.

        Args:
            min_value: Minimum balance value to include
            force_refresh: Whether to force a refresh

        Returns:
            List of balance data
        """
        spot_state = self.get_spot_state(force_refresh)
        balances = []

        try:
            for balance in spot_state.get("balances", []):
                if float(balance.get("total", 0)) > min_value:
                    balances.append({
                        "asset": balance.get("coin", ""),
                        "available": float(balance.get("available", 0)),
                        "total": float(balance.get("total", 0)),
                        "in_orders": float(balance.get("total", 0)) - float(balance.get("available", 0))
                    })
        except Exception as e:
            self.logger.error(f"Error processing balances: {str(e)}")

        return balances

    def get_open_orders(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get open orders.

        Args:
            force_refresh: Whether to force a refresh

        Returns:
            List of open orders
        """
        current_time = time.time()
        cache_key = "open_orders"

        # Check if we need to refresh
        if (force_refresh or
                cache_key not in self.last_update or
                current_time - self.last_update.get(cache_key, 0) > 5.0):  # Refresh every 5 seconds

            try:
                raw_orders = self.info.open_orders(self.user_address)
                self.open_orders_cache = []

                for order in raw_orders:
                    self.open_orders_cache.append({
                        "symbol": order.get("coin", ""),
                        "side": "Buy" if order.get("side", "") == "B" else "Sell",
                        "size": float(order.get("sz", 0)),
                        "price": float(order.get("limitPx", 0)),
                        "order_id": order.get("oid", 0),
                        "timestamp": datetime.fromtimestamp(order.get("timestamp", 0) / 1000)
                    })

                self.last_update[cache_key] = current_time
                self.logger.debug(f"Refreshed open orders for {self.user_address}")
            except Exception as e:
                self.logger.error(f"Error fetching open orders: {str(e)}")

        return self.open_orders_cache

    def get_fills_history(self,
                          limit: int = 100,
                          start_time: Optional[int] = None,
                          end_time: Optional[int] = None,
                          force_refresh: bool = False) -> pd.DataFrame:
        """
        Get filled orders history.

        Args:
            limit: Maximum number of fills to return
            start_time: Optional start time in milliseconds
            end_time: Optional end time in milliseconds
            force_refresh: Whether to force a refresh

        Returns:
            DataFrame of fill history
        """
        current_time = time.time()
        cache_key = "fills"

        # Check if we need to refresh
        if (force_refresh or
                cache_key not in self.last_update or
                current_time - self.last_update.get(cache_key, 0) > 30.0):  # Refresh every 30 seconds

            try:
                # Set default time range if not provided
                if start_time is None:
                    # Default to last 7 days
                    start_time = int((current_time - (7 * 24 * 3600)) * 1000)

                if end_time is None:
                    end_time = int(current_time * 1000)

                # Fetch fills
                fills = self.info.user_fills_by_time(
                    self.user_address,
                    start_time=start_time,
                    end_time=end_time
                )

                # Convert to DataFrame
                if fills:
                    df = pd.DataFrame(fills)

                    # Process data
                    if not df.empty:
                        # Convert timestamp
                        df['time'] = pd.to_datetime(df['time'], unit='ms')

                        # Convert numeric columns
                        numeric_cols = ['sz', 'px', 'closedPnl']
                        for col in numeric_cols:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col])

                        # Rename columns for clarity
                        df = df.rename(columns={
                            'time': 'timestamp',
                            'coin': 'symbol',
                            'sz': 'size',
                            'px': 'price',
                            'closedPnl': 'pnl'
                        })

                        # Add side in readable format
                        if 'side' in df.columns:
                            df['side'] = df['side'].apply(lambda x: 'Buy' if x == 'B' else 'Sell')

                        # Calculate total value
                        if 'size' in df.columns and 'price' in df.columns:
                            df['total_value'] = df['size'] * df['price']

                        # Sort by timestamp (newest first)
                        df = df.sort_values('timestamp', ascending=False)

                        # Limit number of rows
                        df = df.head(limit)

                        self.fills_cache = df
                    else:
                        self.fills_cache = pd.DataFrame()
                else:
                    self.fills_cache = pd.DataFrame()

                self.last_update[cache_key] = current_time
                self.logger.debug(f"Refreshed fill history for {self.user_address}")

            except Exception as e:
                self.logger.error(f"Error fetching fills history: {str(e)}")

                # Return existing cache if available
                if isinstance(self.fills_cache, pd.DataFrame) and not self.fills_cache.empty:
                    return self.fills_cache

                return pd.DataFrame()

        return self.fills_cache

    def get_account_value(self) -> float:
        """
        Get total account value.

        Returns:
            Account value in USD
        """
        user_state = self.get_perpetual_state()

        try:
            margin_summary = user_state.get("marginSummary", {})
            return float(margin_summary.get("accountValue", 0))
        except Exception as e:
            self.logger.error(f"Error getting account value: {str(e)}")
            return 0.0

    def get_balance_for_coin(self, coin: str) -> float:
        """
        Get balance for a specific coin.

        Args:
            coin: Coin symbol

        Returns:
            Available balance
        """
        balances = self.get_spot_balances()

        for balance in balances:
            if balance["asset"].lower() == coin.lower():
                return balance["available"]

        return 0.0