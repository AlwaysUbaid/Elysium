# Position Manager module
"""
Position manager for tracking and managing trading positions.
Includes risk management and position sizing functionality.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from elysium.core.exchange import ExchangeManager


class PositionManager:
    """
    Manages positions and provides risk management functionality.
    """

    def __init__(self,
                 exchange_manager: ExchangeManager,
                 max_position_size: Dict[str, float] = None,
                 max_drawdown_pct: float = 0.1,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the position manager.

        Args:
            exchange_manager: ExchangeManager instance
            max_position_size: Maximum position size by coin {"ETH": 5.0, ...}
            max_drawdown_pct: Maximum allowed drawdown as percentage (0.1 = 10%)
            logger: Optional logger instance
        """
        self.exchange = exchange_manager
        self.max_position_size = max_position_size or {}
        self.max_drawdown_pct = max_drawdown_pct
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Track position state
        self.positions = {}
        self.position_history = {}
        self.initial_account_value = 0
        self.last_account_value = 0

        # Initialize positions
        self.refresh_positions()

    def refresh_positions(self) -> Dict[str, Any]:
        """
        Refresh position data from the exchange.

        Returns:
            Current positions
        """
        try:
            # Get perpetual positions
            user_state = self.exchange.info.user_state(self.exchange.account_address)

            # Update account value tracking
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))

            if self.initial_account_value == 0:
                self.initial_account_value = account_value

            self.last_account_value = account_value

            # Process positions
            positions = {}
            for asset_position in user_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                if float(position.get("szi", 0)) != 0:
                    coin = position.get("coin", "")
                    positions[coin] = {
                        "size": float(position.get("szi", 0)),
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0)),
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0)),
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
        # First refresh to ensure we have latest data
        self.refresh_positions()
        return self.positions.get(coin, {})

    def get_drawdown(self) -> float:
        """
        Calculate current drawdown percentage.

        Returns:
            Current drawdown as a percentage (0.05 = 5%)
        """
        if self.initial_account_value == 0:
            return 0

        return max(0, (self.initial_account_value - self.last_account_value) / self.initial_account_value)

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

    def calculate_optimal_position_size(self,
                                        coin: str,
                                        risk_per_trade: float = 0.01) -> float:
        """
        Calculate optimal position size based on risk parameters.

        Args:
            coin: Coin to calculate for
            risk_per_trade: Percentage of account to risk per trade (0.01 = 1%)

        Returns:
            Optimal position size
        """
        # Get latest account value
        self.refresh_positions()
        account_value = self.last_account_value

        # Get current price
        try:
            mid_price = float(self.exchange.info.all_mids().get(coin, 0))
            if mid_price == 0:
                self.logger.warning(f"Could not get price for {coin}")
                return 0
        except Exception as e:
            self.logger.error(f"Error getting price for {coin}: {str(e)}")
            return 0

        # Calculate position size based on risk
        risk_amount = account_value * risk_per_trade

        # Simple calculation assuming 1% move would trigger stop loss
        position_value = risk_amount / 0.01
        position_size = position_value / mid_price

        # Apply maximum position limit if set
        max_size = self.max_position_size.get(coin, float('inf'))
        position_size = min(position_size, max_size)

        return position_size