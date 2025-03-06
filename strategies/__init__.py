"""
Strategies module for Elysium trading platform.

This module defines the base strategy class and common functionality
for all trading strategies in the Elysium platform.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Callable

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils.signing import get_timestamp_ms

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """Base class for all Elysium trading strategies."""

    def __init__(
            self,
            name: str,
            exchange: Exchange,
            info: Info,
            symbols: List[str],
            params: Dict[str, Any],
            update_interval: float = 1.0
    ):
        """
        Initialize strategy.

        Args:
            name: Strategy name
            exchange: Exchange instance
            info: Info instance
            symbols: List of trading symbols
            params: Strategy parameters
            update_interval: Strategy update interval in seconds
        """
        self.name = name
        self.exchange = exchange
        self.info = info
        self.symbols = symbols
        self.params = params
        self.update_interval = update_interval

        self.running = False
        self.thread = None
        self.start_time = None
        self.last_update_time = None
        self.status = "initialized"
        self.active_orders: Dict[int, Dict[str, Any]] = {}
        self.stats = {
            "total_trades": 0,
            "profitable_trades": 0,
            "total_profit_loss": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0
        }

        logger.info(f"Initialized strategy: {self.name}")
        logger.info(f"Trading symbols: {', '.join(self.symbols)}")
        logger.info(f"Parameters: {self.params}")

    def start(self) -> bool:
        """
        Start the strategy.

        Returns:
            True if successfully started, False otherwise
        """
        if self.running:
            logger.warning(f"Strategy {self.name} is already running")
            return False

        logger.info(f"Starting strategy: {self.name}")

        try:
            self.running = True
            self.start_time = datetime.now()
            self.status = "running"

            # Initialize strategy-specific state
            self.initialize()

            # Start strategy thread
            self.thread = threading.Thread(target=self._run_loop)
            self.thread.daemon = True
            self.thread.start()

            logger.info(f"Strategy {self.name} started successfully")
            return True

        except Exception as e:
            self.running = False
            self.status = f"start_failed: {str(e)}"
            logger.error(f"Failed to start strategy {self.name}: {str(e)}")
            return False

    def stop(self) -> bool:
        """
        Stop the strategy.

        Returns:
            True if successfully stopped, False otherwise
        """
        if not self.running:
            logger.warning(f"Strategy {self.name} is not running")
            return False

        logger.info(f"Stopping strategy: {self.name}")

        try:
            self.running = False
            self.status = "stopping"

            # Cancel all active orders
            self.cancel_all_orders()

            # Wait for thread to complete
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5.0)

            self.status = "stopped"
            logger.info(f"Strategy {self.name} stopped successfully")
            return True

        except Exception as e:
            self.status = f"stop_failed: {str(e)}"
            logger.error(f"Failed to stop strategy {self.name}: {str(e)}")
            return False

    def _run_loop(self):
        """Main strategy loop."""
        while self.running:
            try:
                start_time = time.time()

                # Update strategy state
                self.update()
                self.last_update_time = datetime.now()

                # Calculate sleep time to maintain update interval
                elapsed = time.time() - start_time
                sleep_time = max(0.1, self.update_interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in strategy {self.name} loop: {str(e)}")
                time.sleep(1.0)  # Sleep longer on error

    @abstractmethod
    def initialize(self):
        """Initialize strategy-specific state."""
        pass

    @abstractmethod
    def update(self):
        """Update strategy state and execute trading logic."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """
        Get strategy status.

        Returns:
            Dictionary with strategy status information
        """
        runtime = None
        if self.start_time:
            runtime = (datetime.now() - self.start_time).total_seconds()

        return {
            "name": self.name,
            "status": self.status,
            "running": self.running,
            "start_time": self.start_time,
            "last_update_time": self.last_update_time,
            "runtime_seconds": runtime,
            "symbols": self.symbols,
            "active_orders_count": len(self.active_orders),
            "stats": self.stats
        }

    def cancel_all_orders(self):
        """Cancel all active orders for the strategy."""
        logger.info(f"Cancelling all orders for strategy {self.name}")

        for symbol in self.symbols:
            try:
                orders = self.info.open_orders(self.exchange.wallet.address)
                for order in orders:
                    if order["coin"] in self.symbols:
                        self.exchange.cancel(order["coin"], order["oid"])
                        logger.info(f"Cancelled order {order['oid']} for {order['coin']}")
                self.active_orders.clear()
            except Exception as e:
                logger.error(f"Error cancelling orders for {symbol}: {str(e)}")

    def place_limit_order(
            self,
            symbol: str,
            is_buy: bool,
            size: float,
            price: float,
            order_id_tag: Optional[str] = None
    ) -> Optional[int]:
        """
        Place a limit order and track it in active orders.

        Args:
            symbol: Trading symbol
            is_buy: True for buy, False for sell
            size: Order size
            price: Order price
            order_id_tag: Optional tag for tracking order

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            order_result = self.exchange.order(
                symbol,
                is_buy,
                size,
                price,
                {"limit": {"tif": "Gtc"}}
            )

            if order_result["status"] == "ok":
                status = order_result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.active_orders[oid] = {
                        "symbol": symbol,
                        "side": "buy" if is_buy else "sell",
                        "size": size,
                        "price": price,
                        "time": get_timestamp_ms(),
                        "tag": order_id_tag
                    }
                    logger.info(f"Placed {'buy' if is_buy else 'sell'} order: {size} {symbol} @ {price}")
                    return oid
                else:
                    logger.warning(f"Order not resting: {status}")
            else:
                logger.error(f"Order placement failed: {order_result}")

            return None

        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return None

    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            cancel_result = self.exchange.cancel(symbol, order_id)

            if cancel_result["status"] == "ok":
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                logger.info(f"Cancelled order {order_id} for {symbol}")
                return True
            else:
                logger.error(f"Order cancellation failed: {cancel_result}")
                return False

        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return False

    def update_order(
            self,
            symbol: str,
            order_id: int,
            new_size: Optional[float] = None,
            new_price: Optional[float] = None
    ) -> Optional[int]:
        """
        Update an existing order with new size and/or price.

        Args:
            symbol: Trading symbol
            order_id: Order ID to update
            new_size: New order size (or None to keep current)
            new_price: New order price (or None to keep current)

        Returns:
            New order ID if successful, None otherwise
        """
        # First get the current order details
        if order_id not in self.active_orders:
            logger.warning(f"Order {order_id} not found in active orders")
            return None

        order = self.active_orders[order_id]

        # Use current values if not specified
        size = new_size if new_size is not None else order["size"]
        price = new_price if new_price is not None else order["price"]
        is_buy = order["side"] == "buy"

        # Cancel the existing order
        if not self.cancel_order(symbol, order_id):
            logger.warning(f"Failed to cancel order {order_id} for update")
            return None

        # Place a new order
        return self.place_limit_order(symbol, is_buy, size, price, order.get("tag"))

    def update_params(self, new_params: Dict[str, Any]) -> bool:
        """
        Update strategy parameters.

        Args:
            new_params: New parameter values

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update params
            self.params.update(new_params)
            logger.info(f"Updated parameters for strategy {self.name}: {new_params}")
            return True

        except Exception as e:
            logger.error(f"Error updating parameters: {str(e)}")
            return False

    def update_stats(self, new_stats: Dict[str, Any]):
        """
        Update strategy statistics.

        Args:
            new_stats: New statistics values
        """
        self.stats.update(new_stats)