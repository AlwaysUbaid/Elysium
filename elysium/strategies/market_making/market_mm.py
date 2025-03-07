"""
Market order-based market making strategy implementation.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from elysium.strategies.base_strategy import BaseStrategy
from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor


class MarketOrderMaking(BaseStrategy):
    """
    A market order-based market making strategy.
    
    This strategy:
    1. Monitors the market and places market orders at regular intervals
    2. Uses configurable target positions and rebalancing thresholds
    3. Alternates between buy and sell orders based on target position
    4. Uses smaller order sizes for less price impact
    """

    def __init__(self,
                 config: Dict[str, Any],
                 exchange: ExchangeManager,
                 position_manager: PositionManager,
                 order_executor: OrderExecutor,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the market order-based strategy.

        Args:
            config: Configuration parameters for the strategy
            exchange: Exchange manager instance
            position_manager: Position manager instance
            order_executor: Order executor instance
            logger: Optional logger instance
        """
        super().__init__(config, exchange, position_manager, order_executor, logger)

        # Extract configuration
        self.symbol = config.get("symbol", "KOGU/USDC")
        self.display_name = config.get("display_name", self.symbol)
        self.max_order_size = float(config.get("max_order_size", 1000.0))
        self.min_order_size = float(config.get("min_order_size", 100.0))
        self.target_position = float(config.get("target_position", 5000.0))  # Target token balance
        self.rebalance_threshold = float(config.get("rebalance_threshold", 0.1))  # 10% of target
        self.order_interval = float(config.get("order_interval", 30.0))  # seconds
        self.max_slippage = float(config.get("max_slippage", 0.005))  # 0.5% max slippage
        self.order_size_pct = float(config.get("order_size_pct", 0.2))  # 20% of rebalance amount

        # Internal state
        self.last_order_time = 0
        self.best_bid = 0.0
        self.best_ask = 0.0
        self.orderbook_subscription_id = None
        self.last_order_was_buy = False  # Track last order side for alternating

        self.logger.info(f"Initialized {self.__class__.__name__} for {self.display_name}")
        self.logger.info(f"Configuration: {config}")

    @classmethod
    def get_default_parameters(cls) -> Dict[str, Any]:
        """
        Get default parameters for the strategy.
        
        Returns:
            Default parameters
        """
        return {
            "symbol": "KOGU/USDC",
            "display_name": "KOGU/USDC",
            "max_order_size": 1000.0,
            "min_order_size": 100.0,
            "target_position": 5000.0,
            "rebalance_threshold": 0.1,
            "order_interval": 30.0,
            "max_slippage": 0.005,
            "order_size_pct": 0.2
        }

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
            self.last_order_time = 0
            
            # Log initial position
            current_position = self._get_token_position()
            self.logger.info(f"Initial position: {current_position} {self.symbol}")
            self.logger.info(f"Target position: {self.target_position} {self.symbol}")
            
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
                    
                    # Check if it's time to place a new order
                    current_time = int(time.time())
                    if (current_time - self.last_order_time) >= self.order_interval:
                        self.on_tick()
        
        except Exception as e:
            self.logger.error(f"Error processing orderbook update: {str(e)}")

    def on_tick(self) -> None:
        """Process market update and place orders if needed."""
        try:
            # Get current position
            current_position = self._get_token_position()
            
            # Calculate position deviation from target
            position_diff = self.target_position - current_position
            
            # Check if deviation exceeds threshold
            threshold_amount = self.target_position * self.rebalance_threshold
            
            # Get current time
            current_time = int(time.time())  # Define current_time properly
            
            if abs(position_diff) >= threshold_amount:
                # Determine order side
                is_buy = position_diff > 0
                
                # Calculate order size (a fraction of the total imbalance)
                order_size = min(
                    abs(position_diff) * self.order_size_pct,
                    self.max_order_size
                )
                
                # Ensure order size is above minimum
                if order_size >= self.min_order_size:
                    # Place market order
                    self._place_market_order(is_buy, order_size)
                    self.last_order_time = current_time
                    self.last_order_was_buy = is_buy
                else:
                    self.logger.info(f"Order size {order_size} below minimum {self.min_order_size}")
            else:
                # If we're within the threshold, place alternating small orders for market making
                if current_time - self.last_order_time >= (self.order_interval * 2):
                    # Toggle the order side
                    is_buy = not self.last_order_was_buy
                    
                    # Use minimum order size for regular market making
                    order_size = self.min_order_size
                    
                    # Place market order
                    self._place_market_order(is_buy, order_size)
                    self.last_order_time = current_time
                    self.last_order_was_buy = is_buy
                    
                    self.logger.info(f"Placed alternating {'buy' if is_buy else 'sell'} order for market making")
                
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
            
            # Log the fill details
            side = fill_data.get("side", "")
            price = float(fill_data.get("px", 0))
            size = float(fill_data.get("sz", 0))
            
            self.logger.info(f"Trade executed: {side} {size} @ {price}")
            
            # Get updated position
            current_position = self._get_token_position()
            self.logger.info(f"Current position: {current_position} {self.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error processing fill: {str(e)}")

    def on_order_update(self, order_data: Dict[str, Any]) -> None:
        """
        Process order updates.
        
        Args:
            order_data: Order update data
        """
        pass  # Market orders are executed immediately, so we don't need to track them

    def _place_market_order(self, is_buy: bool, size: float) -> None:
        """
        Place a market order.
        
        Args:
            is_buy: True for buy, False for sell
            size: Order size
        """
        try:
            side_str = "Buy" if is_buy else "Sell"
            self.logger.info(f"Placing market {side_str} order: {size}")
            
            # Calculate a price with slippage (for market orders)
            # For buy orders: use best ask + slippage
            # For sell orders: use best bid - slippage
            price = 0
            if is_buy:
                price = self.best_ask * (1 + self.max_slippage)
            else:
                price = self.best_bid * (1 - self.max_slippage)
            
            # Place market order with IOC (Immediate-or-Cancel) type
            response = self.order_executor.place_market_order(
                coin=self.symbol,
                is_buy=is_buy,
                size=size,
                slippage=self.max_slippage,  # This is just used for slippage protection
                callback=self.on_fill
            )
            
            if response.get("status") == "ok":
                self.logger.info(f"Market {side_str} order placed successfully")
            else:
                self.logger.error(f"Failed to place market {side_str} order: {response}")
                
        except Exception as e:
            self.logger.error(f"Error placing market order: {str(e)}")

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