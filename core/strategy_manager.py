"""
Strategy manager for loading, configuring and executing trading strategies.
"""

import logging
import importlib
import inspect
from typing import Dict, Any, List, Optional, Type

from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor
from elysium.strategies.base_strategy import BaseStrategy


class StrategyManager:
    """
    Manages the creation, configuration and execution of trading strategies.
    """

    def __init__(self,
                 exchange_manager: ExchangeManager,
                 position_manager: PositionManager,
                 order_executor: OrderExecutor,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the strategy manager.

        Args:
            exchange_manager: ExchangeManager instance
            position_manager: PositionManager instance
            order_executor: OrderExecutor instance
            logger: Optional logger instance
        """
        self.exchange = exchange_manager
        self.position_manager = position_manager
        self.order_executor = order_executor
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Track available and active strategies
        self.available_strategies: Dict[str, Type[BaseStrategy]] = {}
        self.active_strategy: Optional[BaseStrategy] = None

        # Discover available strategies
        self._discover_strategies()

    def _discover_strategies(self):
        """
        Discover available strategy implementations by scanning the strategies package.
        """
        try:
            # Import core strategy module
            import elysium.strategies as strategies_pkg

            # Look for strategies in the market_making package
            try:
                import elysium.strategies.market_making as mm_pkg
                self._register_strategies_from_module(mm_pkg)
            except ImportError:
                self.logger.warning("Market making strategies package not found")

            # Look for strategies in the arb package
            try:
                import elysium.strategies.arb as arb_pkg
                self._register_strategies_from_module(arb_pkg)
            except ImportError:
                self.logger.warning("Arbitrage strategies package not found")

            # Look for strategies in the trend_following package
            try:
                import elysium.strategies.trend_following as tf_pkg
                self._register_strategies_from_module(tf_pkg)
            except ImportError:
                self.logger.warning("Trend following strategies package not found")

            self.logger.info(
                f"Discovered {len(self.available_strategies)} strategies: {list(self.available_strategies.keys())}")

        except ImportError as e:
            self.logger.error(f"Error discovering strategies: {str(e)}")

    def _register_strategies_from_module(self, module):
        """
        Register strategies from a module.

        Args:
            module: Module to scan for strategy classes
        """
        for name, obj in inspect.getmembers(module):
            # Check if it's a class and a subclass of BaseStrategy
            if (inspect.isclass(obj) and
                    issubclass(obj, BaseStrategy) and
                    obj != BaseStrategy):
                strategy_name = name.lower()
                self.available_strategies[strategy_name] = obj
                self.logger.debug(f"Registered strategy: {strategy_name}")

    def get_available_strategies(self) -> List[str]:
        """
        Get list of available strategy names.

        Returns:
            List of strategy names
        """
        return list(self.available_strategies.keys())

    def create_strategy(self, strategy_name: str, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """
        Create a strategy instance.

        Args:
            strategy_name: Name of the strategy to create
            config: Configuration parameters for the strategy

        Returns:
            Strategy instance or None if strategy not found
        """
        strategy_name = strategy_name.lower()

        if strategy_name not in self.available_strategies:
            self.logger.error(f"Strategy '{strategy_name}' not found")
            return None

        try:
            # Create the strategy instance
            strategy_class = self.available_strategies[strategy_name]
            strategy = strategy_class(
                config=config,
                exchange=self.exchange,
                position_manager=self.position_manager,
                order_executor=self.order_executor,
                logger=self.logger
            )

            self.logger.info(f"Created strategy: {strategy_name}")
            return strategy

        except Exception as e:
            self.logger.error(f"Error creating strategy '{strategy_name}': {str(e)}")
            return None

    def set_active_strategy(self, strategy: BaseStrategy) -> bool:
        """
        Set the active strategy.

        Args:
            strategy: Strategy instance

        Returns:
            True if successful, False otherwise
        """
        # Stop current strategy if exists
        if self.active_strategy is not None:
            self.stop_active_strategy()

        self.active_strategy = strategy
        self.logger.info(f"Set active strategy: {strategy.__class__.__name__}")
        return True

    def start_active_strategy(self) -> bool:
        """
        Start the active strategy.

        Returns:
            True if started successfully, False otherwise
        """
        if self.active_strategy is None:
            self.logger.error("No active strategy to start")
            return False

        try:
            # Initialize and start the strategy
            if self.active_strategy.initialize():
                self.active_strategy.start()
                self.logger.info(f"Started strategy: {self.active_strategy.__class__.__name__}")
                return True
            else:
                self.logger.error(f"Failed to initialize strategy: {self.active_strategy.__class__.__name__}")
                return False

        except Exception as e:
            self.logger.error(f"Error starting strategy: {str(e)}")
            return False

    def stop_active_strategy(self) -> bool:
        """
        Stop the active strategy.

        Returns:
            True if stopped successfully, False otherwise
        """
        if self.active_strategy is None:
            self.logger.warning("No active strategy to stop")
            return False

        try:
            self.active_strategy.stop()
            self.logger.info(f"Stopped strategy: {self.active_strategy.__class__.__name__}")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping strategy: {str(e)}")
            return False

    def get_active_strategy_status(self) -> Dict[str, Any]:
        """
        Get status of the active strategy.

        Returns:
            Status information or empty dict if no active strategy
        """
        if self.active_strategy is None:
            return {}

        return self.active_strategy.get_status()