"""
Order executor for placing and tracking orders.
Provides high-level order operations and tracking for both spot and perpetual markets.
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
    Supports spot and perpetual markets, with various order types.
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
        
        # Keeps track of fills for reporting
        self.fills: List[Dict[str, Any]] = []
        
        # Setup callbacks
        self._setup_order_callbacks()
        
        # Start the update processing thread
        self.running = True
        self.update_thread = threading.Thread(target=self._process_updates_loop)
        self.update_thread.daemon = True
        self.update_thread.start()

    def _setup_order_callbacks(self):
        """Set up callbacks for order updates and fills."""
        try:
            # Subscribe to user events (fills, etc.)
            self.exchange.info.subscribe(
                {"type": "userEvents", "user": self.exchange.wallet_address},
                self._on_user_events
            )

            # Subscribe to order updates
            self.exchange.info.subscribe(
                {"type": "orderUpdates", "user": self.exchange.wallet_address},
                self._on_order_updates
            )
            
            self.logger.info("Order callbacks set up successfully")

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
                    
                    # Add to fill history
                    self.fills.append({
                        "symbol": fill.get("coin", ""),
                        "side": "Buy" if fill.get("side", "") == "B" else "Sell",
                        "size": float(fill.get("sz", 0)),
                        "price": float(fill.get("px", 0)),
                        "timestamp": fill.get("time", 0),
                        "order_id": fill.get("oid", 0),
                        "pnl": float(fill.get("closedPnl", 0)) if "closedPnl" in fill else 0.0,
                        "is_spot": "/" in fill.get("coin", "")  # Check if this is a spot market
                    })

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
            
    def _process_updates_loop(self):
        """Process updates in a background thread."""
        while self.running:
            try:
                self.process_updates()
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in update processing loop: {str(e)}")
                time.sleep(1)

    def _is_spot_market(self, symbol: str) -> bool:
        """
        Determine if a symbol is for spot or perpetual market.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if spot market, False if perpetual
        """
        # Spot markets typically have a trading pair format with a slash
        return "/" in symbol

    # ======== SPOT MARKET ORDERS ========
    
    def place_spot_limit_order(self,
                          coin: str,
                          is_buy: bool,
                          size: float,
                          price: float,
                          post_only: bool = False,
                          callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a limit order in the spot market.

        Args:
            coin: Trading pair symbol (e.g. 'KOGU/USDC')
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            price: Limit price
            post_only: Whether order must be maker only (ALO)
            callback: Optional callback when order is filled or cancelled

        Returns:
            Order response and tracking info
        """
        if not self._is_spot_market(coin):
            self.logger.warning(f"Symbol {coin} is not a spot market. Use place_perp_limit_order instead.")
            return {"status": "error", "message": "Invalid spot market symbol"}
        
        # Determine order type
        order_type = {"limit": {"tif": "Alo" if post_only else "Gtc"}}
        
        # Place the order
        response = self.exchange.order(
            coin,
            is_buy,
            size,
            price,
            order_type
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
                    "post_only": post_only,
                    "time": datetime.now(),
                    "filled": False,
                    "cancelled": False,
                    "callback": callback,
                    "is_spot": True,
                    "order_type": "limit"
                }

                self.logger.info(f"Tracking spot limit order {order_id} for {coin}: "
                                f"{'Buy' if is_buy else 'Sell'} {size} @ {price}")

        return response

    def place_spot_market_order(self,
                           coin: str,
                           is_buy: bool,
                           size: float,
                           max_slippage: float = 0.05,
                           callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a market order in the spot market using IOC.

        Args:
            coin: Trading pair symbol (e.g. 'KOGU/USDC')
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            max_slippage: Maximum acceptable slippage (default 5%)
            callback: Optional callback when order is filled

        Returns:
            Order response and tracking info
        """
        if not self._is_spot_market(coin):
            self.logger.warning(f"Symbol {coin} is not a spot market. Use place_perp_market_order instead.")
            return {"status": "error", "message": "Invalid spot market symbol"}
        
        # For market orders, get current market price
        try:
            book_data = self.exchange.info.l2_snapshot(coin)
            if book_data and "levels" in book_data and len(book_data["levels"]) >= 2:
                best_bid = float(book_data["levels"][0][0]["px"])
                best_ask = float(book_data["levels"][1][0]["px"])
                
                # Calculate price with slippage
                price = best_ask * (1 + max_slippage) if is_buy else best_bid * (1 - max_slippage)
            else:
                # Fallback: fetch midprice and add/subtract slippage
                all_mids = self.exchange.info.all_mids()
                if coin in all_mids:
                    mid_price = float(all_mids[coin])
                    price = mid_price * (1 + max_slippage) if is_buy else mid_price * (1 - max_slippage)
                else:
                    self.logger.error(f"Could not get price for {coin}")
                    return {"status": "error", "message": "Failed to get market price"}
        except Exception as e:
            self.logger.error(f"Error getting market price: {str(e)}")
            return {"status": "error", "message": f"Failed to get market price: {str(e)}"}
        
        # Use IOC (Immediate-or-Cancel) order type for market orders
        order_type = {"limit": {"tif": "Ioc"}}
        
        # Place the market order
        response = self.exchange.order(
            coin,
            is_buy,
            size,
            price,
            order_type
        )

        # Handle market order fills immediately
        if response.get("status") == "ok":
            for status in response["response"]["data"]["statuses"]:
                if "filled" in status:
                    fill = status["filled"]
                    order_id = fill["oid"]

                    fill_info = {
                        "id": order_id,
                        "coin": coin,
                        "side": "buy" if is_buy else "sell",
                        "size": float(fill["totalSz"]),
                        "price": float(fill["avgPx"]),
                        "filled": True,
                        "time": datetime.now(),
                        "is_spot": True,
                        "order_type": "market"
                    }
                    
                    # Add to fill history
                    self.fills.append({
                        "symbol": coin,
                        "side": "Buy" if is_buy else "Sell",
                        "size": float(fill["totalSz"]),
                        "price": float(fill["avgPx"]),
                        "timestamp": int(time.time() * 1000),
                        "order_id": order_id,
                        "is_spot": True
                    })

                    # Call the callback immediately for market orders
                    if callback:
                        callback(fill_info)
                        
                    self.logger.info(f"Spot market order filled: {fill_info['side']} {fill_info['size']} @ {fill_info['price']}")

        return response

    def cancel_spot_order(self, coin: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel a spot market order by ID.

        Args:
            coin: Trading pair symbol (e.g. 'KOGU/USDC')
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        if not self._is_spot_market(coin):
            self.logger.warning(f"Symbol {coin} is not a spot market. Use cancel_perp_order instead.")
            return {"status": "error", "message": "Invalid spot market symbol"}
        
        response = self.exchange.cancel(coin, order_id)

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
                
            self.logger.info(f"Spot order {order_id} for {coin} cancelled")

        return response
    
    # ======== PERPETUAL MARKET ORDERS ========
    
    def place_perp_limit_order(self,
                          coin: str,
                          is_buy: bool,
                          size: float,
                          price: float,
                          post_only: bool = False,
                          reduce_only: bool = False,
                          callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a limit order in the perpetual market.

        Args:
            coin: Trading pair symbol (e.g. 'ETH')
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            price: Limit price
            post_only: Whether order must be maker only (ALO)
            reduce_only: Whether order should only reduce position
            callback: Optional callback when order is filled or cancelled

        Returns:
            Order response and tracking info
        """
        if self._is_spot_market(coin):
            self.logger.warning(f"Symbol {coin} is a spot market. Use place_spot_limit_order instead.")
            return {"status": "error", "message": "Invalid perpetual market symbol"}
        
        # Determine order type
        order_type = {"limit": {"tif": "Alo" if post_only else "Gtc"}}
        
        # Place the order
        response = self.exchange.order(
            coin,
            is_buy,
            size,
            price,
            order_type,
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
                    "callback": callback,
                    "is_spot": False,
                    "order_type": "limit"
                }

                self.logger.info(f"Tracking perp limit order {order_id} for {coin}: "
                                f"{'Buy' if is_buy else 'Sell'} {size} @ {price}")

        return response

    def place_perp_market_order(self,
                           coin: str,
                           is_buy: bool,
                           size: float,
                           max_slippage: float = 0.05,
                           reduce_only: bool = False,
                           callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a market order in the perpetual market using IOC.

        Args:
            coin: Trading pair symbol (e.g. 'ETH')
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            max_slippage: Maximum acceptable slippage (default 5%)
            reduce_only: Whether order should only reduce position
            callback: Optional callback when order is filled

        Returns:
            Order response and tracking info
        """
        if self._is_spot_market(coin):
            self.logger.warning(f"Symbol {coin} is a spot market. Use place_spot_market_order instead.")
            return {"status": "error", "message": "Invalid perpetual market symbol"}
        
        # For market orders, get current market price
        try:
            book_data = self.exchange.info.l2_snapshot(coin)
            if book_data and "levels" in book_data and len(book_data["levels"]) >= 2:
                best_bid = float(book_data["levels"][0][0]["px"])
                best_ask = float(book_data["levels"][1][0]["px"])
                
                # Calculate price with slippage
                price = best_ask * (1 + max_slippage) if is_buy else best_bid * (1 - max_slippage)
            else:
                # Fallback: fetch midprice and add/subtract slippage
                all_mids = self.exchange.info.all_mids()
                if coin in all_mids:
                    mid_price = float(all_mids[coin])
                    price = mid_price * (1 + max_slippage) if is_buy else mid_price * (1 - max_slippage)
                else:
                    self.logger.error(f"Could not get price for {coin}")
                    return {"status": "error", "message": "Failed to get market price"}
        except Exception as e:
            self.logger.error(f"Error getting market price: {str(e)}")
            return {"status": "error", "message": f"Failed to get market price: {str(e)}"}
        
        # Use IOC (Immediate-or-Cancel) order type for market orders
        order_type = {"limit": {"tif": "Ioc"}}
        
        # Place the market order
        response = self.exchange.order(
            coin,
            is_buy,
            size,
            price,
            order_type,
            reduce_only=reduce_only
        )

        # Handle market order fills immediately
        if response.get("status") == "ok":
            for status in response["response"]["data"]["statuses"]:
                if "filled" in status:
                    fill = status["filled"]
                    order_id = fill["oid"]

                    fill_info = {
                        "id": order_id,
                        "coin": coin,
                        "side": "buy" if is_buy else "sell",
                        "size": float(fill["totalSz"]),
                        "price": float(fill["avgPx"]),
                        "filled": True,
                        "time": datetime.now(),
                        "is_spot": False,
                        "order_type": "market"
                    }
                    
                    # Add to fill history
                    self.fills.append({
                        "symbol": coin,
                        "side": "Buy" if is_buy else "Sell",
                        "size": float(fill["totalSz"]),
                        "price": float(fill["avgPx"]),
                        "timestamp": int(time.time() * 1000),
                        "order_id": order_id,
                        "is_spot": False
                    })

                    # Call the callback immediately for market orders
                    if callback:
                        callback(fill_info)
                        
                    self.logger.info(f"Perp market order filled: {fill_info['side']} {fill_info['size']} @ {fill_info['price']}")

        return response

    def cancel_perp_order(self, coin: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel a perpetual market order by ID.

        Args:
            coin: Trading pair symbol (e.g. 'ETH')
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        if self._is_spot_market(coin):
            self.logger.warning(f"Symbol {coin} is a spot market. Use cancel_spot_order instead.")
            return {"status": "error", "message": "Invalid perpetual market symbol"}
        
        response = self.exchange.cancel(coin, order_id)

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
                
            self.logger.info(f"Perp order {order_id} for {coin} cancelled")

        return response
        
    # ======== GENERAL API METHODS (BACKWARDS COMPATIBILITY) ========
    
    def place_limit_order(self,
                          coin: str,
                          is_buy: bool,
                          size: float,
                          price: float,
                          post_only: bool = False,
                          reduce_only: bool = False,
                          callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a limit order (spot or perpetual).
        
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
        if self._is_spot_market(coin):
            return self.place_spot_limit_order(coin, is_buy, size, price, post_only, callback)
        else:
            return self.place_perp_limit_order(coin, is_buy, size, price, post_only, reduce_only, callback)
    
    def place_market_order(self,
                           coin: str,
                           is_buy: bool,
                           size: float,
                           slippage: float = 0.05,
                           reduce_only: bool = False,
                           callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Place a market order (spot or perpetual).
        
        Args:
            coin: Trading pair symbol
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            reduce_only: Whether order should only reduce position
            callback: Optional callback when order is filled
            
        Returns:
            Order response and tracking info
        """
        if self._is_spot_market(coin):
            return self.place_spot_market_order(coin, is_buy, size, slippage, callback)
        else:
            return self.place_perp_market_order(coin, is_buy, size, slippage, reduce_only, callback)
    
    def cancel_order(self, coin: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order by ID (spot or perpetual).
        
        Args:
            coin: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response
        """
        if self._is_spot_market(coin):
            return self.cancel_spot_order(coin, order_id)
        else:
            return self.cancel_perp_order(coin, order_id)

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
    
    def get_recent_fills(self, limit: int = 10, spot_only: bool = False, perp_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get recent fills.
        
        Args:
            limit: Maximum number of fills to return
            spot_only: Return only spot market fills
            perp_only: Return only perpetual market fills
            
        Returns:
            List of recent fills
        """
        filtered_fills = self.fills
        
        if spot_only:
            filtered_fills = [fill for fill in filtered_fills if fill.get("is_spot", False)]
        elif perp_only:
            filtered_fills = [fill for fill in filtered_fills if not fill.get("is_spot", False)]
            
        return sorted(filtered_fills, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]
    
    def cleanup(self):
        """Clean up resources when shutting down."""
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1.0)