# Rebate Manager module
"""
Rebate manager for optimizing trading fees through builder rebates.
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils.types import BuilderInfo


class RebateManager:
    """
    Manages builder rebates for optimizing trading costs.

    This class allows for selecting appropriate builder rebate codes
    based on market conditions, strategy type, and order characteristics.
    """

    def __init__(self,
                 exchange: Exchange,
                 info: Info,
                 default_builder: Optional[str] = None,
                 default_fee_rate: int = 1,  # 0.1 basis points (1/10th of a basis point)
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the rebate manager.

        Args:
            exchange: Hyperliquid exchange instance
            info: Hyperliquid info instance
            default_builder: Default builder address to use
            default_fee_rate: Default fee rate in tenths of basis points (e.g., 10 = 1 bp)
            logger: Optional logger instance
        """
        self.exchange = exchange
        self.info = info
        self.default_builder = default_builder
        self.default_fee_rate = default_fee_rate
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Mapping of builder addresses to their performance metrics
        self.builder_metrics: Dict[str, Dict[str, Any]] = {}

        # Approved builders that have been validated
        self.approved_builders: List[str] = []

        # Currently selected builder for orders
        self.current_builder: Optional[str] = default_builder
        self.current_fee_rate: int = default_fee_rate

    def initialize(self) -> bool:
        """
        Initialize the rebate manager by loading approved builders.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Load approved builders
            if self.default_builder:
                self.approved_builders.append(self.default_builder)
                self.logger.info(f"Using default builder: {self.default_builder}")

                # Approve the default builder if not already approved
                self._ensure_builder_approved(self.default_builder, f"0.{self.default_fee_rate / 10}%")

            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize rebate manager: {str(e)}")
            return False

    def _ensure_builder_approved(self, builder_address: str, max_fee_rate: str) -> bool:
        """
        Ensure a builder is approved for use.

        Args:
            builder_address: The builder's address
            max_fee_rate: Maximum fee rate as a percentage string (e.g., "0.001%")

        Returns:
            bool: True if builder is approved (or newly approved), False if approval failed
        """
        try:
            # Check if builder is already approved
            # Note: This is a placeholder - actual implementation would need to check
            # current approvals from the exchange

            # For demonstration, assume we need to approve it
            result = self.exchange.approve_builder_fee(builder_address, max_fee_rate)

            if result.get("status") == "ok":
                self.logger.info(f"Builder {builder_address} approved with max fee rate {max_fee_rate}")
                return True
            else:
                self.logger.error(f"Failed to approve builder {builder_address}: {result}")
                return False

        except Exception as e:
            self.logger.error(f"Error approving builder {builder_address}: {str(e)}")
            return False

    def add_builder(self, builder_address: str, max_fee_rate: str, fee_rate: int = 1) -> bool:
        """
        Add a new builder to the approved list.

        Args:
            builder_address: The builder's address
            max_fee_rate: Maximum fee rate as a percentage string (e.g., "0.001%")
            fee_rate: Fee rate to use in tenths of basis points

        Returns:
            bool: True if builder was successfully added
        """
        if self._ensure_builder_approved(builder_address, max_fee_rate):
            if builder_address not in self.approved_builders:
                self.approved_builders.append(builder_address)

            self.builder_metrics[builder_address] = {
                "fee_rate": fee_rate,
                "success_count": 0,
                "failure_count": 0,
                "total_fees_paid": 0.0,
                "last_used": None
            }
            return True
        return False

    def select_best_builder(self,
                            coin: str,
                            order_type: str,
                            is_buy: bool,
                            size: float) -> Optional[BuilderInfo]:
        """
        Select the best builder based on current market conditions and order characteristics.

        Args:
            coin: The trading pair
            order_type: Type of order (e.g., "limit", "market")
            is_buy: Whether the order is a buy (True) or sell (False)
            size: Order size

        Returns:
            Optional[BuilderInfo]: The selected builder info or None if no suitable builder
        """
        # Placeholder for more sophisticated selection logic
        # In a real implementation, this would consider:
        # - Market conditions (volatility, spread, etc.)
        # - Historical builder performance
        # - Order characteristics

        if not self.approved_builders:
            self.logger.warning("No approved builders available")
            return None

        # For now, just use the default or first approved builder
        selected_builder = self.current_builder or self.approved_builders[0]
        selected_fee = self.builder_metrics.get(selected_builder, {}).get("fee_rate", self.default_fee_rate)

        self.logger.debug(f"Selected builder {selected_builder} with fee rate {selected_fee}")

        return {
            "b": selected_builder,
            "f": selected_fee
        }

    def update_builder_metrics(self,
                               builder_address: str,
                               success: bool,
                               fees_paid: float) -> None:
        """
        Update metrics for a builder based on order execution results.

        Args:
            builder_address: The builder's address
            success: Whether the order was successful
            fees_paid: Amount of fees paid
        """
        if builder_address not in self.builder_metrics:
            self.builder_metrics[builder_address] = {
                "fee_rate": self.default_fee_rate,
                "success_count": 0,
                "failure_count": 0,
                "total_fees_paid": 0.0,
                "last_used": None
            }

        metrics = self.builder_metrics[builder_address]

        if success:
            metrics["success_count"] += 1
        else:
            metrics["failure_count"] += 1

        metrics["total_fees_paid"] += fees_paid
        metrics["last_used"] = time.time()

    def get_all_builder_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all builders.

        Returns:
            Dict mapping builder addresses to their metrics
        """
        return self.builder_metrics