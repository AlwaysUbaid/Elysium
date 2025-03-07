"""
Main entry point for the Elysium trading framework.
"""

import os
import sys
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from elysium.core.logger import create_logger
from elysium.config import Config, get_config
from elysium.core.exchange import ExchangeManager
from elysium.core.position_manager import PositionManager
from elysium.core.order_executor import OrderExecutor
from elysium.core.strategy_manager import StrategyManager
from elysium.strategies import get_available_strategies, get_strategy_class


def print_header():
    """Print header banner."""
    print("\n" + "=" * 70)
    print("            Elysium Trading Bot - HyperLiquid Terminal")
    print("=" * 70)


def get_token_pairs() -> List[Dict[str, str]]:
    """
    Get available token pairs on HyperLiquid.
    
    Returns:
        List of token pairs
    """
    # These are some common pairs on HyperLiquid testnet
    return [
        {"symbol": "KOGU/USDC", "api_symbol": "KOGU/USDC", "display_name": "KOGU/USDC"},
        {"symbol": "ETH", "api_symbol": "ETH", "display_name": "ETH/USD (Perp)"},
        {"symbol": "BTC", "api_symbol": "BTC", "display_name": "BTC/USD (Perp)"},
        {"symbol": "SOL", "api_symbol": "SOL", "display_name": "SOL/USD (Perp)"},
        {"symbol": "ARB", "api_symbol": "ARB", "display_name": "ARB/USD (Perp)"}
    ]


def select_token_pair() -> Dict[str, str]:
    """
    Let user select a token pair to trade.
    
    Returns:
        Selected token pair info
    """
    token_pairs = get_token_pairs()
    
    print("\nAvailable Token Pairs:")
    print("-" * 40)
    
    for i, pair in enumerate(token_pairs, 1):
        print(f"{i}. {pair['display_name']}")
    
    choice = 0
    while choice < 1 or choice > len(token_pairs):
        try:
            choice = int(input(f"\nSelect a token pair (1-{len(token_pairs)}): "))
        except ValueError:
            print("Please enter a valid number.")
    
    return token_pairs[choice - 1]


def select_strategy() -> str:
    """
    Let user select a trading strategy.
    
    Returns:
        Selected strategy name
    """
    available_strategies = get_available_strategies()
    
    if not available_strategies:
        print("No strategies available. Using default market making strategy.")
        return "basic_market_making"
    
    print("\nAvailable Strategies:")
    print("-" * 40)
    
    strategy_display_names = {
        "basic_market_making": "Basic Market Making - Simple spread-based strategy",
        "market_order_making": "Market Order Making - Uses only market orders"
    }
    
    for i, strategy in enumerate(available_strategies, 1):
        display_name = strategy_display_names.get(strategy, strategy)
        print(f"{i}. {display_name}")
    
    choice = 0
    while choice < 1 or choice > len(available_strategies):
        try:
            choice = int(input(f"\nSelect a strategy (1-{len(available_strategies)}): "))
        except ValueError:
            print("Please enter a valid number.")
    
    return available_strategies[choice - 1]


def get_default_parameters(strategy_name: str, token_pair: Dict[str, str]) -> Dict[str, Any]:
    """
    Get default parameters for a strategy.
    
    Args:
        strategy_name: Strategy name
        token_pair: Token pair information
    
    Returns:
        Default parameters
    """
    if strategy_name == "basic_market_making":
        return {
            "symbol": token_pair["api_symbol"],
            "display_name": token_pair["display_name"],
            "max_order_size": 1000.0 if "KOGU" in token_pair["symbol"] else 0.1,
            "min_order_size": 100.0 if "KOGU" in token_pair["symbol"] else 0.01,
            "position_use_pct": 0.90,
            "initial_offset": 0.0005,  # 0.05%
            "min_offset": 0.0003,      # 0.03%
            "offset_reduction": 0.00005,
            "order_refresh_time": 15,  # seconds
            "max_active_orders": 2
        }
    
    return {}


def customize_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Let user customize strategy parameters.
    
    Args:
        params: Default parameters
    
    Returns:
        Customized parameters
    """
    print("\nStrategy Parameters:")
    print("-" * 40)
    
    for key, value in params.items():
        if key not in ["symbol", "display_name"]:  # Skip these fields in display
            if isinstance(value, float):
                print(f"{key}: {value:.6f}")
            else:
                print(f"{key}: {value}")
    
    customize = input("\nCustomize these parameters? (y/n): ").lower() == 'y'
    
    if not customize:
        return params
    
    print("\nPress Enter to keep default value, or enter a new value.")
    updated_params = params.copy()
    
    for key, value in params.items():
        if key in ["symbol", "display_name"]:  # Skip these fields
            continue
            
        if isinstance(value, float):
            try:
                new_value = input(f"{key} [{value:.6f}]: ")
                if new_value:
                    updated_params[key] = float(new_value)
            except ValueError:
                print(f"Invalid value, keeping default: {value}")
        
        elif isinstance(value, int):
            try:
                new_value = input(f"{key} [{value}]: ")
                if new_value:
                    updated_params[key] = int(new_value)
            except ValueError:
                print(f"Invalid value, keeping default: {value}")
        
        else:
            new_value = input(f"{key} [{value}]: ")
            if new_value:
                updated_params[key] = new_value
    
    return updated_params


def display_balances(exchange: ExchangeManager):
    """
    Display account balances.
    
    Args:
        exchange: Exchange manager
    """
    try:
        spot_state, perp_state = exchange.get_balances()
        
        print("\nAccount Balances:")
        print("-" * 40)
        
        # Display spot balances
        print("Spot Balances:")
        if spot_state and "balances" in spot_state:
            for balance in spot_state["balances"]:
                if float(balance.get("total", 0)) > 0:
                    print(f"  {balance.get('coin', '')}: {float(balance.get('total', 0)):.6f}")
        else:
            print("  No spot balances found.")
        
        # Display perpetual account value
        print("\nPerpetual Account:")
        if perp_state and "marginSummary" in perp_state:
            margin_summary = perp_state["marginSummary"]
            print(f"  Account Value: ${float(margin_summary.get('accountValue', 0)):.2f}")
            print(f"  Margin Used: ${float(margin_summary.get('totalMarginUsed', 0)):.2f}")
        else:
            print("  No perpetual account data found.")
            
    except Exception as e:
        print(f"Error getting balances: {str(e)}")


def main():
    """Main entry point."""
    # Print welcome header
    print_header()
    
    # Set up logging
    log_level = logging.INFO
    logger = create_logger('elysium', log_level=log_level)

    logger.info("Starting Elysium Trading Framework")

    # Initialize configuration
    config = get_config()

    # Load configuration
    if not config.load():
        logger.error("Failed to load configuration. Exiting.")
        return

    # Get API credentials
    wallet_address, private_key = config.get_api_credentials()

    # Check if credentials are missing and prompt if needed
    if not wallet_address or not private_key:
        print("\nAPI credentials are missing in configuration.")
        setup_credentials = input("Would you like to set up API credentials now? (y/n): ").lower() == 'y'
        
        if setup_credentials:
            wallet_address = input("Enter your HyperLiquid wallet address: ").strip()
            private_key = input("Enter your private key (will not be displayed): ").strip()
            
            if wallet_address and private_key:
                if config.set_api_credentials(wallet_address, private_key):
                    print("API credentials saved successfully.")
                else:
                    logger.error("Failed to save API credentials. Exiting.")
                    return
            else:
                logger.error("Invalid credentials provided. Exiting.")
                return
        else:
            logger.error("API credentials are required to continue. Exiting.")
            return

    # Set up exchange connection
    base_url = config.get('exchange.base_url')
    use_testnet = config.get('exchange.use_testnet', True)

    try:
        # Initialize components
        print("\nConnecting to exchange...")
        exchange = ExchangeManager(
            wallet_address=wallet_address,
            private_key=private_key,
            use_testnet=use_testnet,
            logger=create_logger('elysium.exchange', log_level=log_level)
        )
        
        print(f"Connected to {'Testnet' if use_testnet else 'Mainnet'} as {wallet_address}")

        # Set up position manager
        position_manager = PositionManager(
            exchange_manager=exchange,
            logger=create_logger('elysium.position', log_level=log_level)
        )

        # Set up order executor
        order_executor = OrderExecutor(
            exchange_manager=exchange,
            logger=create_logger('elysium.orders', log_level=log_level)
        )

        # Set up strategy manager
        strategy_manager = StrategyManager(
            exchange_manager=exchange,
            position_manager=position_manager,
            order_executor=order_executor,
            logger=create_logger('elysium.strategy', log_level=log_level)
        )
        
        # Display balances
        display_balances(exchange)
        
        # Interactive token selection
        token_pair = select_token_pair()
        print(f"\nSelected {token_pair['display_name']} for trading.")
        
        # Interactive strategy selection
        strategy_name = select_strategy()
        print(f"\nSelected strategy: {strategy_name}")
        
        # Get and customize parameters
        default_params = get_default_parameters(strategy_name, token_pair)
        strategy_params = customize_parameters(default_params)
        
        # Create strategy
        print("\nInitializing strategy...")
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
                print("\nStrategy is now running. Press Ctrl+C to stop.")
                print("-" * 70)
                
                while True:
                    # Display status periodically
                    status = strategy_manager.get_active_strategy_status()
                    
                    if status:
                        runtime = status.get('runtime', '00:00:00')
                        trades = status.get('trades_executed', 0)
                        
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Running: {runtime}, Trades: {trades}", end='')
                    
                    # Sleep to avoid busy waiting
                    time.sleep(5)

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

# =================================OLD Main.py=================================
# # Main module
# """
# Main entry point for the Elysium trading framework.
# """

# import os
# import sys
# import logging
# import argparse
# import time
# from datetime import datetime
# from typing import Dict, Any, Optional

# from elysium.core.logger import create_logger
# from elysium.config import Config
# from elysium.core.exchange import ExchangeManager
# from elysium.core.position_manager import PositionManager
# from elysium.core.order_executor import OrderExecutor
# from elysium.core.strategy_manager import StrategyManager
# from elysium.rebates.rebate_manager import RebateManager
# from elysium.rebates.rebate_strategies import RebateStrategy, RebateStrategySelector
# from elysium.utils.helpers import setup_exchange


# def parse_args():
#     """Parse command line arguments."""
#     parser = argparse.ArgumentParser(description='Elysium Trading Framework')

#     parser.add_argument('--config', type=str, default='config.json',
#                         help='Path to configuration file')

#     parser.add_argument('--strategy', type=str,
#                         help='Strategy to run (overrides config)')

#     parser.add_argument('--symbol', type=str,
#                         help='Trading symbol (overrides config)')

#     parser.add_argument('--testnet', action='store_true',
#                         help='Use testnet instead of mainnet')

#     parser.add_argument('--debug', action='store_true',
#                         help='Enable debug logging')

#     parser.add_argument('--setup', action='store_true',
#                         help='Create default configuration file')

#     return parser.parse_args()


# def main():
#     """Main entry point."""
#     # Parse command line arguments
#     args = parse_args()

#     # Set up logging
#     log_level = logging.DEBUG if args.debug else logging.INFO
#     logger = create_logger('elysium', log_level=log_level)

#     logger.info("Starting Elysium Trading Framework")

#     # Initialize configuration
#     config = Config(args.config, logger)

#     # Create default config if requested
#     if args.setup:
#         config.create_default_config()
#         logger.info(f"Created default configuration file: {args.config}")
#         return

#     # Load configuration
#     if not config.load():
#         logger.error("Failed to load configuration. Exiting.")
#         return

#     # Override configuration with command line arguments
#     if args.strategy:
#         config.set('strategy.name', args.strategy)

#     if args.symbol:
#         config.set('strategy.params.symbol', args.symbol)

#     if args.testnet:
#         config.set('exchange.base_url', 'https://api.hyperliquid-testnet.xyz')

#     # Get API credentials
#     account_address, private_key = config.get_api_credentials()

#     if not account_address or not private_key:
#         logger.error("Missing API credentials in configuration. Exiting.")
#         return

#     # Set up exchange connection
#     base_url = config.get('exchange.base_url')

#     try:
#         # Initialize components
#         address, info, exchange_client = setup_exchange(
#             secret_key=private_key,
#             account_address=account_address,
#             base_url=base_url
#         )

#         # Set up exchange manager
#         exchange = ExchangeManager(
#             wallet=exchange_client.wallet,
#             account_address=address,
#             base_url=base_url,
#             use_rebates=config.get('rebates.enabled', True),
#             logger=create_logger('elysium.exchange', log_level=log_level)
#         )

#         # Set up position manager
#         position_manager = PositionManager(
#             exchange_manager=exchange,
#             max_position_size=config.get('risk.max_position_size', {}),
#             max_drawdown_pct=config.get('risk.max_drawdown_pct', 0.1),
#             logger=create_logger('elysium.position', log_level=log_level)
#         )

#         # Set up order executor
#         order_executor = OrderExecutor(
#             exchange_manager=exchange,
#             logger=create_logger('elysium.orders', log_level=log_level)
#         )

#         # Set up rebate manager if enabled
#         if config.get('rebates.enabled', True):
#             rebate_manager = RebateManager(
#                 exchange=exchange_client,
#                 info=info,
#                 default_builder=config.get('rebates.default_builder'),
#                 default_fee_rate=config.get('rebates.default_fee_rate', 1),
#                 logger=create_logger('elysium.rebates', log_level=log_level)
#             )

#             # Initialize rebate manager
#             rebate_manager.initialize()

#             # Set up rebate strategy
#             rebate_strategy = RebateStrategy(config.get('rebates.strategy', 'default'))
#             rebate_selector = RebateStrategySelector(
#                 rebate_manager=rebate_manager,
#                 strategy=rebate_strategy
#             )

#         # Set up strategy manager
#         strategy_manager = StrategyManager(
#             exchange_manager=exchange,
#             position_manager=position_manager,
#             order_executor=order_executor,
#             logger=create_logger('elysium.strategy', log_level=log_level)
#         )

#         # Get strategy name and parameters
#         strategy_name = config.get_strategy_name()
#         strategy_params = config.get_strategy_params()

#         if not strategy_name:
#             logger.error("No strategy specified in configuration. Exiting.")
#             return

#         # Create strategy
#         strategy = strategy_manager.create_strategy(strategy_name, strategy_params)

#         if not strategy:
#             logger.error(f"Failed to create strategy: {strategy_name}. Exiting.")
#             return

#         # Set active strategy
#         strategy_manager.set_active_strategy(strategy)

#         # Initialize and start strategy
#         logger.info(f"Starting strategy: {strategy_name}")

#         if strategy_manager.start_active_strategy():
#             logger.info(f"Strategy {strategy_name} started successfully")

#             # Main loop - keep running until interrupted
#             try:
#                 while True:
#                     # Periodically log status
#                     status = strategy_manager.get_active_strategy_status()

#                     if status:
#                         runtime = status.get('runtime', '00:00:00')
#                         pnl = status.get('pnl', 0.0)
#                         pnl_pct = status.get('pnl_pct', 0.0)
#                         trades = status.get('trades_executed', 0)

#                         logger.info(
#                             f"Strategy running for {runtime}, PnL: ${pnl:.2f} ({pnl_pct:.2f}%), Trades: {trades}")

#                     # Sleep to avoid busy waiting
#                     time.sleep(60)

#             except KeyboardInterrupt:
#                 logger.info("Keyboard interrupt received, stopping strategy...")
#                 strategy_manager.stop_active_strategy()
#                 logger.info("Strategy stopped")
#         else:
#             logger.error(f"Failed to start strategy: {strategy_name}")

#     except Exception as e:
#         logger.exception(f"Error running Elysium: {str(e)}")

#     finally:
#         logger.info("Exiting Elysium Trading Framework")


# if __name__ == "__main__":
#     main()
