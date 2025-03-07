# Initialize the module
"""
Elysium Trading Framework

A modular, high-performance trading framework built on the Hyperliquid Python SDK
that enables sophisticated trading strategies with builder rebate optimization.
"""

__version__ = "0.1.0"
__author__ = "Elysium Team"
__email__ = "contact@elysium.xyz"
__license__ = "MIT"

from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor
from elysium.core.strategy_manager import StrategyManager
from elysium.strategies.base_strategy import BaseStrategy
from elysium.rebates.rebate_manager import RebateManager
from elysium.rebates.rebate_strategies import RebateStrategy, RebateStrategySelector