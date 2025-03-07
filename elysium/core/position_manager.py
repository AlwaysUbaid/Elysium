"""
Position manager for tracking and managing trading positions.
Includes risk management and position sizing functionality.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import threading

from elysium.core.exchange import ExchangeManager


class PositionManager:
    """
    Manages positions and provides risk management functionality.
    """

    def __init__(self,
                 exchange_manager: ExchangeManager,
                 max_position_size: Dict[str, float] = None,
                 max_drawdown_pct: float = 0.1,
                 risk_per_trade: float = 0.01,
                 position_update_interval: float = 10.0,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the position manager.

        Args:
            exchange_manager: ExchangeManager instance
            max_position_size: Maximum position size by coin {"ETH": 5.0, ...}
            max_drawdown_pct: Maximum allowed drawdown as percentage (0.1 = 10%)
            risk_per_trade: Percentage of account to risk per trade (0.01 = 1%)
            position_update_interval: How often to refresh positions in seconds
            logger: Optional logger instance
        """
        self.exchange = exchange_manager
        self.max_position_size = max_position_size or {}
        self.max_drawdown_pct = max_drawdown_pct
        self.risk_per_trade = risk_per_trade
        self.position_update_interval = position_update_interval
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Track position state
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.position_history: Dict[str, List[Dict[str, Any]]] = {}
        self.initial_account_value = 0
        self.last_account_value = 0
        self.account_values_history: List[Dict[str, Any]] = []
        
        # For position updates
        self.running = True
        self.update_thread = threading.Thread(target=self._position_update_loop)
        self.update_thread.daemon = True
        
        # Initialize positions
        self.refresh_positions()
        
        # Start position update thread
        self.update_thread.start()
        self.logger.info("Position manager initialized")

    def _position_update_loop(self):
        """Background thread to periodically update positions."""
        while self.running:
            try:
                self.refresh_positions()
                time.sleep(self.position_update_interval)
            except Exception as e:
                self.logger.error(f"Error in position update loop: {str(e)}")
                time.sleep(self.position_update_interval)

    def refresh_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Refresh position data from the exchange.

        Returns:
            Current positions
        """
        try:
            # Get perpetual positions
            user_state = self.exchange.info.user_state(self.exchange.wallet_address)

            # Update account value tracking
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            
            # Record account value history
            self.account_values_history.append({
                "timestamp": datetime.now(),
                "value": account_value
            })
            
            # Keep history within reasonable size
            if len(self.account_values_history) > 1000:
                self.account_values_history = self.account_values_history[-1000:]

            if self.initial_account_value == 0:
                self.initial_account_value = account_value

            self.last_account_value = account_value

            # Process positions
            positions = {}
            for asset_position in user_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                coin = position.get("coin", "")
                size = float(position.get("szi", 0))
                
                # Only track non-zero positions
                if size != 0:
                    positions[coin] = {
                        "size": size,
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0)) if "markPx" in position else 0,
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0)),
                        "side": "long" if size > 0 else "short",
                        "value": abs(size) * float(position.get("markPx", 0)) if "markPx" in position else 0
                    }

                    # Track position history
                    if coin not in self.position_history:
                        self.position_history[coin] = []

                    self.position_history[coin].append({
                        "timestamp": datetime.now(),
                        "size": positions[coin]["size"],
                        "price": positions[coin]["mark_price"],
                        "pnl": positions[coin]["unrealized_pnl"]
                    })
                    
                    # Keep history within reasonable size
                    if len(self.position_history[coin]) > 1000:
                        self.position_history[coin] = self.position_history[coin][-1000:]

            # For previously tracked coins that now have zero positions
            for coin in self.positions:
                if coin not in positions:
                    # Add history entry showing position is closed
                    if coin in self.position_history:
                        self.position_history[coin].append({
                            "timestamp": datetime.now(),
                            "size": 0,
                            "price": 0,
                            "pnl": 0
                        })

            self.positions = positions
            return positions

        except Exception as e:
            self.logger.error(f"Error refreshing positions: {str(e)}")
            return {}

    def get_position(self, coin: str) -> Dict[str, Any]:
        """
        Get position information for a specific coin.

        Args:
            coin: Coin symbol

        Returns:
            Position information or empty dict if no position
        """
        return self.positions.get(coin, {})

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all current positions.
        
        Returns:
            Dictionary of all positions keyed by coin
        """
        return self.positions
    
    def get_position_value(self, coin: str) -> float:
        """
        Get the USD value of a position.
        
        Args:
            coin: Coin symbol
            
        Returns:
            Position value in USD
        """
        position = self.get_position(coin)
        if not position:
            return 0.0
        
        return abs(position["size"]) * position["mark_price"]

    def get_drawdown(self) -> float:
        """
        Calculate current drawdown percentage.

        Returns:
            Current drawdown as a percentage (0.05 = 5%)
        """
        if self.initial_account_value == 0:
            return 0

        return max(0, (self.initial_account_value - self.last_account_value) / self.initial_account_value)

    def get_account_value(self) -> float:
        """
        Get current account value.
        
        Returns:
            Current account value in USD
        """
        return self.last_account_value

    def check_risk_limits(self) -> Tuple[bool, List[str]]:
        """
        Check if any risk limits are being exceeded.

        Returns:
            Tuple of (is_within_limits, list_of_warnings)
        """
        warnings = []

        # Check drawdown limit
        drawdown = self.get_drawdown()
        if drawdown > self.max_drawdown_pct:
            warnings.append(f"Maximum drawdown exceeded: {drawdown:.2%} > {self.max_drawdown_pct:.2%}")

        # Check position size limits
        for coin, position in self.positions.items():
            max_size = self.max_position_size.get(coin, float('inf'))
            if abs(position["size"]) > max_size:
                warnings.append(f"Position size limit exceeded for {coin}: {abs(position['size'])} > {max_size}")

        return len(warnings) == 0, warnings

    def calculate_position_size(self,
                               coin: str,
                               entry_price: float,
                               stop_loss_price: Optional[float] = None,
                               risk_override: Optional[float] = None) -> float:
        """
        Calculate optimal position size based on risk parameters.

        Args:
            coin: Coin to calculate for
            entry_price: Expected entry price
            stop_loss_price: Stop loss price (if None, assumes 1% risk)
            risk_override: Override default risk per trade (if None, uses default)

        Returns:
            Optimal position size
        """
        # Use default or override risk percentage
        risk_pct = risk_override if risk_override is not None else self.risk_per_trade
        
        # Get account value
        account_value = self.last_account_value
        if account_value <= 0:
            self.logger.warning("Account value is zero or negative, cannot calculate position size")
            return 0.0
        
        # Calculate risk amount in USD
        risk_amount = account_value * risk_pct
        
        # Calculate position size based on entry and stop loss
        if stop_loss_price is not None and stop_loss_price > 0:
            # Calculate risk per unit
            price_delta = abs(entry_price - stop_loss_price)
            if price_delta <= 0:
                self.logger.warning(f"Invalid stop loss for {coin}, entry: {entry_price}, stop: {stop_loss_price}")
                return 0.0
                
            # Position size = risk amount / risk per unit
            position_size = risk_amount / price_delta
        else:
            # Default to 1% price movement for stop loss
            position_size = risk_amount / (entry_price * 0.01)
        
        # Apply maximum position limit if set
        max_size = self.max_position_size.get(coin, float('inf'))
        position_size = min(position_size, max_size)
        
        self.logger.info(f"Calculated position size for {coin}: {position_size} (${risk_amount:.2f} risk)")
        return position_size

    def get_position_history(self, coin: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get position history for a coin.
        
        Args:
            coin: Coin symbol
            limit: Maximum number of history items to return
            
        Returns:
            List of position history items
        """
        history = self.position_history.get(coin, [])
        return history[-limit:] if limit > 0 else history
    
    def cleanup(self):
        """Clean up resources when shutting down."""
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1.0)