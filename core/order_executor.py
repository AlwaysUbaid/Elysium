# Order Executor module
"""
Order executor for placing and tracking orders.
Provides high-level order operations and tracking.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import threading
import queue

from elysium.core.exchange import ExchangeManager


class OrderExecutor:
    """
    Executes and tracks orders on the exchange.
    """

    def __init__(self,
                 exchange_manager: ExchangeManager,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the order executor.

        Args:
            exchange_manager: ExchangeManager instance
            logger: Optional logger instance
        """
        self.exchange = exchange_manager
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Track active orders
        self.active_orders: Dict[int, Dict[str, Any]] = {}
        self.order_updates_queue = queue.Queue()

        # Setup callbacks
        self._setup_order_callbacks()

    def _setup_order_callbacks(self):
        """Set up callbacks for order updates and fills."""
        try:
            # Subscribe to user events (fills, etc.)
            self.exchange.info.subscribe(
                {"type": "userEvents", "user": self.exchange.account_address},
                self._on_user_events
            )

            # Subscribe to order updates
            self.exchange.info.subscribe(
                {"type": "orderUpdates", "user": self.exchange.account_address},
                self._on_order_updates
            )

        except Exception as e:
            self.logger.error(f"Error setting up order callbacks: {str(e)}")

    def _on_user_events(self, event: Dict[str, Any]):
        """
        Handle user events from the websocket.

        Args:
            event: Event data
        """
        try:
            if "data" in event and "fills" in event["data"]:
                fills = event["data"]["fills"]
                for fill in fills:
                    self.logger.info(f"Fill received: {fill}")

                    # Update order tracking
                    order_id = fill.get("oid")
                    if order_id in self.active_orders:
                        self.active_orders[order_id]["filled"] = True
                        self.active_orders[order_id]["fill_time"] = datetime.now()
                        self.active_orders[order_id]["fill_price"] = float(fill.get("px", 0))
                        self.active_orders[order_id]["fill_size"] = float(fill.get("sz", 0))

                    # Add to updates queue
                    self.order_updates_queue.put({"type": "fill", "data": fill})

        except Exception as e:
            self.logger.error(f"Error processing user event: {str(e)}")

    def _on_order_updates(self, update: Dict[str, Any]):
        """
        Handle order updates from the websocket.

        Args:
            update: Update data
        """
        try:
            self.logger.debug(f"Order update received: {update}")

            # Add to updates queue
            self.order_updates_queue.put({"type": "order_update", "data": update})

        except Exception as e:
            self.logger.error(f"Error processing order update: {str(e)}")

    def place_limit_order(self,
                          coin: str,
                          is_buy: bool,
                          size: float,
                          price: float,
                          post_only: bool = False,
                          reduce_only: bool = False,
                          callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a limit order.

        Args:
            coin: Trading pair symbol
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            price: Limit price
            post_only: Whether order must be maker only (ALO)
            reduce_only: Whether order should only reduce position
            callback: Optional callback when order is filled or cancelled

        Returns:
            Order response and tracking info
        """
        # Determine time-in-force option
        tif = "Alo" if post_only else "Gtc"

        # Place the order
        response = self.exchange.place_order(
            coin=coin,
            is_buy=is_buy,
            size=size,
            price=price,
            order_type={"limit": {"tif": tif}},
            reduce_only=reduce_only
        )

        # Track the order if successful
        if response.get("status") == "ok":
            status = response["response"]["data"]["statuses"][0]
            if "resting" in status:
                order_id = status["resting"]["oid"]

                # Track this order
                self.active_orders[order_id] = {
                    "id": order_id,
                    "coin": coin,
                    "side": "buy" if is_buy else "sell",
                    "size": size,
                    "price": price,
                    "reduce_only": reduce_only,
                    "post_only": post_only,
                    "time": datetime.now(),
                    "filled": False,
                    "cancelled": False,
                    "callback": callback
                }

                self.logger.info(f"Tracking order {order_id} for {coin}")

        return response

    def place_market_order(self,
                           coin: str,
                           is_buy: bool,
                           size: float,
                           reduce_only: bool = False,
                           callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a market order.

        Args:
            coin: Trading pair symbol
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            reduce_only: Whether order should only reduce position
            callback: Optional callback when order is filled

        Returns:
            Order response and tracking info
        """
        response = self.exchange.market_order(
            coin=coin,
            is_buy=is_buy,
            size=size,
            reduce_only=reduce_only
        )

        # Track the order if successful
        if response.get("status") == "ok":
            for status in response["response"]["data"]["statuses"]:
                if "filled" in status:
                    fill = status["filled"]
                    order_id = fill["oid"]

                    # Call the callback immediately for market orders
                    if callback:
                        callback({
                            "id": order_id,
                            "coin": coin,
                            "side": "buy" if is_buy else "sell",
                            "size": float(fill["totalSz"]),
                            "price": float(fill["avgPx"]),
                            "filled": True,
                            "time": datetime.now()
                        })

        return response

    def cancel_order(self, coin: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order by ID.

        Args:
            coin: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        response = self.exchange.cancel_order(coin, order_id)

        # Update tracking if successful
        if response.get("status") == "ok" and order_id in self.active_orders:
            self.active_orders[order_id]["cancelled"] = True
            self.active_orders[order_id]["cancel_time"] = datetime.now()

            # Call the callback if provided
            if self.active_orders[order_id].get("callback"):
                self.active_orders[order_id]["callback"]({
                    **self.active_orders[order_id],
                    "status": "cancelled"
                })

        return response

    def wait_for_fill(self, order_id: int, timeout: float = 30.0) -> Tuple[bool, Dict[str, Any]]:
        """
        Wait for an order to be filled.

        Args:
            order_id: Order ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (was_filled, order_info)
        """
        if order_id not in self.active_orders:
            return False, {}

        start_time = time.time()
        order_info = self.active_orders[order_id]

        while time.time() - start_time < timeout:
            # Check if order was filled or cancelled
            if order_info.get("filled", False):
                return True, order_info
            if order_info.get("cancelled", False):
                return False, order_info

            # Wait a bit before checking again
            time.sleep(0.1)

        # Timeout reached
        return False, order_info

    def process_updates(self):
        """Process any pending order updates from the queue."""
        while not self.order_updates_queue.empty():
            update = self.order_updates_queue.get()

            if update["type"] == "fill":
                fill = update["data"]
                order_id = fill.get("oid")

                # Handle fill callbacks
                if order_id in self.active_orders and self.active_orders[order_id].get("callback"):
                    self.active_orders[order_id]["callback"]({
                        **self.active_orders[order_id],
                        "status": "filled",
                        "fill_price": float(fill.get("px", 0)),
                        "fill_size": float(fill.get("sz", 0))
                    })