# Rebate Strategies module
"""
Implementation of different rebate strategies for selecting builder rebates.
"""

from enum import Enum
from typing import Dict, Any, Optional

from hyperliquid.utils.types import BuilderInfo
from elysium.rebates.rebate_manager import RebateManager


class RebateStrategy(Enum):
    """Strategies for applying builder rebates."""

    # Always use the default builder
    DEFAULT = "default"

    # Round-robin between approved builders
    ROUND_ROBIN = "round_robin"

    # Select based on historical performance
    PERFORMANCE_BASED = "performance_based"

    # Select based on market conditions
    MARKET_ADAPTIVE = "market_adaptive"

    # No rebate applied
    NONE = "none"


class RebateStrategySelector:
    """
    Selects and applies rebate strategies based on configuration.
    """

    def __init__(self,
                 rebate_manager: RebateManager,
                 strategy: RebateStrategy = RebateStrategy.DEFAULT):
        """
        Initialize the rebate strategy selector.

        Args:
            rebate_manager: RebateManager instance
            strategy: Strategy to use for rebate selection
        """
        self.rebate_manager = rebate_manager
        self.strategy = strategy
        self.current_index = 0  # For round-robin strategy

    def get_builder_info(self,
                         coin: str,
                         order_type: str,
                         is_buy: bool,
                         size: float) -> Optional[BuilderInfo]:
        """
        Get builder info based on the selected strategy.

        Args:
            coin: The trading pair
            order_type: Type of order (e.g., "limit", "market")
            is_buy: Whether the order is a buy (True) or sell (False)
            size: Order size

        Returns:
            Optional[BuilderInfo]: Selected builder info or None
        """
        if self.strategy == RebateStrategy.NONE:
            return None

        if self.strategy == RebateStrategy.DEFAULT:
            # Use default builder from rebate manager
            if self.rebate_manager.default_builder:
                return {
                    "b": self.rebate_manager.default_builder,
                    "f": self.rebate_manager.default_fee_rate
                }
            return None

        if self.strategy == RebateStrategy.ROUND_ROBIN:
            return self._round_robin_select()

        if self.strategy == RebateStrategy.PERFORMANCE_BASED:
            return self._performance_based_select()

        if self.strategy == RebateStrategy.MARKET_ADAPTIVE:
            return self.rebate_manager.select_best_builder(coin, order_type, is_buy, size)

        # Default fallback
        return None

    def _round_robin_select(self) -> Optional[BuilderInfo]:
        """
        Select builders in a round-robin fashion.

        Returns:
            Optional[BuilderInfo]: Selected builder info or None
        """
        builders = self.rebate_manager.approved_builders

        if not builders:
            return None

        if self.current_index >= len(builders):
            self.current_index = 0

        selected = builders[self.current_index]
        fee_rate = self.rebate_manager.builder_metrics.get(selected, {}).get(
            "fee_rate", self.rebate_manager.default_fee_rate)

        # Increment for next selection
        self.current_index += 1

        return {
            "b": selected,
            "f": fee_rate
        }

    def _performance_based_select(self) -> Optional[BuilderInfo]:
        """
        Select builder based on historical performance.

        Returns:
            Optional[BuilderInfo]: Selected builder info or None
        """
        metrics = self.rebate_manager.get_all_builder_metrics()

        if not metrics:
            return None

        # Find builder with highest success rate
        best_builder = None
        best_success_rate = -1

        for address, data in metrics.items():
            total = data["success_count"] + data["failure_count"]
            if total > 0:
                success_rate = data["success_count"] / total
                if success_rate > best_success_rate:
                    best_success_rate = success_rate
                    best_builder = address

        if best_builder:
            return {
                "b": best_builder,
                "f": metrics[best_builder]["fee_rate"]
            }

        # If no statistics yet, use first builder
        if self.rebate_manager.approved_builders:
            first = self.rebate_manager.approved_builders[0]
            return {
                "b": first,
                "f": self.rebate_manager.default_fee_rate
            }

        return None