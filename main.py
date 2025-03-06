# Main module
"""
Main entry point for the Elysium trading framework.
"""

import os
import sys
import logging
import argparse
import time
from datetime import datetime
from typing import Dict, Any, Optional

from elysium.core.logger import create_logger
from elysium.config import Config
from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor
from elysium.core.strategy_manager import StrategyManager
from elysium.rebates.rebate_manager import RebateManager
from elysium.rebates.rebate_strategies import RebateStrategy, RebateStrategySelector
from elysium.utils.helpers import setup_exchange


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Elysium Trading Framework')

    parser.add_argument('--config', type=str, default='config.json',
                        help='Path to configuration file')

    parser.add_argument('--strategy', type=str,
                        help='Strategy to run (overrides config)')

    parser.add_argument('--symbol', type=str,
                        help='Trading symbol (overrides config)')

    parser.add_argument('--testnet', action='store_true',
                        help='Use testnet instead of mainnet')

    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    parser.add_argument('--setup', action='store_true',
                        help='Create default configuration file')

    return parser.parse_args()


def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = create_logger('elysium', log_level=log_level)

    logger.info("Starting Elysium Trading Framework")

    # Initialize configuration
    config = Config(args.config, logger)

    # Create default config if requested
    if args.setup:
        config.create_default_config()
        logger.info(f"Created default configuration file: {args.config}")
        return

    # Load configuration
    if not config.load():
        logger.error("Failed to load configuration. Exiting.")
        return

    # Override configuration with command line arguments
    if args.strategy:
        config.set('strategy.name', args.strategy)

    if args.symbol:
        config.set('strategy.params.symbol', args.symbol)

    if args.testnet:
        config.set('exchange.base_url', 'https://api.hyperliquid-testnet.xyz')

    # Get API credentials
    account_address, private_key = config.get_api_credentials()

    if not account_address or not private_key:
        logger.error("Missing API credentials in configuration. Exiting.")
        return

    # Set up exchange connection
    base_url = config.get('exchange.base_url')

    try:
        # Initialize components
        address, info, exchange_client = setup_exchange(
            secret_key=private_key,
            account_address=account_address,
            base_url=base_url
        )

        # Set up exchange manager
        exchange = ExchangeManager(
            wallet=exchange_client.wallet,
            account_address=address,
            base_url=base_url,
            use_rebates=config.get('rebates.enabled', True),
            logger=create_logger('elysium.exchange', log_level=log_level)
        )

        # Set up position manager
        position_manager = PositionManager(
            exchange_manager=exchange,
            max_position_size=config.get('risk.max_position_size', {}),
            max_drawdown_pct=config.get('risk.max_drawdown_pct', 0.1),
            logger=create_logger('elysium.position', log_level=log_level)
        )

        # Set up order executor
        order_executor = OrderExecutor(
            exchange_manager=exchange,
            logger=create_logger('elysium.orders', log_level=log_level)
        )

        # Set up rebate manager if enabled
        if config.get('rebates.enabled', True):
            rebate_manager = RebateManager(
                exchange=exchange_client,
                info=info,
                default_builder=config.get('rebates.default_builder'),
                default_fee_rate=config.get('rebates.default_fee_rate', 1),
                logger=create_logger('elysium.rebates', log_level=log_level)
            )

            # Initialize rebate manager
            rebate_manager.initialize()

            # Set up rebate strategy
            rebate_strategy = RebateStrategy(config.get('rebates.strategy', 'default'))
            rebate_selector = RebateStrategySelector(
                rebate_manager=rebate_manager,
                strategy=rebate_strategy
            )

        # Set up strategy manager
        strategy_manager = StrategyManager(
            exchange_manager=exchange,
            position_manager=position_manager,
            order_executor=order_executor,
            logger=create_logger('elysium.strategy', log_level=log_level)
        )

        # Get strategy name and parameters
        strategy_name = config.get_strategy_name()
        strategy_params = config.get_strategy_params()

        if not strategy_name:
            logger.error("No strategy specified in configuration. Exiting.")
            return

        # Create strategy
        strategy = strategy_manager.create_strategy(strategy_name, strategy_params)

        if not strategy:
            logger.error(f"Failed to create strategy: {strategy_name}. Exiting.")
            return

        # Set active strategy
        strategy_manager.set_active_strategy(strategy)

        # Initialize and start strategy
        logger.info(f"Starting strategy: {strategy_name}")

        if strategy_manager.start_active_strategy():
            logger.info(f"Strategy {strategy_name} started successfully")

            # Main loop - keep running until interrupted
            try:
                while True:
                    # Periodically log status
                    status = strategy_manager.get_active_strategy_status()

                    if status:
                        runtime = status.get('runtime', '00:00:00')
                        pnl = status.get('pnl', 0.0)
                        pnl_pct = status.get('pnl_pct', 0.0)
                        trades = status.get('trades_executed', 0)

                        logger.info(
                            f"Strategy running for {runtime}, PnL: ${pnl:.2f} ({pnl_pct:.2f}%), Trades: {trades}")

                    # Sleep to avoid busy waiting
                    time.sleep(60)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping strategy...")
                strategy_manager.stop_active_strategy()
                logger.info("Strategy stopped")
        else:
            logger.error(f"Failed to start strategy: {strategy_name}")

    except Exception as e:
        logger.exception(f"Error running Elysium: {str(e)}")

    finally:
        logger.info("Exiting Elysium Trading Framework")


if __name__ == "__main__":
    main()