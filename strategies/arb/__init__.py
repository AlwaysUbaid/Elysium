# Initialize the module
"""
Arbitrage strategy module for Elysium trading platform.

This module implements arbitrage strategies for the Elysium platform.
"""

import logging
from abc import abstractmethod
from typing import Dict, Any, Optional, List, Tuple

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from strategies import Strategy

logger = logging.getLogger(__name__)


class ArbitrageStrategy(Strategy):
    """Base class for arbitrage strategies."""

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
        Initialize arbitrage strategy.

        Args:
            name: Strategy name
            exchange: Exchange instance
            info: Info instance
            symbols: List of trading symbols
            params: Strategy parameters
            update_interval: Strategy update interval in seconds
        """
        super().__init__(
            name=name,
            exchange=exchange,
            info=info,
            symbols=symbols,
            params=params,
            update_interval=update_interval
        )

        # Arbitrage-specific state
        self.opportunities: List[Dict[str, Any]] = []
        self.executed_arbs: List[Dict[str, Any]] = []
        self.min_profit_threshold = params.get("min_profit_threshold", 0.001)  # Minimum profit (0.1%)
        self.max_position_per_pair = params.get("max_position_per_pair", 1000)  # Max position size per pair
        self.execution_delay = params.get("execution_delay", 0.1)  # Delay between leg executions (seconds)
        self.max_slippage = params.get("max_slippage", 0.0005)  # Maximum acceptable slippage (0.05%)

    @abstractmethod
    def find_opportunities(self) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities.

        Returns:
            List of arbitrage opportunities
        """
        pass

    @abstractmethod
    def execute_arbitrage(self, opportunity: Dict[str, Any]) -> bool:
        """
        Execute an arbitrage opportunity.

        Args:
            opportunity: Arbitrage opportunity details

        Returns:
            True if successfully executed, False otherwise
        """
        pass

    def update(self):
        """Update strategy state and execute trading logic."""
        try:
            # Find opportunities
            opportunities = self.find_opportunities()

            if opportunities:
                logger.info(f"Found {len(opportunities)} arbitrage opportunities")

                # Sort by expected profit
                opportunities.sort(key=lambda x: x.get("expected_profit", 0), reverse=True)

                # Execute best opportunity if above threshold
                best_opp = opportunities[0]
                if best_opp.get("expected_profit_pct", 0) >= self.min_profit_threshold:
                    logger.info(
                        f"Executing arbitrage opportunity with expected profit: {best_opp.get('expected_profit_pct', 0):.4f}%")

                    if self.execute_arbitrage(best_opp):
                        self.executed_arbs.append({
                            "time": self.last_update_time,
                            "opportunity": best_opp,
                            "success": True
                        })

                        # Update statistics
                        self.stats["total_trades"] += 1
                        profit = best_opp.get("actual_profit", best_opp.get("expected_profit", 0))
                        self.stats["total_profit_loss"] += profit

                        if profit > 0:
                            self.stats["profitable_trades"] += 1

                        if self.stats["total_trades"] > 0:
                            self.stats["win_rate"] = (self.stats["profitable_trades"] / self.stats[
                                "total_trades"]) * 100

            # Store current opportunities
            self.opportunities = opportunities

        except Exception as e:
            logger.error(f"Error in arbitrage update: {str(e)}")

    def check_balance_sufficient(self, currency: str, required_amount: float) -> bool:
        """
        Check if balance for a currency is sufficient for an arbitrage trade.

        Args:
            currency: Currency symbol
            required_amount: Required amount

        Returns:
            True if balance is sufficient, False otherwise
        """
        try:
            # For USDC or other quote currencies in spot markets
            if currency in ["USDC", "USDT", "USD"]:
                spot_state = self.info.spot_user_state(self.exchange.wallet.address)
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == currency:
                        available = float(balance.get("available", 0))
                        return available >= required_amount

            # For perpetual margins
            else:
                perp_state = self.info.user_state(self.exchange.wallet.address)
                margin_summary = perp_state.get("marginSummary", {})
                available = float(margin_summary.get("withdrawable", 0))
                return available >= required_amount

            return False

        except Exception as e:
            logger.error(f"Error checking balance for {currency}: {str(e)}")
            return False

    def calculate_arbitrage_profit(
            self,
            buy_price: float,
            sell_price: float,
            trade_size: float,
            fee_rate: float = 0.0006  # 0.06% (0.03% maker + 0.03% taker for conservative calc)
    ) -> Tuple[float, float]:
        """
        Calculate expected profit from an arbitrage opportunity.

        Args:
            buy_price: Buy price
            sell_price: Sell price
            trade_size: Trade size
            fee_rate: Trading fee rate

        Returns:
            Tuple of (profit_amount, profit_percentage)
        """
        # Calculate costs
        buy_cost = buy_price * trade_size
        sell_amount = sell_price * trade_size

        # Calculate fees
        buy_fee = buy_cost * fee_rate
        sell_fee = sell_amount * fee_rate

        # Calculate profit
        profit = sell_amount - buy_cost - buy_fee - sell_fee
        profit_percentage = (profit / buy_cost) * 100

        return profit, profit_percentage