"""
Basic market making strategy implementation.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from elysium.strategies.base_strategy import BaseStrategy
from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor


class BasicMarketMaking(BaseStrategy):
    """
    A basic market making strategy that places orders around the mid price.
    
    This strategy:
    1. Places buy and sell orders at a configurable spread around the mid price
    2. Refreshes orders periodically or when market moves significantly
    3. Adjusts order sizes based on current inventory
    """

    def __init__(self,
                 config: Dict[str, Any],
                 exchange: ExchangeManager,
                 position_manager: PositionManager,
                 order_executor: OrderExecutor,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the market making strategy.

        Args:
            config: Configuration parameters for the strategy
            exchange: Exchange manager instance
            position_manager: Position manager instance
            order_executor: Order executor instance
            logger: Optional logger instance
        """
        super().__init__(config, exchange, position_manager, order_executor, logger)

        # Extract configuration
        self.symbol = config.get("symbol", "KOGU/USDC")  # Default to KOGU/USDC
        self.display_name = config.get("display_name", self.symbol)
        self.max_order_size = float(config.get("max_order_size", 6000.0))
        self.min_order_size = float(config.get("min_order_size", 1000.0))
        self.position_use_pct = float(config.get("position_use_pct", 0.90))
        self.initial_offset = float(config.get("initial_offset", 0.0001))  # 0.01%
        self.min_offset = float(config.get("min_offset", 0.00009))  # 0.009%
        self.offset_reduction = float(config.get("offset_reduction", 0.00001))
        self.order_refresh_time = float(config.get("order_refresh_time", 10.0))  # seconds
        self.max_active_orders = int(config.get("max_active_orders", 4))

        # Internal state
        self.current_buy_offset = self.initial_offset
        self.current_sell_offset = self.initial_offset
        self.best_bid = 0.0
        self.best_ask = 0.0
        self.last_order_time = 0
        self.active_orders: Dict[int, Dict[str, Any]] = {}
        self.orderbook_subscription_id = None

        self.logger.info(f"Initialized {self.__class__.__name__} for {self.display_name}")
        self.logger.info(f"Configuration: {config}")

    def initialize(self) -> bool:
        """
        Initialize the strategy.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Subscribe to orderbook updates
            self.orderbook_subscription_id = self.exchange.subscribe_to_orderbook(
                self.symbol, 
                self._handle_orderbook_update
            )
            
            if self.orderbook_subscription_id < 0:
                self.logger.error(f"Failed to subscribe to orderbook for {self.symbol}")
                return False
                
            self.logger.info(f"Subscribed to orderbook for {self.symbol}")
            
            # Reset internal state
            self.current_buy_offset = self.initial_offset
            self.current_sell_offset = self.initial_offset
            self.last_order_time = 0
            self.active_orders = {}
            
            # Cancel any existing orders
            self.cancel_all_orders()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing strategy: {str(e)}")
            return False

    def _handle_orderbook_update(self, update: Dict[str, Any]) -> None:
        """
        Process orderbook updates from the websocket.
        
        Args:
            update: Orderbook update data
        """
        try:
            if "data" in update and "levels" in update["data"] and len(update["data"]["levels"]) >= 2:
                bids = update["data"]["levels"][0]
                asks = update["data"]["levels"][1]
                
                if bids and asks:
                    self.best_bid = float(bids[0]["px"])
                    self.best_ask = float(asks[0]["px"])
                    
                    # Check if it's time to refresh orders
                    current_time = int(time.time() * 1000)
                    if (current_time - self.last_order_time) >= (self.order_refresh_time * 1000):
                        self.on_tick()
        
        except Exception as e:
            self.logger.error(f"Error processing orderbook update: {str(e)}")

    def on_tick(self) -> None:
        """Process market update and refresh orders if needed."""
        try:
            # Place new orders
            self.place_orders()
            
        except Exception as e:
            self.logger.error(f"Error in on_tick: {str(e)}")

    def on_fill(self, fill_data: Dict[str, Any]) -> None:
        """
        Process a fill event.
        
        Args:
            fill_data: Fill data
        """
        try:
            self.logger.info(f"Fill received: {fill_data}")
            
            # Update trade counter
            self.trades_executed += 1
            
            # Refresh orders on fill
            self.on_tick()
            
        except Exception as e:
            self.logger.error(f"Error processing fill: {str(e)}")

    def on_order_update(self, order_data: Dict[str, Any]) -> None:
        """
        Process order updates.
        
        Args:
            order_data: Order update data
        """
        pass  # Process order updates if needed

    def place_orders(self) -> None:
        """Place market making orders."""
        try:
            # Cancel existing orders
            self.cancel_all_orders()
            
            # Adjust offsets to move closer to market price over time
            self.current_buy_offset = max(
                self.current_buy_offset - self.offset_reduction, 
                self.min_offset
            )
            self.current_sell_offset = max(
                self.current_sell_offset - self.offset_reduction,
                self.min_offset
            )
            
            # Calculate prices with dynamic offsets
            buy_price = self._format_price(self.best_ask * (1 - self.current_buy_offset))
            sell_price = self._format_price(self.best_bid * (1 + self.current_sell_offset))
            
            self.logger.info(f"Placing orders - Buy: {buy_price} (-{self.current_buy_offset:.6f}), Sell: {sell_price} (+{self.current_sell_offset:.6f})")
            
            # Get position and balance information
            position = self._get_token_position()
            usdc_balance = self._get_usdc_balance()
            
            self.logger.info(f"Account state - Position: {position} {self.display_name}, USDC: {usdc_balance}")
            
            # Calculate buy size based on USDC balance
            max_possible_buy = min(self.max_order_size, (usdc_balance / buy_price) * 0.95)  # Use 95% of available balance
            buy_size = max(min(max_possible_buy, self.max_order_size), self.min_order_size)
            buy_size = float(f"{buy_size:.2f}")  # Round to 2 decimal places
            
            # Calculate sell size based on available position
            max_sell_size = position * self.position_use_pct
            sell_size = max(min(max_sell_size, self.max_order_size), self.min_order_size)
            sell_size = float(f"{sell_size:.2f}")  # Round to 2 decimal places
            
            # Place buy order if size is sufficient
            if buy_size >= self.min_order_size:
                self._place_limit_order(is_buy=True, size=buy_size, price=buy_price)
            
            # Place sell order if size is sufficient
            if sell_size >= self.min_order_size:
                self._place_limit_order(is_buy=False, size=sell_size, price=sell_price)
            
            # Update last order time
            self.last_order_time = int(time.time() * 1000)
            
        except Exception as e:
            self.logger.error(f"Error placing orders: {str(e)}")

    def _place_limit_order(self, is_buy: bool, size: float, price: float) -> None:
        """
        Place a limit order.
        
        Args:
            is_buy: True for buy, False for sell
            size: Order size
            price: Order price
        """
        side_str = "Buy" if is_buy else "Sell"
        self.logger.info(f"Placing {side_str} order: {size} @ {price}")
        
        response = self.order_executor.place_limit_order(
            coin=self.symbol,
            is_buy=is_buy,
            size=size,
            price=price,
            post_only=True,
            callback=self.on_fill
        )
        
        if response.get("status") == "ok":
            self.logger.info(f"{side_str} order placed successfully")
        else:
            self.logger.error(f"Failed to place {side_str} order: {response}")

    def cancel_all_orders(self) -> None:
        """Cancel all existing orders for the strategy."""
        try:
            count = self.exchange.cancel_all_orders(self.symbol)
            if count > 0:
                self.logger.info(f"Cancelled {count} existing orders")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")

    def _get_token_position(self) -> float:
        """
        Get current token position.
        
        Returns:
            Token position size
        """
        try:
            spot_state = self.exchange.info.spot_user_state(self.exchange.account_address)
            
            # Get base token from symbol
            base_token = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
            
            for balance in spot_state.get("balances", []):
                if balance.get("coin") == base_token:
                    return float(balance.get("total", "0"))
            
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting token position: {str(e)}")
            return 0.0
    
    def _get_usdc_balance(self) -> float:
        """
        Get available USDC balance.
        
        Returns:
            USDC balance
        """
        try:
            spot_state = self.exchange.info.spot_user_state(self.exchange.account_address)
            
            for balance in spot_state.get("balances", []):
                if balance.get("coin") == "USDC":
                    return float(balance.get("total", "0"))
            
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting USDC balance: {str(e)}")
            return 0.0
    
    def _format_price(self, price: float) -> float:
        """
        Format price to the correct number of decimal places.
        
        Args:
            price: Price to format
            
        Returns:
            Formatted price
        """
        # For spot trading we use 6 decimal places
        return round(price, 6)

# =================================================Old BasicMm.py==============================================
# Basic Mm module
# """
# Basic market making strategy implementation.
# """

# import logging
# import time
# from typing import Dict, Any, List, Optional, Tuple
# from datetime import datetime

# from elysium.strategies.base_strategy import BaseStrategy
# from elysium.core.exchange import ExchangeManager
# from elysium.core.position_manager import PositionManager
# from elysium.core.order_executor import OrderExecutor
# from elysium.data.market_data import MarketData


# class BasicMarketMaking(BaseStrategy):
#     """
#     A basic market making strategy that places orders around the mid price.

#     This strategy:
#     1. Places buy and sell orders at a configurable spread around the mid price
#     2. Refreshes orders when the market moves beyond a threshold
#     3. Manages inventory to stay within target range
#     4. Cancels and replaces orders regularly
#     """

#     def __init__(self,
#                  config: Dict[str, Any],
#                  exchange: ExchangeManager,
#                  position_manager: PositionManager,
#                  order_executor: OrderExecutor,
#                  logger: Optional[logging.Logger] = None):
#         """
#         Initialize the market making strategy.

#         Args:
#             config: Configuration parameters for the strategy
#             exchange: Exchange manager instance
#             position_manager: Position manager instance
#             order_executor: Order executor instance
#             logger: Optional logger instance
#         """
#         super().__init__(config, exchange, position_manager, order_executor, logger)

#         # Extract configuration
#         self.symbol = config.get("symbol", "ETH")
#         self.display_name = config.get("display_name", self.symbol)
#         self.order_size = config.get("order_size", 0.1)
#         self.min_spread = config.get("min_spread", 0.002)  # 0.2%
#         self.max_spread = config.get("max_spread", 0.005)  # 0.5%
#         self.inventory_target = config.get("inventory_target", 0.0)
#         self.inventory_range = config.get("inventory_range", 0.5)
#         self.order_refresh_time = config.get("order_refresh_time", 30)  # seconds
#         self.max_orders_per_side = config.get("max_orders_per_side", 1)
#         self.tick_interval = config.get("tick_interval", 1.0)  # seconds
#         self.max_position = config.get("max_position", 1.0)
#         self.min_order_size = config.get("min_order_size", 0.01)

#         # Internal state
#         self.active_buys = {}
#         self.active_sells = {}
#         self.last_order_refresh = 0
#         self.current_position = 0
#         self.mid_price = 0
#         self.market_data = None

#         # Configure max spread with dynamic adjustment
#         self.original_min_spread = self.min_spread
#         self.original_max_spread = self.max_spread
#         self.inventory_skew_enabled = config.get("inventory_skew_enabled", True)

#         # Initialize market data
#         self.initialize_market_data()

#     def initialize_market_data(self):
#         """Initialize market data handler."""
#         self.market_data = MarketData(self.exchange.info, self.logger)

#         # Subscribe to order book updates
#         self.market_data.subscribe_to_orderbook(self.symbol, self.on_orderbook_update)

#     def initialize(self) -> bool:
#         """
#         Initialize the strategy.

#         Returns:
#             bool: True if initialization was successful, False otherwise
#         """
#         try:
#             # Get initial market data
#             self.update_market_data()

#             if self.mid_price == 0:
#                 self.logger.error(f"Could not get mid price for {self.symbol}")
#                 return False

#             # Update position
#             self.update_position()

#             # Cancel any existing orders
#             self.cancel_all_orders()

#             self.logger.info(f"Initialized market making strategy for {self.symbol}")
#             self.logger.info(f"Initial mid price: {self.mid_price}")
#             self.logger.info(f"Initial position: {self.current_position}")

#             return True

#         except Exception as e:
#             self.logger.error(f"Error initializing strategy: {str(e)}")
#             return False

#     def update_market_data(self) -> None:
#         """Update market data from exchange."""
#         try:
#             # Get current mid price
#             self.mid_price = self.market_data.get_mid_price(self.symbol, force_refresh=True)

#             if self.mid_price == 0:
#                 self.logger.warning(f"Could not get mid price for {self.symbol}")

#         except Exception as e:
#             self.logger.error(f"Error updating market data: {str(e)}")

#     def update_position(self) -> None:
#         """Update current position from exchange."""
#         try:
#             # For spot market making, get balance
#             spot_balances = self.position_manager.exchange.info.spot_user_state(
#                 self.position_manager.exchange.account_address
#             )

#             found = False
#             # Parse symbol name to extract the base asset
#             base_asset = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol

#             for balance in spot_balances.get("balances", []):
#                 if balance.get("coin") == base_asset:
#                     self.current_position = float(balance.get("total", 0))
#                     found = True
#                     break

#             if not found:
#                 self.current_position = 0

#         except Exception as e:
#             self.logger.error(f"Error updating position: {str(e)}")

#     def calculate_order_prices(self) -> Tuple[float, float]:
#         """
#         Calculate order prices based on market and inventory.

#         Returns:
#             Tuple with (buy_price, sell_price)
#         """
#         # Get current bid/ask
#         best_bid, best_ask = self.market_data.get_best_bid_ask(self.symbol)

#         if best_bid == 0 or best_ask == 0:
#             self.logger.warning(f"Could not get bid/ask for {self.symbol}, using mid price")
#             # Use mid price with default spread
#             buy_price = self.mid_price * (1 - self.min_spread)
#             sell_price = self.mid_price * (1 + self.min_spread)
#             return buy_price, sell_price

#         # Calculate default prices based on market spread
#         market_spread = (best_ask - best_bid) / best_bid

#         # Adjust our spread based on market
#         adjusted_min_spread = max(self.min_spread, market_spread * 0.5)
#         adjusted_max_spread = max(self.max_spread, market_spread * 2)

#         # Default to min_spread
#         buy_spread = adjusted_min_spread
#         sell_spread = adjusted_min_spread

#         # Apply inventory skew if enabled
#         if self.inventory_skew_enabled:
#             # Calculate inventory skew factor (-1 to 1 scale)
#             inventory_skew = (self.current_position - self.inventory_target) / self.inventory_range
#             inventory_skew = max(-1, min(1, inventory_skew))  # Clamp to [-1, 1]

#             # Adjust spreads based on inventory
#             # If we have too much inventory, tighten buy spread and widen sell spread
#             # If we have too little inventory, tighten sell spread and widen buy spread
#             spread_range = adjusted_max_spread - adjusted_min_spread

#             if inventory_skew > 0:  # We have too much inventory
#                 buy_spread = adjusted_min_spread + spread_range * inventory_skew  # Widen buy spread
#                 sell_spread = adjusted_min_spread  # Tighten sell spread
#             else:  # We have too little inventory
#                 buy_spread = adjusted_min_spread  # Tighten buy spread
#                 sell_spread = adjusted_min_spread + spread_range * abs(inventory_skew)  # Widen sell spread

#         # Calculate final prices
#         buy_price = best_bid * (1 - buy_spread)
#         sell_price = best_ask * (1 + sell_spread)

#         return buy_price, sell_price

#     def calculate_order_sizes(self) -> Tuple[float, float]:
#         """
#         Calculate order sizes based on inventory.

#         Returns:
#             Tuple with (buy_size, sell_size)
#         """
#         # Default sizes
#         buy_size = self.order_size
#         sell_size = self.order_size

#         # Adjust based on current position
#         if self.inventory_skew_enabled:
#             # Calculate available room for position
#             buy_capacity = self.max_position - self.current_position
#             sell_capacity = self.current_position

#             # Scale order sizes
#             buy_size = min(buy_size, buy_capacity)
#             sell_size = min(sell_size, sell_capacity)

#             # Ensure minimum size
#             buy_size = max(buy_size, self.min_order_size)
#             sell_size = max(sell_size, self.min_order_size)

#         return buy_size, sell_size

#     def on_tick(self) -> None:
#         """Process a tick update."""
#         # Check if we need to refresh orders
#         current_time = time.time()

#         # Update market data
#         self.update_market_data()

#         # Update position
#         self.update_position()

#         # Only refresh orders periodically or if prices have moved significantly
#         if current_time - self.last_order_refresh >= self.order_refresh_time:
#             self.refresh_orders()
#             self.last_order_refresh = current_time

#     def on_orderbook_update(self, orderbook_data: Dict[str, Any]) -> None:
#         """
#         Process orderbook update from websocket.

#         Args:
#             orderbook_data: Orderbook data
#         """
#         try:
#             # Check if we have a significant price move
#             if "levels" in orderbook_data and len(orderbook_data["levels"]) >= 2:
#                 bid_levels = orderbook_data["levels"][0]
#                 ask_levels = orderbook_data["levels"][1]

#                 if bid_levels and ask_levels:
#                     best_bid = float(bid_levels[0]["px"])
#                     best_ask = float(ask_levels[0]["px"])
#                     new_mid = (best_bid + best_ask) / 2

#                     # Check if price moved significantly
#                     if self.mid_price > 0:
#                         price_change_pct = abs(new_mid - self.mid_price) / self.mid_price

#                         # If price moved more than half our min spread, refresh orders
#                         if price_change_pct > (self.min_spread / 2):
#                             self.mid_price = new_mid
#                             current_time = time.time()

#                             # Only refresh if we haven't recently refreshed
#                             if current_time - self.last_order_refresh >= 5:  # 5 second throttle
#                                 self.refresh_orders()
#                                 self.last_order_refresh = current_time
#                     else:
#                         self.mid_price = new_mid
#         except Exception as e:
#             self.logger.error(f"Error in orderbook update: {str(e)}")

#     def on_fill(self, fill_data: Dict[str, Any]) -> None:
#         """
#         Process a fill event.

#         Args:
#             fill_data: Fill data from exchange
#         """
#         try:
#             self.logger.info(f"Fill received: {fill_data}")

#             # Update position
#             self.update_position()

#             # Update trade counter
#             self.trades_executed += 1

#             # Refresh orders after a fill
#             self.refresh_orders()

#         except Exception as e:
#             self.logger.error(f"Error in on_fill: {str(e)}")

#     def on_order_update(self, order_data: Dict[str, Any]) -> None:
#         """
#         Process an order update event.

#         Args:
#             order_data: Order update data
#         """
#         try:
#             self.logger.debug(f"Order update: {order_data}")

#             # Handle order status updates (cancelled, filled, etc.)
#             order_id = order_data.get("oid")

#             if order_id in self.active_buys:
#                 if order_data.get("status") in ["filled", "canceled"]:
#                     del self.active_buys[order_id]

#             elif order_id in self.active_sells:
#                 if order_data.get("status") in ["filled", "canceled"]:
#                     del self.active_sells[order_id]

#         except Exception as e:
#             self.logger.error(f"Error in on_order_update: {str(e)}")

#     def refresh_orders(self) -> None:
#         """Cancel existing orders and place new ones."""
#         try:
#             self.logger.info(f"Refreshing orders for {self.symbol}")

#             # Cancel existing orders
#             self.cancel_all_orders()

#             # Calculate order prices
#             buy_price, sell_price = self.calculate_order_prices()

#             # Calculate order sizes
#             buy_size, sell_size = self.calculate_order_sizes()

#             self.logger.info(f"Order prices - Buy: {buy_price:.8f}, Sell: {sell_price:.8f}")
#             self.logger.info(f"Order sizes - Buy: {buy_size:.8f}, Sell: {sell_size:.8f}")

#             # Place buy order if we have capacity
#             if buy_size >= self.min_order_size:
#                 response = self.order_executor.place_limit_order(
#                     coin=self.symbol,
#                     is_buy=True,
#                     size=buy_size,
#                     price=buy_price,
#                     post_only=True,
#                     callback=self.on_order_callback
#                 )

#                 if response.get("status") == "ok":
#                     oid = response.get("response", {}).get("data", {}).get("statuses", [{}])[0].get("resting", {}).get(
#                         "oid")
#                     if oid:
#                         self.active_buys[oid] = {
#                             "price": buy_price,
#                             "size": buy_size,
#                             "time": time.time()
#                         }
#                         self.logger.info(f"Placed buy order: {buy_size} @ {buy_price}")

#             # Place sell order if we have inventory
#             if sell_size >= self.min_order_size:
#                 response = self.order_executor.place_limit_order(
#                     coin=self.symbol,
#                     is_buy=False,
#                     size=sell_size,
#                     price=sell_price,
#                     post_only=True,
#                     callback=self.on_order_callback
#                 )

#                 if response.get("status") == "ok":
#                     oid = response.get("response", {}).get("data", {}).get("statuses", [{}])[0].get("resting", {}).get(
#                         "oid")
#                     if oid:
#                         self.active_sells[oid] = {
#                             "price": sell_price,
#                             "size": sell_size,
#                             "time": time.time()
#                         }
#                         self.logger.info(f"Placed sell order: {sell_size} @ {sell_price}")

#         except Exception as e:
#             self.logger.error(f"Error refreshing orders: {str(e)}")

#     def cancel_all_orders(self) -> None:
#         """Cancel all existing orders."""
#         try:
#             result = self.order_executor.exchange.cancel_all_orders(self.symbol)
#             self.active_buys = {}
#             self.active_sells = {}
#             self.logger.info(f"Cancelled all orders for {self.symbol}")
#         except Exception as e:
#             self.logger.error(f"Error cancelling orders: {str(e)}")

#     def on_order_callback(self, order_data: Dict[str, Any]) -> None:
#         """
#         Callback for order events.

#         Args:
#             order_data: Order data including status updates
#         """
#         try:
#             order_id = order_data.get("id")
#             status = order_data.get("status")

#             self.logger.debug(f"Order callback: {order_id} - {status}")

#             if status == "filled":
#                 # Process fill
#                 self.logger.info(f"Order {order_id} filled: {order_data.get('size')} @ {order_data.get('price')}")

#                 # Update position
#                 self.update_position()

#                 # Refresh orders after fill
#                 self.refresh_orders()

#             elif status == "cancelled":
#                 # Process cancellation
#                 self.logger.debug(f"Order {order_id} cancelled")

#                 # Remove from active orders
#                 if order_id in self.active_buys:
#                     del self.active_buys[order_id]
#                 elif order_id in self.active_sells:
#                     del self.active_sells[order_id]

#         except Exception as e:
#             self.logger.error(f"Error in order callback: {str(e)}")