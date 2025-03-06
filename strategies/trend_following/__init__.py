# Initialize the module
"""
Trend Following strategy module for Elysium trading platform.

This module implements trend following strategies for the Elysium platform.
"""

import logging
import pandas as pd
import numpy as np
from abc import abstractmethod
from typing import Dict, Any, Optional, List, Tuple

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from strategies import Strategy

logger = logging.getLogger(__name__)


class TrendFollowingStrategy(Strategy):
    """Base class for trend following strategies."""

    def __init__(
            self,
            name: str,
            exchange: Exchange,
            info: Info,
            symbols: List[str],
            params: Dict[str, Any],
            update_interval: float = 60.0  # Default to checking every minute
    ):
        """
        Initialize trend following strategy.

        Args:
            name: Strategy name
            exchange: Exchange instance
            info: Info instance
            symbols: List of trading symbols
            params: Strategy parameters
            update_interval: Strategy update interval in seconds
        """
        super().__init__(
            name=name,
            exchange=exchange,
            info=info,
            symbols=symbols,
            params=params,
            update_interval=update_interval
        )

        # Trend following specific state
        self.candle_data: Dict[str, pd.DataFrame] = {}
        self.last_signals: Dict[str, Dict[str, Any]] = {}
        self.indicators: Dict[str, Dict[str, Any]] = {}
        self.position_sizes: Dict[str, float] = {}

        # Default parameters
        self.candle_interval = params.get("candle_interval", "1h")
        self.lookback_periods = params.get("lookback_periods", 100)
        self.position_sizing_method = params.get("position_sizing_method", "fixed")
        self.max_position_size = params.get("max_position_size", 1000)
        self.risk_per_trade = params.get("risk_per_trade", 0.01)  # 1% of account equity
        self.stop_loss_pct = params.get("stop_loss_pct", 0.02)  # 2% stop loss
        self.take_profit_pct = params.get("take_profit_pct", 0.06)  # 6% take profit
        self.max_open_positions = params.get("max_open_positions", 5)

    def initialize(self):
        """Initialize strategy-specific state."""
        # Initialize data for each symbol
        logger.info(f"Initializing {self.name} strategy")

        for symbol in self.symbols:
            # Fetch initial candle data
            try:
                self.candle_data[symbol] = self._fetch_candle_data(symbol)

                if self.candle_data[symbol].empty:
                    logger.warning(f"No candle data available for {symbol}, excluding from strategy")
                    continue

                # Initialize indicators
                self.indicators[symbol] = self._calculate_indicators(self.candle_data[symbol])

                # Initialize signal tracking
                self.last_signals[symbol] = {
                    "signal": "neutral",
                    "timestamp": None,
                    "price": None,
                    "stop_loss": None,
                    "take_profit": None,
                    "position_size": 0
                }

                # Get current position
                position = self._get_position_size(symbol)
                self.position_sizes[symbol] = position

                logger.info(
                    f"Initialized {symbol} with {len(self.candle_data[symbol])} candles and position size {position}")

            except Exception as e:
                logger.error(f"Error initializing {symbol}: {str(e)}")

    def update(self):
        """Update strategy state and execute trading logic."""
        try:
            # Update candle data for each symbol
            for symbol in self.symbols:
                if symbol not in self.candle_data:
                    self.candle_data[symbol] = self._fetch_candle_data(symbol)
                else:
                    # Update with new candles
                    updated_candles = self._fetch_candle_data(symbol, limit=10)
                    if not updated_candles.empty:
                        # Merge with existing data
                        combined = pd.concat([self.candle_data[symbol], updated_candles])
                        # Remove duplicates
                        combined = combined.drop_duplicates(subset=["timestamp"]).sort_values(by="timestamp")
                        # Keep only the lookback periods
                        self.candle_data[symbol] = combined.tail(self.lookback_periods)

                if symbol not in self.candle_data or self.candle_data[symbol].empty:
                    logger.warning(f"No candle data available for {symbol}, skipping")
                    continue

                # Update indicators
                self.indicators[symbol] = self._calculate_indicators(self.candle_data[symbol])

                # Update current position
                current_position = self._get_position_size(symbol)
                self.position_sizes[symbol] = current_position

                # Generate trading signals
                signal = self._generate_signal(symbol)

                # Execute trading logic
                if signal:
                    # Only execute if the signal is different from the last one
                    last_signal = self.last_signals[symbol]

                    if signal["signal"] != last_signal["signal"]:
                        logger.info(f"New signal for {symbol}: {signal['signal']} at {signal['price']}")

                        if self._execute_signal(symbol, signal):
                            # Update last signal
                            self.last_signals[symbol] = signal
                            logger.info(f"Executed signal for {symbol}: {signal['signal']}")
                        else:
                            logger.warning(f"Failed to execute signal for {symbol}: {signal['signal']}")

            # Check stop loss and take profit conditions
            self._check_exit_conditions()

            # Update stats
            self._update_strategy_stats()

        except Exception as e:
            logger.error(f"Error in trend following update: {str(e)}")

    def _fetch_candle_data(self, symbol: str, limit: int = None) -> pd.DataFrame:
        """
        Fetch candle data for a symbol.

        Args:
            symbol: Trading symbol
            limit: Maximum number of candles to fetch

        Returns:
            DataFrame with candle data
        """
        try:
            # Use lookback_periods if limit not specified
            limit = limit or self.lookback_periods

            # Get candles from info
            candles = self.info.candles_snapshot(
                symbol,
                self.candle_interval,
                int(pd.Timestamp.now().timestamp() * 1000) - (
                            limit * self._interval_to_milliseconds(self.candle_interval)),
                int(pd.Timestamp.now().timestamp() * 1000)
            )

            if not candles:
                logger.warning(f"No candle data found for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(candles)

            if df.empty:
                return df

            # Rename columns to more friendly names
            df = df.rename(columns={
                "T": "timestamp",
                "t": "timestamp_ms",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
            })

            # Convert numeric columns
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col])

            # Add datetime column
            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')

            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)

            return df

        except Exception as e:
            logger.error(f"Error fetching candle data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def _get_position_size(self, symbol: str) -> float:
        """
        Get current position size for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current position size (positive for long, negative for short, 0 for no position)
        """
        try:
            # For spot trading
            if "/" in symbol:
                base_currency = symbol.split("/")[0]
                spot_state = self.info.spot_user_state(self.exchange.wallet.address)
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == base_currency:
                        return float(balance.get("total", "0"))
            # For tokens with @ notation (e.g., @140 for HWTR/USDC)
            elif symbol.startswith("@"):
                # Map to appropriate token for spot positions
                if symbol == "@140":  # HWTR/USDC
                    spot_state = self.info.spot_user_state(self.exchange.wallet.address)
                    for balance in spot_state.get("balances", []):
                        if balance.get("coin") == "HWTR" or str(balance.get("token")) == "189":
                            return float(balance.get("total", "0"))
            # For perpetual contracts
            else:
                perp_state = self.info.user_state(self.exchange.wallet.address)
                for asset_position in perp_state.get("assetPositions", []):
                    position = asset_position.get("position", {})
                    if position.get("coin") == symbol:
                        return float(position.get("szi", "0"))

            return 0.0
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {str(e)}")
            return 0.0

    def _calculate_position_size(self, symbol: str, signal: Dict[str, Any]) -> float:
        """
        Calculate position size for a trade.

        Args:
            symbol: Trading symbol
            signal: Trading signal

        Returns:
            Position size
        """
        try:
            account_value = 0.0

            # Get account value
            perp_state = self.info.user_state(self.exchange.wallet.address)
            account_value = float(perp_state.get("marginSummary", {}).get("accountValue", "0"))

            if account_value <= 0:
                # Fallback if we can't get account value
                account_value = 10000.0

            # Calculate position size based on method
            if self.position_sizing_method == "fixed":
                return min(self.max_position_size, float(self.params.get("fixed_position_size", 100)))

            elif self.position_sizing_method == "percentage":
                equity_percentage = float(self.params.get("equity_percentage", 0.05))
                position_value = account_value * equity_percentage

                current_price = signal["price"]
                if current_price <= 0:
                    return 0

                # Convert position value to position size
                position_size = position_value / current_price
                return min(self.max_position_size, position_size)

            elif self.position_sizing_method == "risk":
                risk_amount = account_value * self.risk_per_trade

                # Calculate risk per unit
                stop_loss_price = signal["stop_loss"]
                current_price = signal["price"]

                if stop_loss_price <= 0 or current_price <= 0:
                    return 0

                # Risk per unit is the difference between entry and stop loss
                risk_per_unit = abs(current_price - stop_loss_price)
                if risk_per_unit <= 0:
                    return 0

                # Position size = risk amount / risk per unit
                position_size = risk_amount / risk_per_unit
                return min(self.max_position_size, position_size)

            else:
                return min(self.max_position_size, 100)  # Default to fixed size

        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {str(e)}")
            return 0

    def _execute_signal(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """
        Execute a trading signal.

        Args:
            symbol: Trading symbol
            signal: Trading signal

        Returns:
            True if successfully executed, False otherwise
        """
        try:
            signal_type = signal["signal"]
            current_position = self.position_sizes.get(symbol, 0)
            price = signal["price"]
            position_size = signal["position_size"]

            # Check if we already have the desired position
            if signal_type == "long" and current_position > 0:
                logger.info(f"Already have long position for {symbol}, adjusting if needed")
                if abs(current_position - position_size) < 0.1 * position_size:
                    return True  # Position already close enough
                else:
                    # Adjust position size
                    size_delta = position_size - current_position
                    is_buy = size_delta > 0

                    result = self.exchange.market_open(
                        symbol,
                        is_buy,
                        abs(size_delta),
                        price,
                        slippage=0.002
                    )

                    return result["status"] == "ok"

            elif signal_type == "short" and current_position < 0:
                logger.info(f"Already have short position for {symbol}, adjusting if needed")
                if abs(abs(current_position) - position_size) < 0.1 * position_size:
                    return True  # Position already close enough
                else:
                    # Adjust position size
                    size_delta = position_size - abs(current_position)
                    is_buy = size_delta < 0

                    result = self.exchange.market_open(
                        symbol,
                        is_buy,
                        abs(size_delta),
                        price,
                        slippage=0.002
                    )

                    return result["status"] == "ok"

            # Close current position if it's opposite of signal
            if (signal_type == "long" and current_position < 0) or (signal_type == "short" and current_position > 0):
                logger.info(f"Closing opposite position for {symbol}")
                close_result = self.exchange.market_close(symbol)

                if close_result["status"] != "ok":
                    logger.error(f"Failed to close position for {symbol}: {close_result}")
                    return False

            # Exit position if signal is neutral/exit
            if signal_type == "neutral" or signal_type == "exit":
                if current_position != 0:
                    logger.info(f"Exiting position for {symbol}")
                    result = self.exchange.market_close(symbol)
                    return result["status"] == "ok"
                return True  # Already neutral

            # Open new position
            logger.info(f"Opening {signal_type} position for {symbol} with size {position_size}")

            result = self.exchange.market_open(
                symbol,
                signal_type == "long",  # is_buy
                position_size,
                price,
                slippage=0.002
            )

            # Create stop loss and take profit orders if applicable
            if result["status"] == "ok" and signal["stop_loss"] > 0:
                # Market stop loss
                stop_order_type = {
                    "trigger": {
                        "triggerPx": signal["stop_loss"],
                        "isMarket": True,
                        "tpsl": "sl"
                    }
                }

                self.exchange.order(
                    symbol,
                    signal_type != "long",  # opposite side
                    position_size,
                    signal["stop_loss"],
                    stop_order_type,
                    reduce_only=True
                )

                # Take profit if set
                if signal["take_profit"] > 0:
                    tp_order_type = {
                        "trigger": {
                            "triggerPx": signal["take_profit"],
                            "isMarket": True,
                            "tpsl": "tp"
                        }
                    }

                    self.exchange.order(
                        symbol,
                        signal_type != "long",  # opposite side
                        position_size,
                        signal["take_profit"],
                        tp_order_type,
                        reduce_only=True
                    )

            return result["status"] == "ok"

        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {str(e)}")
            return False

    def _check_exit_conditions(self):
        """Check stop loss and take profit conditions for existing positions."""
        try:
            for symbol, signal in self.last_signals.items():
                current_position = self.position_sizes.get(symbol, 0)

                # Skip if no position
                if current_position == 0:
                    continue

                # Get current price
                latest_candle = self.candle_data.get(symbol)
                if latest_candle is None or latest_candle.empty:
                    continue

                current_price = float(latest_candle.iloc[-1]["close"])

                # Check stop loss condition
                if signal["stop_loss"] and (
                        (current_position > 0 and current_price <= signal["stop_loss"]) or
                        (current_position < 0 and current_price >= signal["stop_loss"])
                ):
                    logger.info(f"Stop loss triggered for {symbol} at {current_price}")
                    self.exchange.market_close(symbol)

                    # Update signal to neutral
                    self.last_signals[symbol] = {
                        "signal": "neutral",
                        "timestamp": pd.Timestamp.now(),
                        "price": current_price,
                        "stop_loss": None,
                        "take_profit": None,
                        "position_size": 0
                    }

                    # Update stats
                    self.stats["total_trades"] += 1

                # Check take profit condition
                elif signal["take_profit"] and (
                        (current_position > 0 and current_price >= signal["take_profit"]) or
                        (current_position < 0 and current_price <= signal["take_profit"])
                ):
                    logger.info(f"Take profit triggered for {symbol} at {current_price}")
                    self.exchange.market_close(symbol)

                    # Update signal to neutral
                    self.last_signals[symbol] = {
                        "signal": "neutral",
                        "timestamp": pd.Timestamp.now(),
                        "price": current_price,
                        "stop_loss": None,
                        "take_profit": None,
                        "position_size": 0
                    }

                    # Update stats
                    self.stats["total_trades"] += 1
                    self.stats["profitable_trades"] += 1

        except Exception as e:
            logger.error(f"Error checking exit conditions: {str(e)}")

    def _update_strategy_stats(self):
        """Update strategy performance statistics."""
        try:
            # Update win rate
            if self.stats["total_trades"] > 0:
                self.stats["win_rate"] = (self.stats["profitable_trades"] / self.stats["total_trades"]) * 100

            # Calculate current PnL
            total_pnl = 0.0

            for symbol in self.symbols:
                current_position = self.position_sizes.get(symbol, 0)

                if current_position == 0:
                    continue

                # Get current price
                latest_candle = self.candle_data.get(symbol)
                if latest_candle is None or latest_candle.empty:
                    continue

                current_price = float(latest_candle.iloc[-1]["close"])

                # Get entry price from signal
                entry_price = self.last_signals.get(symbol, {}).get("price", current_price)

                # Calculate PnL
                if current_position > 0:
                    pnl = (current_price - entry_price) * current_position
                else:
                    pnl = (entry_price - current_price) * abs(current_position)

                total_pnl += pnl

            # Update stats
            self.stats["total_profit_loss"] = total_pnl

        except Exception as e:
            logger.error(f"Error updating strategy stats: {str(e)}")

    def _interval_to_milliseconds(self, interval: str) -> int:
        """
        Convert interval string to milliseconds.

        Args:
            interval: Interval string (e.g., "1m", "1h", "1d")

        Returns:
            Interval in milliseconds
        """
        seconds_per_unit = {
            "m": 60,
            "h": 60 * 60,
            "d": 24 * 60 * 60,
            "w": 7 * 24 * 60 * 60,
        }

        try:
            unit = interval[-1]
            value = int(interval[:-1])
            return value * seconds_per_unit[unit] * 1000
        except (ValueError, KeyError):
            return 60 * 60 * 1000  # Default to 1 hour

    @abstractmethod
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate technical indicators for a DataFrame.

        Args:
            df: DataFrame with candle data

        Returns:
            Dictionary of indicator values
        """
        pass

    @abstractmethod
    def _generate_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Signal dictionary or None
        """
        pass