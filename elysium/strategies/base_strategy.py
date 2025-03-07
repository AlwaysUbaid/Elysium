# Base Strategy module
"""
Base strategy class defining the interface for all trading strategies.
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    """

    def __init__(self,
                 config: Dict[str, Any],
                 exchange: ExchangeManager,
                 position_manager: PositionManager,
                 order_executor: OrderExecutor,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the base strategy.

        Args:
            config: Configuration parameters for the strategy
            exchange: Exchange manager for API interactions
            position_manager: Position manager for tracking positions
            order_executor: Order executor for placing orders
            logger: Optional logger instance
        """
        self.config = config
        self.exchange = exchange
        self.position_manager = position_manager
        self.order_executor = order_executor
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Strategy state
        self.running = False
        self.should_stop = False
        self.last_tick_time = 0
        self.start_time = None
        self.thread = None

        # Performance tracking
        self.trades_executed = 0
        self.pnl = 0.0
        self.initial_portfolio_value = 0.0
        self.current_portfolio_value = 0.0

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the strategy. Should be called once before start.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        pass

    @abstractmethod
    def on_tick(self) -> None:
        """Process a tick/update of market data."""
        pass

    @abstractmethod
    def on_fill(self, fill_data: Dict[str, Any]) -> None:
        """Process a fill event."""
        pass

    @abstractmethod
    def on_order_update(self, order_data: Dict[str, Any]) -> None:
        """Process an order update event."""
        pass

    def start(self) -> None:
        """Start the strategy."""
        if self.running:
            self.logger.warning(f"Strategy {self.__class__.__name__} is already running")
            return

        self.running = True
        self.should_stop = False
        self.start_time = datetime.now()

        # Get initial portfolio value
        self.initial_portfolio_value = self.position_manager.get_account_value()
        self.current_portfolio_value = self.initial_portfolio_value

        # Start the strategy thread
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()

        self.logger.info(f"Strategy {self.__class__.__name__} started")

    def stop(self) -> None:
        """Stop the strategy."""
        if not self.running:
            self.logger.warning(f"Strategy {self.__class__.__name__} is not running")
            return

        self.should_stop = True
        self.logger.info(f"Stopping strategy {self.__class__.__name__}...")

        # Wait for the thread to complete
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=30)

        self.running = False
        self.logger.info(f"Strategy {self.__class__.__name__} stopped")

    def _run_loop(self) -> None:
        """Main strategy loop."""
        while self.running and not self.should_stop:
            try:
                # Process any updates
                self.order_executor.process_updates()

                # Call on_tick at the strategy's tick interval
                current_time = time.time()
                tick_interval = self.config.get("tick_interval", 1.0)

                if current_time - self.last_tick_time >= tick_interval:
                    self.on_tick()
                    self.last_tick_time = current_time

                    # Update portfolio value
                    self.current_portfolio_value = self.position_manager.get_account_value()

                # Prevent CPU spinning
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in strategy loop: {str(e)}")
                time.sleep(5)  # Sleep longer on error

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the strategy.

        Returns:
            Dict with status information
        """
        runtime = None
        if self.start_time:
            runtime = str(datetime.now() - self.start_time).split('.')[0]  # Format as HH:MM:SS

        return {
            "name": self.__class__.__name__,
            "running": self.running,
            "start_time": self.start_time,
            "runtime": runtime,
            "trades_executed": self.trades_executed,
            "initial_portfolio_value": self.initial_portfolio_value,
            "current_portfolio_value": self.current_portfolio_value,
            "pnl": self.current_portfolio_value - self.initial_portfolio_value,
            "pnl_pct": (
                                   self.current_portfolio_value / self.initial_portfolio_value - 1) * 100 if self.initial_portfolio_value > 0 else 0
        }

    def _calculate_portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        return self.position_manager.get_account_value()