# Initialize the module
"""
Market Making strategy module for Elysium trading platform.

This module implements market making strategies for the Elysium platform.
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils.signing import get_timestamp_ms

from strategies import Strategy

logger = logging.getLogger(__name__)


class BasicMarketMaker(Strategy):
    """Basic market making strategy."""

    def __init__(
            self,
            exchange: Exchange,
            info: Info,
            symbols: List[str],
            params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize basic market making strategy.

        Args:
            exchange: Exchange instance
            info: Info instance
            symbols: List of trading symbols
            params: Strategy parameters
        """
        # Default parameters
        default_params = {
            "max_order_size": 6000,
            "min_order_size": 1000,
            "position_use_pct": 0.90,
            "tick_size": 0.0001,
            "initial_offset": 0.0001,  # 0.01%
            "min_offset": 0.00009,  # 0.009%
            "offset_reduction": 0.00001,
            "order_refresh_time": 10,  # seconds
            "max_position": 20000,  # Maximum position size
            "min_spread": 0.0001,  # Minimum spread to maintain
        }

        # Override defaults with provided params
        if params:
            default_params.update(params)

        super().__init__(
            name="Basic Market Maker",
            exchange=exchange,
            info=info,
            symbols=symbols,
            params=default_params,
            update_interval=1.0  # Check every second, but only refresh orders based on order_refresh_time
        )

        # Strategy-specific state
        self.current_buy_offset: Dict[str, float] = {}
        self.current_sell_offset: Dict[str, float] = {}
        self.last_order_time: Dict[str, int] = {}
        self.book_subscriptions: List[int] = []

    def initialize(self):
        """Initialize strategy-specific state."""
        # Initialize offset for each symbol
        for symbol in self.symbols:
            self.current_buy_offset[symbol] = self.params["initial_offset"]
            self.current_sell_offset[symbol] = self.params["initial_offset"]
            self.last_order_time[symbol] = 0

        # Subscribe to order book updates
        for symbol in self.symbols:
            sub_id = self.info.subscribe(
                {"type": "l2Book", "coin": symbol},
                self.on_orderbook_update
            )
            self.book_subscriptions.append(sub_id)

        logger.info(f"Initialized {self.name} strategy for {len(self.symbols)} symbols")

    def on_orderbook_update(self, msg):
        """
        Handle order book updates.

        Args:
            msg: Order book update message
        """
        if not self.running:
            return

        try:
            if "data" in msg and "coin" in msg["data"]:
                symbol = msg["data"]["coin"]

                # Process only if it's one of our target symbols
                if symbol in self.symbols:
                    if "levels" in msg["data"] and len(msg["data"]["levels"]) >= 2:
                        levels = msg["data"]["levels"]
                        if len(levels[0]) > 0 and len(levels[1]) > 0:
                            best_bid = float(levels[0][0]["px"])
                            best_ask = float(levels[1][0]["px"])

                            current_time = get_timestamp_ms()

                            # Only refresh orders if enough time has passed since last update
                            if (current_time - self.last_order_time.get(symbol, 0)) >= (
                                    self.params["order_refresh_time"] * 1000):
                                self.place_orders(symbol, best_bid, best_ask)
                                self.last_order_time[symbol] = current_time

        except Exception as e:
            logger.error(f"Error in orderbook update: {str(e)}")

    def update(self):
        """Update strategy state and execute trading logic."""
        # Most logic happens in on_orderbook_update
        # This method is for periodic checks and cleanup

        try:
            # Check active orders and remove any that have been filled or cancelled
            oids_to_remove = []

            for oid, order in self.active_orders.items():
                symbol = order["symbol"]
                try:
                    order_status = self.info.query_order_by_oid(self.exchange.wallet.address, oid)
                    if not order_status or "error" in order_status:
                        oids_to_remove.append(oid)
                except Exception:
                    oids_to_remove.append(oid)

            for oid in oids_to_remove:
                if oid in self.active_orders:
                    del self.active_orders[oid]

            # Periodically refresh orderbooks for symbols that haven't received updates
            current_time = get_timestamp_ms()
            for symbol in self.symbols:
                if (current_time - self.last_order_time.get(symbol, 0)) >= (
                        self.params["order_refresh_time"] * 2 * 1000):
                    try:
                        book_data = self.info.l2_snapshot(symbol)
                        if book_data and "levels" in book_data and len(book_data["levels"]) >= 2:
                            if len(book_data["levels"][0]) > 0 and len(book_data["levels"][1]) > 0:
                                best_bid = float(book_data["levels"][0][0]["px"])
                                best_ask = float(book_data["levels"][1][0]["px"])
                                self.place_orders(symbol, best_bid, best_ask)
                                self.last_order_time[symbol] = current_time
                    except Exception as e:
                        logger.error(f"Error fetching orderbook for {symbol}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in update: {str(e)}")

    def adjust_offset(self, current_offset: float) -> float:
        """
        Reduce offset while respecting minimum.

        Args:
            current_offset: Current offset value

        Returns:
            Adjusted offset value
        """
        new_offset = current_offset - self.params["offset_reduction"]
        return max(new_offset, self.params["min_offset"])

    def get_position(self, symbol: str) -> float:
        """
        Get current position for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current position size
        """
        try:
            spot_state = self.info.spot_user_state(self.exchange.wallet.address)

            # For spot trading
            if "/" in symbol:
                base_currency = symbol.split("/")[0]
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == base_currency:
                        return float(balance.get("total", "0"))
            # For tokens with @ notation (e.g., @140 for HWTR/USDC)
            elif symbol.startswith("@"):
                # Map to appropriate token for spot positions
                if symbol == "@140":  # HWTR/USDC
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

    def get_quote_currency_balance(self, symbol: str) -> float:
        """
        Get quote currency balance for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Quote currency balance
        """
        try:
            # For spot trading
            if "/" in symbol:
                quote_currency = symbol.split("/")[1]
                spot_state = self.info.spot_user_state(self.exchange.wallet.address)
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == quote_currency:
                        return float(balance.get("total", "0"))
            # For special symbols like @140 (HWTR/USDC)
            elif symbol.startswith("@"):
                spot_state = self.info.spot_user_state(self.exchange.wallet.address)
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == "USDC":  # Assuming USDC is the quote currency
                        return float(balance.get("total", "0"))
            # For perpetual contracts
            else:
                perp_state = self.info.user_state(self.exchange.wallet.address)
                return float(perp_state.get("marginSummary", {}).get("withdrawable", "0"))

            return 0.0
        except Exception as e:
            logger.error(f"Error getting quote currency balance for {symbol}: {str(e)}")
            return 0.0

    def place_orders(self, symbol: str, best_bid: float, best_ask: float):
        """
        Place market making orders for a symbol.

        Args:
            symbol: Trading symbol
            best_bid: Best bid price
            best_ask: Best ask price
        """
        try:
            # Cancel existing orders for this symbol
            self.cancel_symbol_orders(symbol)

            # Adjust offsets
            self.current_buy_offset[symbol] = self.adjust_offset(self.current_buy_offset[symbol])
            self.current_sell_offset[symbol] = self.adjust_offset(self.current_sell_offset[symbol])

            # Calculate prices with dynamic offsets
            buy_price = round(best_ask * (1 - self.current_buy_offset[symbol]), 6)
            sell_price = round(best_bid * (1 + self.current_sell_offset[symbol]), 6)

            # Check if spread is at least minimum spread
            min_spread = self.params["min_spread"]
            actual_spread = sell_price - buy_price
            if actual_spread < min_spread:
                # Adjust prices to maintain minimum spread
                mid_price = (buy_price + sell_price) / 2
                buy_price = mid_price - (min_spread / 2)
                sell_price = mid_price + (min_spread / 2)

            position = self.get_position(symbol)
            quote_balance = self.get_quote_currency_balance(symbol)

            logger.info(f"Refreshing orders for {symbol} - Position: {position}, Quote balance: {quote_balance}")
            logger.info(
                f"Current offsets - Buy: {self.current_buy_offset[symbol]:.6f}, Sell: {self.current_sell_offset[symbol]:.6f}")
            logger.info(
                f"Market - Bid: {best_bid:.6f}, Ask: {best_ask:.6f}, Our prices - Buy: {buy_price:.6f}, Sell: {sell_price:.6f}")

            # Calculate buy size based on quote currency balance
            max_possible_buy = min(self.params["max_order_size"],
                                   (quote_balance / buy_price) * 0.95)  # Use 95% of balance
            buy_size = max(min(max_possible_buy, self.params["max_order_size"]), self.params["min_order_size"])
            buy_size = float(f"{buy_size:.2f}")  # Round to 2 decimal places

            # Calculate sell size based on available position
            max_sell_size = min(position * self.params["position_use_pct"], self.params["max_position"])
            sell_size = max(min(max_sell_size, self.params["max_order_size"]), self.params["min_order_size"])
            sell_size = float(f"{sell_size:.2f}")  # Round to 2 decimal places

            # Place buy order if size is sufficient
            if buy_size >= self.params["min_order_size"]:
                self.place_limit_order(symbol, True, buy_size, buy_price, f"mm_buy_{symbol}")

            # Place sell order if size is sufficient
            if sell_size >= self.params["min_order_size"]:
                self.place_limit_order(symbol, False, sell_size, sell_price, f"mm_sell_{symbol}")

        except Exception as e:
            logger.error(f"Error placing orders for {symbol}: {str(e)}")

    def cancel_symbol_orders(self, symbol: str):
        """
        Cancel all active orders for a specific symbol.

        Args:
            symbol: Trading symbol
        """
        try:
            # First identify orders to cancel
            oids_to_cancel = []
            for oid, order in self.active_orders.items():
                if order["symbol"] == symbol:
                    oids_to_cancel.append((oid, symbol))

            # Cancel identified orders
            for oid, sym in oids_to_cancel:
                self.cancel_order(sym, oid)

        except Exception as e:
            logger.error(f"Error cancelling orders for {symbol}: {str(e)}")

    def stop(self) -> bool:
        """
        Stop the strategy.

        Returns:
            True if successfully stopped, False otherwise
        """
        # Unsubscribe from order book updates
        for sub_id in self.book_subscriptions:
            for symbol in self.symbols:
                try:
                    self.info.unsubscribe({"type": "l2Book", "coin": symbol}, sub_id)
                except Exception:
                    pass

        self.book_subscriptions = []

        # Call parent stop method
        return super().stop()