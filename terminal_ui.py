import cmd
import os
import time
import threading
import logging
import json
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

class ElysiumTerminalUI(cmd.Cmd):
    """Command-line interface for Elysium Trading Platform"""
    
    VERSION = "1.0.0"
    intro = None

    ASCII_ART = '''
    ███████╗██╗  ██╗   ██╗███████╗██╗██╗   ██╗███╗   ███╗
    ██╔════╝██║  ╚██╗ ██╔╝██╔════╝██║██║   ██║████╗ ████║
    █████╗  ██║   ╚████╔╝ ███████╗██║██║   ██║██╔████╔██║
    ██╔══╝  ██║    ╚██╔╝  ╚════██║██║██║   ██║██║╚██╔╝██║
    ███████╗███████╗██║   ███████║██║╚██████╔╝██║ ╚═╝ ██║
    ╚══════╝╚══════╝╚═╝   ╚══════╝╚═╝ ╚═════╝ ╚═╝     ╚═╝
    ===========================================================
    '''
# Updated WELCOME_MSG variable for ElysiumTerminalUI class in terminal_ui.py

    WELCOME_MSG = '''
    Welcome to Elysium Trading Bot
    Type 'help' to see available commands

    Useful Commands:
    - connect     Connect to exchange
                "connect mainnet" or "connect testnet"
    - balance     See your exchange balances
    - positions   Show your open positions

    Spot Trading:
    - buy         Execute a market buy
    - sell        Execute a market sell
    - limit_buy   Place a limit buy order
    - limit_sell  Place a limit sell order

    Perpetual Trading:
    - perp_buy        Execute a perpetual market buy
    - perp_sell       Execute a perpetual market sell
    - perp_limit_buy  Place a perpetual limit buy order
    - perp_limit_sell Place a perpetual limit sell order
    - close_position  Close an entire perpetual position
    - set_leverage    Set leverage for a symbol

    Strategy Trading:
    - select_strategy  Select and configure a trading strategy
    - strategy_status  Check the status of the current strategy
    - stop_strategy    Stop the currently running strategy
    - strategy_params  View parameters of a strategy
    - help_strategies  Show help for trading strategies


    Advanced Order Strategies:
    - scaled_buy          Place multiple buy orders across a price range
    - scaled_sell         Place multiple sell orders across a price range
    - market_scaled_buy   Place multiple buy orders based on current market prices
    - market_scaled_sell  Place multiple sell orders based on current market prices
    - perp_scaled_buy     Place multiple perpetual buy orders across a price range
    - perp_scaled_sell    Place multiple perpetual sell orders across a price range
    - help_scaled         Show detailed help for scaled orders
    - help_market_scaled  Show detailed help for market-aware scaled orders

    Grid Trading:
    - grid_create     Create a new grid trading strategy
    - grid_start      Start a grid trading strategy
    - grid_stop       Stop a grid trading strategy
    - grid_status     Check status of a grid trading strategy
    - grid_list       List all grid trading strategies
    - grid_stop_all   Stop all active grid trading strategies
    - grid_clean      Clean up completed grid trading strategies
    - grid_modify     Modify parameters of a grid trading strategy
    - help_grid       Show detailed help for grid trading

    TWAP Strategy:
    - twap_create     Create a new TWAP execution
    - twap_start      Start a TWAP execution
    - twap_stop       Stop a TWAP execution
    - twap_status     Check status of a TWAP execution
    - twap_list       List all TWAP executions
    - twap_stop_all   Stop all active TWAP executions
    - twap_clean      Clean up completed TWAP executions

    Order Management:
    - cancel      Cancel specific order
    - cancel_all  Cancel all open orders
    - orders      List open orders
    - help        List all commands
    '''


    def __init__(self, api_connector, order_handler, config_manager):
        super().__init__()
        self.prompt = '>>> '
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.authenticated = False
        self.last_command_output = ""

        # Initialize strategy selector
        from strategy_selector import StrategySelector
        self.strategy_selector = StrategySelector(api_connector, order_handler, config_manager)
        
    def preloop(self):
        """Setup before starting the command loop"""
        self.display_layout()
        
        # Authenticate user before proceeding
        auth_success = self.authenticate_user()
        if not auth_success:
            print("\nAuthentication failed. Exiting...")
            import sys
            sys.exit(1)
        
        self.authenticated = True
        print("\nAuthentication successful!")
        print("Initializing Elysium CLI...")
        time.sleep(1)
        print("Ready to trade!\n")
        
    def authenticate_user(self) -> bool:
        """Authenticate user with password"""
        # Password is already stored in config
        if self.config_manager.get('password_hash'):
            for attempt in range(3):  # Allow 3 attempts
                password = input("Enter your password: ")
                if self.config_manager.verify_password(password):
                    return True
                else:
                    print(f"Incorrect password. {2-attempt} attempts remaining.")
            return False
        else:
            # First-time setup
            print("First-time setup. Please create a password:")
            password = input("Enter new password: ")
            confirm = input("Confirm password: ")
            
            if password == confirm:
                self.config_manager.set_password(password)
                return True
            else:
                print("Passwords don't match.")
                return False
    
    def display_layout(self):
        """Display the interface layout"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(self.ASCII_ART)
        print(self.WELCOME_MSG)
        
    def do_connect(self, arg):
        """
        Connect to Hyperliquid exchange
        Usage: connect [mainnet|testnet]
        Options:
            mainnet    Connect to mainnet (default)
            testnet    Connect to testnet
        """
        try:
            # Parse network type from arguments
            arg_lower = arg.lower()
            if "testnet" in arg_lower:
                use_testnet = True
                network_name = "testnet"
            else:
                # Default to mainnet
                use_testnet = False
                network_name = "mainnet"
            
            # Import credentials from dontshareconfig.py
            import dontshareconfig as ds
            
            # Select the appropriate credentials based on network
            if use_testnet:
                wallet_address = ds.testnet_wallet
                secret_key = ds.testnet_secret
            else:
                wallet_address = ds.mainnet_wallet
                secret_key = ds.mainnet_secret
            
            print(f"\nConnecting to Hyperliquid ({network_name})...")
            success = self.api_connector.connect_hyperliquid(wallet_address, secret_key, use_testnet)
            
            if success:
                print(f"Successfully connected to {wallet_address}")
                # Initialize order handler with the connected exchange and info objects
                self.order_handler.exchange = self.api_connector.exchange
                self.order_handler.info = self.api_connector.info
                self.order_handler.wallet_address = wallet_address
            else:
                print("Failed to connect to exchange")
                    
        except Exception as e:
            print(f"Error connecting to exchange: {str(e)}")
    
    def do_balance(self, arg):
        """
        Show current balance across spot and perpetual markets
        Usage: balance
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            print("\n=== Current Balances ===")
            
            # Display spot balances
            print("\nSpot Balances:")
            spot_state = self.api_connector.info.spot_user_state(self.api_connector.wallet_address)
            
            headers = ["Asset", "Available", "Total", "In Orders"]
            rows = []
            
            for balance in spot_state.get("balances", []):
                rows.append([
                    balance.get("coin", ""),
                    float(balance.get("available", 0)),
                    float(balance.get("total", 0)),
                    float(balance.get("total", 0)) - float(balance.get("available", 0))
                ])
            
            self._print_table(headers, rows)
            
            # Display perpetual balance
            print("\nPerpetual Account Summary:")
            perp_state = self.api_connector.info.user_state(self.api_connector.wallet_address)
            margin_summary = perp_state.get("marginSummary", {})
            
            headers = ["Metric", "Value"]
            rows = [
                ["Account Value", f"${float(margin_summary.get('accountValue', 0)):.2f}"],
                ["Total Margin Used", f"${float(margin_summary.get('totalMarginUsed', 0)):.2f}"],
                ["Total Position Value", f"${float(margin_summary.get('totalNtlPos', 0)):.2f}"]
            ]
            
            self._print_table(headers, rows)
            
        except Exception as e:
            print(f"\nError fetching balances: {str(e)}")
    
    def do_buy(self, arg):
        """
        Execute a market buy order
        Usage: buy <symbol> <size> [slippage]
        Example: buy ETH 0.1 0.05
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: buy <symbol> <size> [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            slippage = float(args[2]) if len(args) > 2 else 0.05
            
            print(f"\nExecuting market buy: {size} {symbol} (slippage: {slippage*100}%)")
            result = self.order_handler.market_buy(symbol, size, slippage)
            
            if result["status"] == "ok":
                print("Market buy order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Market buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing market buy: {str(e)}")
    
    def do_sell(self, arg):
        """
        Execute a market sell order
        Usage: sell <symbol> <size> [slippage]
        Example: sell ETH 0.1 0.05
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: sell <symbol> <size> [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            slippage = float(args[2]) if len(args) > 2 else 0.05
            
            print(f"\nExecuting market sell: {size} {symbol} (slippage: {slippage*100}%)")
            result = self.order_handler.market_sell(symbol, size, slippage)
            
            if result["status"] == "ok":
                print("Market sell order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Market sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing market sell: {str(e)}")
    
    def do_limit_buy(self, arg):
        """
        Place a limit buy order
        Usage: limit_buy <symbol> <size> <price>
        Example: limit_buy ETH 0.1 3000
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: limit_buy <symbol> <size> <price>")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            
            print(f"\nPlacing limit buy order: {size} {symbol} @ {price}")
            result = self.order_handler.limit_buy(symbol, size, price)
            
            if result["status"] == "ok":
                print("Limit buy order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Limit buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing limit buy order: {str(e)}")
    
    def do_limit_sell(self, arg):
        """
        Place a limit sell order
        Usage: limit_sell <symbol> <size> <price>
        Example: limit_sell ETH 0.1 3500
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: limit_sell <symbol> <size> <price>")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            
            print(f"\nPlacing limit sell order: {size} {symbol} @ {price}")
            result = self.order_handler.limit_sell(symbol, size, price)
            
            if result["status"] == "ok":
                print("Limit sell order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Limit sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing limit sell order: {str(e)}")

    # =================================Perp Trading==============================================

    def do_perp_buy(self, arg):
        """
        Execute a perpetual market buy order
        Usage: perp_buy <symbol> <size> [leverage] [slippage]
        Example: perp_buy BTC 0.01 5 0.03
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: perp_buy <symbol> <size> [leverage] [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            leverage = int(args[2]) if len(args) > 2 else 1
            slippage = float(args[3]) if len(args) > 3 else 0.05
            
            print(f"\nExecuting perp market buy: {size} {symbol} with {leverage}x leverage (slippage: {slippage*100}%)")
            result = self.order_handler.perp_market_buy(symbol, size, leverage, slippage)
            
            if result["status"] == "ok":
                print("Perpetual market buy order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Perpetual market buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing perpetual market buy: {str(e)}")

    def do_perp_sell(self, arg):
        """
        Execute a perpetual market sell order
        Usage: perp_sell <symbol> <size> [leverage] [slippage]
        Example: perp_sell BTC 0.01 5 0.03
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: perp_sell <symbol> <size> [leverage] [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            leverage = int(args[2]) if len(args) > 2 else 1
            slippage = float(args[3]) if len(args) > 3 else 0.05
            
            print(f"\nExecuting perp market sell: {size} {symbol} with {leverage}x leverage (slippage: {slippage*100}%)")
            result = self.order_handler.perp_market_sell(symbol, size, leverage, slippage)
            
            if result["status"] == "ok":
                print("Perpetual market sell order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Perpetual market sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing perpetual market sell: {str(e)}")

    def do_perp_limit_buy(self, arg):
        """
        Place a perpetual limit buy order
        Usage: perp_limit_buy <symbol> <size> <price> [leverage]
        Example: perp_limit_buy BTC 0.01 50000 5
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: perp_limit_buy <symbol> <size> <price> [leverage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            leverage = int(args[3]) if len(args) > 3 else 1
            
            print(f"\nPlacing perp limit buy order: {size} {symbol} @ {price} with {leverage}x leverage")
            result = self.order_handler.perp_limit_buy(symbol, size, price, leverage)
            
            if result["status"] == "ok":
                print("Perpetual limit buy order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Perpetual limit buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing perpetual limit buy order: {str(e)}")

    def do_perp_limit_sell(self, arg):
        """
        Place a perpetual limit sell order
        Usage: perp_limit_sell <symbol> <size> <price> [leverage]
        Example: perp_limit_sell BTC 0.01 60000 5
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: perp_limit_sell <symbol> <size> <price> [leverage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            leverage = int(args[3]) if len(args) > 3 else 1
            
            print(f"\nPlacing perp limit sell order: {size} {symbol} @ {price} with {leverage}x leverage")
            result = self.order_handler.perp_limit_sell(symbol, size, price, leverage)
            
            if result["status"] == "ok":
                print("Perpetual limit sell order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Perpetual limit sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing perpetual limit sell order: {str(e)}")
# ===================Close Position============================
    def do_close_position(self, arg):
        """
        Close an entire perpetual position
        Usage: close_position <symbol> [slippage]
        Example: close_position BTC 0.03
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 1:
                print("Invalid arguments. Usage: close_position <symbol> [slippage]")
                return
                
            symbol = args[0]
            slippage = float(args[1]) if len(args) > 1 else 0.05
            
            print(f"\nClosing position for {symbol} (slippage: {slippage*100}%)")
            result = self.order_handler.close_position(symbol, slippage)
            
            if result["status"] == "ok":
                print("Position closed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Position close failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError closing position: {str(e)}")

# ============================ Leverage Setting ===============================

    def do_set_leverage(self, arg):
        """
        Set leverage for a symbol
        Usage: set_leverage <symbol> <leverage>
        Example: set_leverage BTC 5
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: set_leverage <symbol> <leverage>")
                return
                
            symbol = args[0]
            leverage = int(args[1])
            
            print(f"\nSetting {leverage}x leverage for {symbol}")
            result = self.order_handler._set_leverage(symbol, leverage)
            
            if result["status"] == "ok":
                print(f"Leverage for {symbol} set to {leverage}x")
            else:
                print(f"Failed to set leverage: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError setting leverage: {str(e)}")

    # ================================ Scaled Order Part =====================================
    def do_scaled_buy(self, arg):
        """
        Place multiple buy orders across a price range (scaled orders)
        Usage: scaled_buy <symbol> <total_size> <num_orders> <start_price> <end_price> [skew]
        Example: scaled_buy ETH 0.5 5 3200 3000 0
        
        Start price should be higher than end price for buy orders.
        Skew value (optional): 0 = linear distribution, >0 = more weight to higher prices
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 5:
                print("Invalid arguments. Usage: scaled_buy <symbol> <total_size> <num_orders> <start_price> <end_price> [skew]")
                return
                
            symbol = args[0]
            total_size = float(args[1])
            num_orders = int(args[2])
            start_price = float(args[3])
            end_price = float(args[4])
            skew = float(args[5]) if len(args) > 5 else 0
            
            # Validate price direction
            if start_price < end_price:
                print("Warning: For buy orders, start_price should be higher than end_price. Swapping values.")
                start_price, end_price = end_price, start_price
            
            print(f"\nPlacing {num_orders} scaled buy orders for {symbol}:")
            print(f"Total size: {total_size}")
            print(f"Price range: {start_price} to {end_price}")
            print(f"Skew: {skew}")
            
            result = self.order_handler.scaled_orders(
                symbol, True, total_size, num_orders, start_price, end_price, skew
            )
            
            if result["status"] == "ok":
                print(f"\n{result['message']}")
                
                # Display order details
                headers = ["Order #", "Size", "Price"]
                rows = []
                
                for i in range(len(result["sizes"])):
                    rows.append([
                        f"{i+1}/{num_orders}",
                        f"{result['sizes'][i]:.8f}",
                        f"{result['prices'][i]:.8f}"
                    ])
                
                self._print_table(headers, rows)
            else:
                print(f"\nScaled buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing scaled buy: {str(e)}")
    
    def do_scaled_sell(self, arg):
        """
        Place multiple sell orders across a price range (scaled orders)
        Usage: scaled_sell <symbol> <total_size> <num_orders> <start_price> <end_price> [skew]
        Example: scaled_sell ETH 0.5 5 3000 3200 0
        
        Start price should be lower than end price for sell orders.
        Skew value (optional): 0 = linear distribution, >0 = more weight to lower prices
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 5:
                print("Invalid arguments. Usage: scaled_sell <symbol> <total_size> <num_orders> <start_price> <end_price> [skew]")
                return
                
            symbol = args[0]
            total_size = float(args[1])
            num_orders = int(args[2])
            start_price = float(args[3])
            end_price = float(args[4])
            skew = float(args[5]) if len(args) > 5 else 0
            
            # Validate price direction
            if start_price > end_price:
                print("Warning: For sell orders, start_price should be lower than end_price. Swapping values.")
                start_price, end_price = end_price, start_price
            
            print(f"\nPlacing {num_orders} scaled sell orders for {symbol}:")
            print(f"Total size: {total_size}")
            print(f"Price range: {start_price} to {end_price}")
            print(f"Skew: {skew}")
            
            result = self.order_handler.scaled_orders(
                symbol, False, total_size, num_orders, start_price, end_price, skew
            )
            
            if result["status"] == "ok":
                print(f"\n{result['message']}")
                
                # Display order details
                headers = ["Order #", "Size", "Price"]
                rows = []
                
                for i in range(len(result["sizes"])):
                    rows.append([
                        f"{i+1}/{num_orders}",
                        f"{result['sizes'][i]:.8f}",
                        f"{result['prices'][i]:.8f}"
                    ])
                
                self._print_table(headers, rows)
            else:
                print(f"\nScaled sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing scaled sell: {str(e)}")
    
    def do_perp_scaled_buy(self, arg):
        """
        Place multiple perpetual buy orders across a price range (scaled orders)
        Usage: perp_scaled_buy <symbol> <total_size> <num_orders> <start_price> <end_price> [leverage] [skew]
        Example: perp_scaled_buy BTC 0.1 5 65000 64000 5 0
        
        Start price should be higher than end price for buy orders.
        Leverage (optional): Leverage to use (default: 1)
        Skew value (optional): 0 = linear distribution, >0 = more weight to higher prices
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 5:
                print("Invalid arguments. Usage: perp_scaled_buy <symbol> <total_size> <num_orders> <start_price> <end_price> [leverage] [skew]")
                return
                
            symbol = args[0]
            total_size = float(args[1])
            num_orders = int(args[2])
            start_price = float(args[3])
            end_price = float(args[4])
            leverage = int(args[5]) if len(args) > 5 else 1
            skew = float(args[6]) if len(args) > 6 else 0
            
            # Validate price direction
            if start_price < end_price:
                print("Warning: For buy orders, start_price should be higher than end_price. Swapping values.")
                start_price, end_price = end_price, start_price
            
            print(f"\nPlacing {num_orders} scaled perpetual buy orders for {symbol}:")
            print(f"Total size: {total_size}")
            print(f"Price range: {start_price} to {end_price}")
            print(f"Leverage: {leverage}x")
            print(f"Skew: {skew}")
            
            result = self.order_handler.perp_scaled_orders(
                symbol, True, total_size, num_orders, start_price, end_price, leverage, skew
            )
            
            if result["status"] == "ok":
                print(f"\n{result['message']}")
                
                # Display order details
                headers = ["Order #", "Size", "Price"]
                rows = []
                
                for i in range(len(result["sizes"])):
                    rows.append([
                        f"{i+1}/{num_orders}",
                        f"{result['sizes'][i]:.8f}",
                        f"{result['prices'][i]:.8f}"
                    ])
                
                self._print_table(headers, rows)
            else:
                print(f"\nScaled perpetual buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing scaled perpetual buy: {str(e)}")
    
    def do_perp_scaled_sell(self, arg):
        """
        Place multiple perpetual sell orders across a price range (scaled orders)
        Usage: perp_scaled_sell <symbol> <total_size> <num_orders> <start_price> <end_price> [leverage] [skew]
        Example: perp_scaled_sell BTC 0.1 5 64000 65000 5 0
        
        Start price should be lower than end price for sell orders.
        Leverage (optional): Leverage to use (default: 1)
        Skew value (optional): 0 = linear distribution, >0 = more weight to lower prices
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 5:
                print("Invalid arguments. Usage: perp_scaled_sell <symbol> <total_size> <num_orders> <start_price> <end_price> [leverage] [skew]")
                return
                
            symbol = args[0]
            total_size = float(args[1])
            num_orders = int(args[2])
            start_price = float(args[3])
            end_price = float(args[4])
            leverage = int(args[5]) if len(args) > 5 else 1
            skew = float(args[6]) if len(args) > 6 else 0
            
            # Validate price direction
            if start_price > end_price:
                print("Warning: For sell orders, start_price should be lower than end_price. Swapping values.")
                start_price, end_price = end_price, start_price
            
            print(f"\nPlacing {num_orders} scaled perpetual sell orders for {symbol}:")
            print(f"Total size: {total_size}")
            print(f"Price range: {start_price} to {end_price}")
            print(f"Leverage: {leverage}x")
            print(f"Skew: {skew}")
            
            result = self.order_handler.perp_scaled_orders(
                symbol, False, total_size, num_orders, start_price, end_price, leverage, skew
            )
            
            if result["status"] == "ok":
                print(f"\n{result['message']}")
                
                # Display order details
                headers = ["Order #", "Size", "Price"]
                rows = []
                
                for i in range(len(result["sizes"])):
                    rows.append([
                        f"{i+1}/{num_orders}",
                        f"{result['sizes'][i]:.8f}",
                        f"{result['prices'][i]:.8f}"
                    ])
                
                self._print_table(headers, rows)
            else:
                print(f"\nScaled perpetual sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing scaled perpetual sell: {str(e)}")

    def do_help_scaled(self, arg):
        """
        Show help about scaled orders functionality
        Usage: help_scaled
        """
        print("\n=== Scaled Orders Help ===")
        print("\nScaled orders place multiple limit orders across a price range.")
        print("They can help you get better average entry or exit prices by spreading orders.")
        
        print("\nCommands:")
        print("  scaled_buy      - Place multiple spot buy orders across a price range")
        print("  scaled_sell     - Place multiple spot sell orders across a price range")
        print("  perp_scaled_buy  - Place multiple perpetual buy orders across a price range")
        print("  perp_scaled_sell - Place multiple perpetual sell orders across a price range")
        
        print("\nSkew parameter:")
        print("  0.0 = Linear distribution (equal size for all orders)")
        print("  >0  = Exponential distribution (larger orders at better prices)")
        print("  1.0 = Moderate skew")
        print("  2.0 = Stronger skew")
        print("  3.0+ = Very aggressive skew")
        
        print("\nExamples:")
        print("  scaled_buy ETH 0.5 5 3200 3000 0")
        print("  Places 5 buy orders totaling 0.5 ETH from $3200 down to $3000 with equal sizes")
        
        print("\n  scaled_sell ETH 0.5 5 3000 3200 2")
        print("  Places 5 sell orders totaling 0.5 ETH from $3000 up to $3200 with more size on lower prices")
        
        print("\n  perp_scaled_buy BTC 0.1 5 65000 64000 5 1")
        print("  Places 5 perpetual buy orders totaling 0.1 BTC from $65000 down to $64000 with 5x leverage")
        print("  and moderately larger sizes on higher prices")
        
        print("\nPrice Direction:")
        print("  For buy orders: start_price should be higher than end_price")
        print("  For sell orders: start_price should be lower than end_price")
        print("  (The system will automatically swap them if provided in the wrong order)")
    # ================================ Scaled Market order=====================================
    def do_market_scaled_buy(self, arg):
        """
        Place multiple buy orders across a price range (scaled orders) with market awareness
        Usage: market_scaled_buy <symbol> <total_size> <num_orders> [price_percent] [skew]
        Example: market_scaled_buy ETH 0.5 5 5 0
        
        This creates 5 orders from 5% below best ask to best bid, adjusting for market conditions.
        The price_percent parameter determines how far below the best ask to start (default: 3%).
        Skew value (optional): 0 = linear distribution, >0 = more weight to higher prices
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: market_scaled_buy <symbol> <total_size> <num_orders> [price_percent] [skew]")
                return
                
            symbol = args[0]
            total_size = float(args[1])
            num_orders = int(args[2])
            price_percent = float(args[3]) if len(args) > 3 else 3.0  # Default to 3%
            skew = float(args[4]) if len(args) > 4 else 0
            
            # Get current market data
            try:
                # Get order book
                order_book = self.api_connector.info.l2_snapshot(symbol)
                
                if not order_book or "levels" not in order_book or len(order_book["levels"]) < 2:
                    print(f"Error: Could not fetch order book for {symbol}")
                    return
                    
                bid_levels = order_book["levels"][0]
                ask_levels = order_book["levels"][1]
                
                if not bid_levels or not ask_levels:
                    print(f"Error: Order book for {symbol} has no bids or asks")
                    return
                
                best_bid = float(bid_levels[0]["px"])
                best_ask = float(ask_levels[0]["px"])
                
                print(f"\nCurrent market for {symbol}:")
                print(f"Best bid: {best_bid}")
                print(f"Best ask: {best_ask}")
                print(f"Spread: {best_ask - best_bid} ({((best_ask - best_bid) / best_bid) * 100:.2f}%)")
                
                # Calculate price range
                start_price = best_ask * (1 - price_percent / 100)  # Start price is below ask
                end_price = best_bid  # End price is at best bid
                
                print(f"\nPlacing {num_orders} market-aware scaled buy orders for {symbol}:")
                print(f"Total size: {total_size}")
                print(f"Price range: {start_price} to {end_price}")
                print(f"This places orders from {price_percent}% below best ask down to the best bid")
                print(f"Skew: {skew}")
                
                # Confirm with user
                confirm = input("\nDo you want to proceed? (y/n): ")
                if confirm.lower() != 'y':
                    print("Order cancelled")
                    return
                
                result = self.order_handler.scaled_orders(
                    symbol, True, total_size, num_orders, start_price, end_price, skew, check_market=False
                )
                
                if result["status"] == "ok":
                    print(f"\n{result['message']}")
                    
                    # Display order details
                    headers = ["Order #", "Size", "Price"]
                    rows = []
                    
                    for i in range(len(result["sizes"])):
                        rows.append([
                            f"{i+1}/{num_orders}",
                            f"{result['sizes'][i]:.8f}",
                            f"{result['prices'][i]:.8f}"
                        ])
                    
                    self._print_table(headers, rows)
                else:
                    print(f"\nMarket-aware scaled buy order failed: {result.get('message', 'Unknown error')}")
                
            except Exception as e:
                print(f"Error fetching market data: {str(e)}")
                return
                
        except Exception as e:
            print(f"\nError executing market-aware scaled buy: {str(e)}")
            
    def do_market_scaled_sell(self, arg):
        """
        Place multiple sell orders across a price range (scaled orders) with market awareness
        Usage: market_scaled_sell <symbol> <total_size> <num_orders> [price_percent] [skew]
        Example: market_scaled_sell ETH 0.5 5 5 0
        
        This creates 5 orders from best ask to 5% above best bid, adjusting for market conditions.
        The price_percent parameter determines how far above the best bid to end (default: 3%).
        Skew value (optional): 0 = linear distribution, >0 = more weight to lower prices
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: market_scaled_sell <symbol> <total_size> <num_orders> [price_percent] [skew]")
                return
                
            symbol = args[0]
            total_size = float(args[1])
            num_orders = int(args[2])
            price_percent = float(args[3]) if len(args) > 3 else 3.0  # Default to 3%
            skew = float(args[4]) if len(args) > 4 else 0
            
            # Get current market data
            try:
                # Get order book
                order_book = self.api_connector.info.l2_snapshot(symbol)
                
                if not order_book or "levels" not in order_book or len(order_book["levels"]) < 2:
                    print(f"Error: Could not fetch order book for {symbol}")
                    return
                    
                bid_levels = order_book["levels"][0]
                ask_levels = order_book["levels"][1]
                
                if not bid_levels or not ask_levels:
                    print(f"Error: Order book for {symbol} has no bids or asks")
                    return
                
                best_bid = float(bid_levels[0]["px"])
                best_ask = float(ask_levels[0]["px"])
                
                print(f"\nCurrent market for {symbol}:")
                print(f"Best bid: {best_bid}")
                print(f"Best ask: {best_ask}")
                print(f"Spread: {best_ask - best_bid} ({((best_ask - best_bid) / best_bid) * 100:.2f}%)")
                
                # Calculate price range
                start_price = best_ask  # Start price is at best ask
                end_price = best_bid * (1 + price_percent / 100)  # End price is above bid
                
                print(f"\nPlacing {num_orders} market-aware scaled sell orders for {symbol}:")
                print(f"Total size: {total_size}")
                print(f"Price range: {start_price} to {end_price}")
                print(f"This places orders from best ask up to {price_percent}% above best bid")
                print(f"Skew: {skew}")
                
                # Confirm with user
                confirm = input("\nDo you want to proceed? (y/n): ")
                if confirm.lower() != 'y':
                    print("Order cancelled")
                    return
                
                result = self.order_handler.scaled_orders(
                    symbol, False, total_size, num_orders, start_price, end_price, skew, check_market=False
                )
                
                if result["status"] == "ok":
                    print(f"\n{result['message']}")
                    
                    # Display order details
                    headers = ["Order #", "Size", "Price"]
                    rows = []
                    
                    for i in range(len(result["sizes"])):
                        rows.append([
                            f"{i+1}/{num_orders}",
                            f"{result['sizes'][i]:.8f}",
                            f"{result['prices'][i]:.8f}"
                        ])
                    
                    self._print_table(headers, rows)
                else:
                    print(f"\nMarket-aware scaled sell order failed: {result.get('message', 'Unknown error')}")
                
            except Exception as e:
                print(f"Error fetching market data: {str(e)}")
                return
                
        except Exception as e:
            print(f"\nError executing market-aware scaled sell: {str(e)}")
            
    def do_help_market_scaled(self, arg):
        """
        Show help about market-aware scaled orders functionality
        Usage: help_market_scaled
        """
        print("\n=== Market-Aware Scaled Orders Help ===")
        print("\nMarket-aware scaled orders automatically adjust to current market conditions.")
        print("They help you place orders at realistic prices based on the current order book.")
        
        print("\nCommands:")
        print("  market_scaled_buy  - Place multiple buy orders from below ask to best bid")
        print("  market_scaled_sell - Place multiple sell orders from best ask to above bid")
        
        print("\nParameters:")
        print("  symbol       - Trading pair symbol (e.g., ETH or PURR/USDC)")
        print("  total_size   - Total size to be distributed across all orders")
        print("  num_orders   - Number of orders to place")
        print("  price_percent - How far from market price to start/end (default: 3%)")
        print("  skew         - Order size distribution (0=equal, >0=weighted)")
        
        print("\nExample for buying:")
        print("  market_scaled_buy PURR/USDC 10 5 2 0")
        print("  Places 5 buy orders totaling 10 PURR from 2% below best ask down to best bid")
        
        print("\nExample for selling:")
        print("  market_scaled_sell ETH 0.5 4 3 1")
        print("  Places 4 sell orders totaling 0.5 ETH from best ask up to 3% above best bid")
        print("  With skew=1, more ETH is placed at lower prices")

    # ================================= Testing Grid Trading =====================================
    def do_test_symbol(self, arg):
        """
        Test if a symbol is available and can be used for grid trading
        Usage: test_symbol <symbol>
        Example: test_symbol BTC
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            symbol = arg.strip()
            if not symbol:
                print("Invalid arguments. Usage: test_symbol <symbol>")
                return
            
            print(f"\nTesting market data retrieval for {symbol}...")
            
            # Add the test_market_data method to order_handler if it doesn't exist
            if not hasattr(self.order_handler, 'test_market_data'):
                print("Adding market data test capability...")
                from types import MethodType
                
                def test_market_data(self, symbol: str):
                    """Dynamic implementation of test_market_data"""
                    if not self.api_connector:
                        return {
                            "success": False,
                            "message": "API connector not set. Please connect to exchange first."
                        }
                    
                    if not self.exchange or not self.info:
                        return {
                            "success": False,
                            "message": "Not connected to exchange. Please connect first."
                        }
                    
                    try:
                        # Try to get market data
                        market_data = self.api_connector.get_market_data(symbol)
                        
                        if "error" in market_data:
                            return {
                                "success": False,
                                "message": f"Could not get market data: {market_data['error']}"
                            }
                        
                        # Check if we have the necessary price data
                        if "mid_price" not in market_data and "best_bid" not in market_data and "best_ask" not in market_data:
                            return {
                                "success": False,
                                "message": f"Could not determine price for {symbol}"
                            }
                        
                        # If we have price data, consider it a success
                        price = market_data.get("mid_price")
                        if not price:
                            if market_data.get("best_bid") and market_data.get("best_ask"):
                                price = (market_data["best_bid"] + market_data["best_ask"]) / 2
                            elif market_data.get("best_bid"):
                                price = market_data["best_bid"]
                            elif market_data.get("best_ask"):
                                price = market_data["best_ask"]
                        
                        return {
                            "success": True,
                            "message": f"Successfully retrieved market data for {symbol}",
                            "price": price,
                            "market_data": market_data
                        }
                    
                    except Exception as e:
                        return {
                            "success": False,
                            "message": f"Error testing market data: {str(e)}"
                        }
                
                # Add the method to the order_handler instance
                self.order_handler.test_market_data = MethodType(test_market_data, self.order_handler)
            
            # Test the symbol
            result = self.order_handler.test_market_data(symbol)
            
            if result["success"]:
                print(f"✅ Symbol {symbol} is available")
                print(f"Current price: {result['price']}")
                
                if "market_data" in result:
                    market_data = result["market_data"]
                    if "best_bid" in market_data:
                        print(f"Best bid: {market_data['best_bid']}")
                    if "best_ask" in market_data:
                        print(f"Best ask: {market_data['best_ask']}")
                
                print("\nThis symbol can be used for grid trading.")
            else:
                print(f"❌ Symbol test failed: {result['message']}")
                print("\nRecommendations:")
                print("1. Check if the symbol is correctly formatted (e.g., 'BTC', not 'btc' or 'Bitcoin')")
                print("2. Verify the symbol is available on the exchange")
                print("3. Try reconnecting to the exchange")
                print("4. Check exchange documentation for supported symbols")
            
        except Exception as e:
            print(f"\nError testing symbol: {str(e)}")
    # ==================================== Grid Trading ==========================================

    def do_grid_create(self, arg):
        """
        Create a new grid trading strategy
        Usage: grid_create <symbol> <upper_price> <lower_price> <num_grids> <total_investment> [is_perp] [leverage] [take_profit] [stop_loss]
        
        Example (spot): grid_create ETH 3500 3000 10 1000
        Example (perp): grid_create BTC 65000 60000 20 5000 true 5 5 10
        
        Parameters:
            symbol:           Trading pair symbol
            upper_price:      Upper price boundary of the grid
            lower_price:      Lower price boundary of the grid
            num_grids:        Number of grid levels (minimum 2)
            total_investment: Total amount to invest in the grid
            is_perp:          (Optional) Whether to use perpetual contracts (true/false)
            leverage:         (Optional) Leverage to use for perpetual orders
            take_profit:      (Optional) Take profit level as percentage
            stop_loss:        (Optional) Stop loss level as percentage
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 5:
                print("Invalid arguments. Usage: grid_create <symbol> <upper_price> <lower_price> <num_grids> <total_investment> [is_perp] [leverage] [take_profit] [stop_loss]")
                return
                
            symbol = args[0]
            upper_price = float(args[1])
            lower_price = float(args[2])
            num_grids = int(args[3])
            total_investment = float(args[4])
            
            # Optional arguments
            is_perp = False
            leverage = 1
            take_profit = None
            stop_loss = None
            
            if len(args) > 5:
                is_perp_str = args[5].lower()
                is_perp = is_perp_str in ['true', 't', 'yes', 'y', '1']
            
            if len(args) > 6 and is_perp:
                leverage = int(args[6])
            
            if len(args) > 7:
                take_profit = float(args[7])
            
            if len(args) > 8:
                stop_loss = float(args[8])
            
            print(f"\nCreating grid trading strategy for {symbol}")
            print(f"Price range: {lower_price} to {upper_price}")
            print(f"Number of grids: {num_grids}")
            print(f"Total investment: {total_investment}")
            if is_perp:
                print(f"Market type: Perpetual")
                print(f"Leverage: {leverage}x")
            else:
                print(f"Market type: Spot")
            if take_profit:
                print(f"Take profit: {take_profit}%")
            if stop_loss:
                print(f"Stop loss: {stop_loss}%")
            
            # Confirm with user
            confirm = input("\nDo you want to proceed? (y/n): ")
            if confirm.lower() != 'y':
                print("Grid creation cancelled")
                return
            
            # Create the grid
            grid_id = self.order_handler.create_grid(
                symbol, upper_price, lower_price, num_grids, total_investment,
                is_perp, leverage, take_profit, stop_loss
            )
            
            print(f"\nCreated grid trading strategy with ID: {grid_id}")
            print("Use 'grid_start {0}' to start the strategy".format(grid_id))
            
        except Exception as e:
            print(f"\nError creating grid trading strategy: {str(e)}")
    
    def do_grid_start(self, arg):
        """
        Start a grid trading strategy
        Usage: grid_start <grid_id>
        Example: grid_start grid_20240308123045_1
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            grid_id = arg.strip()
            if not grid_id:
                print("Invalid arguments. Usage: grid_start <grid_id>")
                return
            
            print(f"\nStarting grid trading strategy {grid_id}")
            
            # Start the grid
            result = self.order_handler.start_grid(grid_id)
            
            if result["status"] == "ok":
                print(f"Successfully started grid strategy {grid_id}")
                print(f"Placed {result['buy_orders']} buy orders and {result['sell_orders']} sell orders")
                print(f"Current market price: {result['current_price']}")
                
                if result.get("warning"):
                    print(f"\nWarning: {result['warning']}")
                
                print("\nUse 'grid_status {0}' to check the status".format(grid_id))
            else:
                print(f"Failed to start grid strategy: {result.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"\nError starting grid strategy: {str(e)}")
    
    def do_grid_stop(self, arg):
        """
        Stop a grid trading strategy
        Usage: grid_stop <grid_id>
        Example: grid_stop grid_20240308123045_1
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            grid_id = arg.strip()
            if not grid_id:
                print("Invalid arguments. Usage: grid_stop <grid_id>")
                return
            
            print(f"\nStopping grid trading strategy {grid_id}")
            
            # Stop the grid
            result = self.order_handler.stop_grid(grid_id)
            
            if result["status"] == "ok":
                print(f"Successfully stopped grid strategy {grid_id}")
                print(f"Cancelled {result['cancelled_orders']}/{result['total_orders']} open orders")
                print(f"Total profit/loss: {result['profit_loss']}")
            else:
                print(f"Failed to stop grid strategy: {result.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"\nError stopping grid strategy: {str(e)}")
    
    def do_grid_status(self, arg):
        """
        Get the status of a grid trading strategy
        Usage: grid_status <grid_id>
        Example: grid_status grid_20240308123045_1
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            grid_id = arg.strip()
            if not grid_id:
                print("Invalid arguments. Usage: grid_status <grid_id>")
                return
            
            # Get the status
            status = self.order_handler.get_grid_status(grid_id)
            
            if status["status"] != "error":
                print(f"\n=== Grid Trading Status: {grid_id} ===")
                print(f"Symbol: {status['symbol']}")
                print(f"Status: {status['status']}")
                print(f"Market type: {'Perpetual' if status.get('is_perp', False) else 'Spot'}")
                if status.get('is_perp', False):
                    print(f"Leverage: {status['leverage']}x")
                print(f"Price range: {status['lower_price']} to {status['upper_price']}")
                print(f"Number of grids: {status['num_grids']}")
                print(f"Grid interval: {status['price_interval']}")
                print(f"Total investment: {status['total_investment']}")
                print(f"Investment per grid: {status['investment_per_grid']}")
                
                if status.get('current_price'):
                    print(f"Current price: {status['current_price']}")
                
                # Count active orders
                open_orders = sum(1 for order in status.get('orders', []) if order.get('status') == 'open')
                filled_orders = len(status.get('filled_orders', []))
                print(f"Open orders: {open_orders}")
                print(f"Filled orders: {filled_orders}")
                print(f"Profit/Loss: {status.get('profit_loss', 0)}")
                
                if status.get('take_profit'):
                    print(f"Take profit: {status['take_profit']}%")
                if status.get('stop_loss'):
                    print(f"Stop loss: {status['stop_loss']}%")
                
                if status.get('error'):
                    print(f"\nError: {status['error']}")
            else:
                print(f"\nFailed to get grid status: {status.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"\nError getting grid status: {str(e)}")
    
    def do_grid_list(self, arg):
        """
        List all grid trading strategies
        Usage: grid_list
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # Get the list
            grid_list = self.order_handler.list_grids()
            
            # Display active grids
            print("\n=== Active Grid Trading Strategies ===")
            if grid_list["active"]:
                for grid in grid_list["active"]:
                    print(f"ID: {grid['id']}")
                    print(f"  Symbol: {grid['symbol']}")
                    print(f"  Status: {grid['status']}")
                    print(f"  Price range: {grid['lower_price']} to {grid['upper_price']}")
                    print(f"  Investment: {grid['total_investment']}")
                    
                    # Count active orders
                    open_orders = sum(1 for order in grid.get('orders', []) if order.get('status') == 'open')
                    filled_orders = len(grid.get('filled_orders', []))
                    print(f"  Open orders: {open_orders}")
                    print(f"  Filled orders: {filled_orders}")
                    print(f"  Profit/Loss: {grid.get('profit_loss', 0)}")
                    print()
            else:
                print("No active grid trading strategies\n")
            
            # Display completed grids
            print("=== Completed Grid Trading Strategies ===")
            if grid_list["completed"]:
                for grid in grid_list["completed"]:
                    print(f"ID: {grid['id']}")
                    print(f"  Symbol: {grid['symbol']}")
                    print(f"  Status: {grid['status']}")
                    print(f"  Price range: {grid['lower_price']} to {grid['upper_price']}")
                    print(f"  Investment: {grid['total_investment']}")
                    print(f"  Filled orders: {len(grid.get('filled_orders', []))}")
                    print(f"  Final Profit/Loss: {grid.get('profit_loss', 0)}")
                    print()
            else:
                print("No completed grid trading strategies")
            
        except Exception as e:
            print(f"\nError listing grid strategies: {str(e)}")
    
    def do_grid_stop_all(self, arg):
        """
        Stop all active grid trading strategies
        Usage: grid_stop_all
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # Confirm with user
            confirm = input("\nAre you sure you want to stop all active grid trading strategies? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
            
            # Stop all grids
            count = self.order_handler.stop_all_grids()
            
            print(f"\nStopped {count} grid trading strategies")
            
        except Exception as e:
            print(f"\nError stopping grid strategies: {str(e)}")
    
    def do_grid_clean(self, arg):
        """
        Clean up completed grid trading strategies
        Usage: grid_clean
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # Clean up completed grids
            count = self.order_handler.clean_completed_grids()
            
            print(f"\nCleaned up {count} completed grid trading strategies")
            
        except Exception as e:
            print(f"\nError cleaning grid strategies: {str(e)}")
    
    def do_grid_modify(self, arg):
        """
        Modify parameters of a grid trading strategy
        Usage: grid_modify <grid_id> [take_profit] [stop_loss]
        Example: grid_modify grid_20240308123045_1 5 10
        
        Parameters:
            grid_id:      ID of the grid to modify
            take_profit:  (Optional) New take profit level as percentage
            stop_loss:    (Optional) New stop loss level as percentage
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 1:
                print("Invalid arguments. Usage: grid_modify <grid_id> [take_profit] [stop_loss]")
                return
            
            grid_id = args[0]
            take_profit = float(args[1]) if len(args) > 1 else None
            stop_loss = float(args[2]) if len(args) > 2 else None
            
            if take_profit is None and stop_loss is None:
                print("No parameters specified to modify")
                return
            
            # Modify the grid
            result = self.order_handler.modify_grid(grid_id, take_profit, stop_loss)
            
            if result["status"] == "ok":
                print(f"\nSuccessfully modified grid {grid_id}")
                print(f"Changes: {', '.join(result['changes'])}")
            else:
                print(f"\nFailed to modify grid: {result.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"\nError modifying grid: {str(e)}")
    
    def do_help_grid(self, arg):
        """
        Show help about grid trading functionality
        Usage: help_grid
        """
        print("\n=== Grid Trading Help ===")
        print("\nGrid trading is a strategy that places multiple buy and sell orders at regular price intervals.")
        print("It profits from price oscillations within a range by buying low and selling high repeatedly.")
        print("This strategy works well in sideways markets with predictable price movements.")
        
        print("\nCommands:")
        print("  grid_create     - Create a new grid trading strategy")
        print("  grid_start      - Start a grid trading strategy")
        print("  grid_stop       - Stop a grid trading strategy")
        print("  grid_status     - Check the status of a grid trading strategy")
        print("  grid_list       - List all grid trading strategies")
        print("  grid_stop_all   - Stop all active grid trading strategies")
        print("  grid_clean      - Clean up completed grid trading strategies")
        print("  grid_modify     - Modify parameters of a grid trading strategy")
        
        print("\nBasic Grid Setup:")
        print("  1. Define your price range (upper and lower boundaries)")
        print("  2. Decide how many grids (price levels) you want")
        print("  3. Set your total investment amount")
        print("  4. Optionally set take profit and stop loss levels")
        
        print("\nExample for spot trading:")
        print("  grid_create ETH 3500 3000 10 1000")
        print("  Creates a grid for ETH with 10 levels from $3000 to $3500, investing $1000 total")
        
        print("\nExample for perpetual trading:")
        print("  grid_create BTC 65000 60000 20 5000 true 5 5 10")
        print("  Creates a grid for BTC perpetuals with 20 levels from $60000 to $65000,")
        print("  investing $5000 total with 5x leverage, 5% take profit and 10% stop loss")
        
        print("\nHow it works:")
        print("  - Orders are placed at regular intervals throughout your price range")
        print("  - When a buy order is filled, a sell order is placed one level above")
        print("  - When a sell order is filled, a buy order is placed one level below")
        print("  - This creates a continuous cycle of buying low and selling high")
        print("  - Profits accumulate with each completed buy-sell cycle")
    # ================================Cancellation of Orders=====================================
    
    def do_cancel(self, arg):
        """
        Cancel a specific order
        Usage: cancel <symbol> <order_id>
        Example: cancel ETH 123456
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: cancel <symbol> <order_id>")
                return
                
            symbol = args[0]
            order_id = int(args[1])
            
            print(f"\nCancelling order {order_id} for {symbol}")
            result = self.order_handler.cancel_order(symbol, order_id)
            
            if result["status"] == "ok":
                print(f"Order {order_id} cancelled successfully")
            else:
                print(f"Failed to cancel order: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError cancelling order: {str(e)}")
    
    def do_cancel_all(self, arg):
        """
        Cancel all open orders, optionally for a specific symbol
        Usage: cancel_all [symbol]
        Example: cancel_all ETH
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            symbol = arg.strip() if arg.strip() else None
            symbol_text = f" for {symbol}" if symbol else ""
            
            print(f"\nCancelling all orders{symbol_text}")
            result = self.order_handler.cancel_all_orders(symbol)
            
            if result["status"] == "ok":
                cancelled = result["data"]["cancelled"]
                failed = result["data"]["failed"]
                print(f"Cancelled {cancelled} orders, {failed} failed")
            else:
                print(f"Failed to cancel orders: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError cancelling orders: {str(e)}")
    
    def do_orders(self, arg):
        """
        List all open orders, optionally for a specific symbol
        Usage: orders [symbol]
        Example: orders ETH
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            symbol = arg.strip() if arg.strip() else None
            symbol_text = f" for {symbol}" if symbol else ""
            
            print(f"\n=== Open Orders{symbol_text} ===")
            open_orders = self.order_handler.get_open_orders(symbol)
            
            if open_orders:
                headers = ["Symbol", "Side", "Size", "Price", "Order ID", "Timestamp"]
                rows = []
                
                for order in open_orders:
                    timestamp = datetime.fromtimestamp(order.get("timestamp", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    rows.append([
                        order.get("coin", ""),
                        "Buy" if order.get("side", "") == "B" else "Sell",
                        float(order.get("sz", 0)),
                        float(order.get("limitPx", 0)),
                        order.get("oid", 0),
                        timestamp
                    ])
                
                self._print_table(headers, rows)
            else:
                print("No open orders")
                
        except Exception as e:
            print(f"\nError fetching open orders: {str(e)}")
    
    def do_positions(self, arg):
        """
        Show current positions
        Usage: positions
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            print("\n=== Current Positions ===")
            positions = []
            
            perp_state = self.api_connector.info.user_state(self.api_connector.wallet_address)
            for asset_position in perp_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                if float(position.get("szi", 0)) != 0:
                    positions.append({
                        "symbol": position.get("coin", ""),
                        "size": float(position.get("szi", 0)),
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0)),
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0))
                    })
            
            if positions:
                headers = ["Symbol", "Size", "Entry Price", "Mark Price", "Unrealized PnL", "Margin Used"]
                rows = []
                
                for pos in positions:
                    rows.append([
                        pos["symbol"],
                        pos["size"],
                        pos["entry_price"],
                        pos["mark_price"],
                        pos["unrealized_pnl"],
                        pos["margin_used"]
                    ])
                
                self._print_table(headers, rows)
            else:
                print("No open positions")
                
        except Exception as e:
            print(f"\nError fetching positions: {str(e)}")
    
    def do_history(self, arg):
        """
        Show trading history
        Usage: history [limit]
        Example: history 10
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            limit = int(arg) if arg.isdigit() else 20
            
            print(f"\n=== Trading History (Last {limit} Trades) ===")
            
            fills = []
            try:
                with open("fills", "r") as f:
                    for line in f:
                        fills.extend(json.loads(line.strip()))
            except FileNotFoundError:
                print("No trading history found")
                return
            
            if fills:
                headers = ["Time", "Symbol", "Side", "Size", "Price", "PnL"]
                rows = []
                
                for fill in fills[-limit:]:
                    time_str = datetime.fromtimestamp(fill["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    rows.append([
                        time_str,
                        fill["coin"],
                        "Buy" if fill["side"] == "B" else "Sell",
                        float(fill["sz"]),
                        float(fill["px"]),
                        float(fill.get("closedPnl", 0))
                    ])
                
                self._print_table(headers, rows)
            else:
                print("No trades found")
                
        except Exception as e:
            print(f"\nError fetching history: {str(e)}")
    
    def do_clear(self, arg):
        """Clear the terminal screen"""
        self.display_layout()
    
    def do_exit(self, arg):
        """Exit the Elysium CLI"""
        print("\nThank you for using Elysium Trading Bot!")
        return True
        
    def do_EOF(self, arg):
        """Exit on Ctrl+D"""
        return self.do_exit(arg)
    
    def _print_table(self, headers, rows):
        """Print a formatted table to the console"""
        # Calculate column widths
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print headers
        header_str = " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
        print(header_str)
        print("-" * len(header_str))
        
        # Print rows
        for row in rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            print(row_str)

# =======================================TWAPS==================================================
    def do_twap_create(self, arg):
        """
        Create a new TWAP execution
        Usage: twap_create <symbol> <side> <quantity> <duration_minutes> <num_slices> [price_limit] [is_perp] [leverage]
        Example: twap_create BTC buy 0.1 60 10 50000
        Example: twap_create ETH buy 0.5 30 5 3000 true 2  # Perpetual with leverage
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 5:
                print("Invalid arguments. Usage: twap_create <symbol> <side> <quantity> <duration_minutes> <num_slices> [price_limit] [is_perp] [leverage]")
                return
                
            symbol = args[0]
            side = args[1].lower()
            if side not in ['buy', 'sell']:
                print("Side must be 'buy' or 'sell'")
                return
                
            quantity = float(args[2])
            duration_minutes = int(args[3])
            num_slices = int(args[4])
            
            # Optional arguments
            price_limit = None
            is_perp = False
            leverage = 1
            
            if len(args) > 5:
                price_limit = float(args[5])
            
            if len(args) > 6:
                is_perp_str = args[6].lower()
                is_perp = is_perp_str in ['true', 't', 'yes', 'y', '1']
            
            if len(args) > 7 and is_perp:
                leverage = int(args[7])
            
            # Create the TWAP
            twap_id = self.order_handler.create_twap(
                symbol, side, quantity, duration_minutes, num_slices, price_limit, is_perp, leverage
            )
            
            print(f"\nCreated TWAP execution {twap_id}")
            print(f"Symbol: {symbol}")
            print(f"Side: {side}")
            print(f"Total Quantity: {quantity}")
            print(f"Duration: {duration_minutes} minutes")
            print(f"Number of Slices: {num_slices}")
            if price_limit:
                print(f"Price Limit: {price_limit}")
            if is_perp:
                print(f"Order Type: Perpetual")
                print(f"Leverage: {leverage}x")
            else:
                print(f"Order Type: Spot")
            print(f"Quantity per Slice: {quantity / num_slices}")
            print(f"Time between Slices: {(duration_minutes * 60) / num_slices} seconds")
            print("\nUse 'twap_start {0}' to start the execution".format(twap_id))
            
        except Exception as e:
            print(f"\nError creating TWAP: {str(e)}")

    def do_twap_start(self, arg):
        """
        Start a TWAP execution
        Usage: twap_start <twap_id>
        Example: twap_start twap_20240308123045_1
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            twap_id = arg.strip()
            if not twap_id:
                print("Invalid arguments. Usage: twap_start <twap_id>")
                return
            
            # Start the TWAP
            success = self.order_handler.start_twap(twap_id)
            
            if success:
                print(f"\nStarted TWAP execution {twap_id}")
                print("Use 'twap_status {0}' to check the status".format(twap_id))
            else:
                print(f"\nFailed to start TWAP execution {twap_id}")
            
        except Exception as e:
            print(f"\nError starting TWAP: {str(e)}")

    def do_twap_stop(self, arg):
        """
        Stop a TWAP execution
        Usage: twap_stop <twap_id>
        Example: twap_stop twap_20240308123045_1
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            twap_id = arg.strip()
            if not twap_id:
                print("Invalid arguments. Usage: twap_stop <twap_id>")
                return
            
            # Stop the TWAP
            success = self.order_handler.stop_twap(twap_id)
            
            if success:
                print(f"\nStopped TWAP execution {twap_id}")
            else:
                print(f"\nFailed to stop TWAP execution {twap_id}")
            
        except Exception as e:
            print(f"\nError stopping TWAP: {str(e)}")

    def do_twap_status(self, arg):
        """
        Get the status of a TWAP execution
        Usage: twap_status <twap_id>
        Example: twap_status twap_20240308123045_1
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            twap_id = arg.strip()
            if not twap_id:
                print("Invalid arguments. Usage: twap_status <twap_id>")
                return
            
            # Get the status
            status = self.order_handler.get_twap_status(twap_id)
            
            if status:
                print(f"\n=== TWAP Execution Status: {twap_id} ===")
                print(f"Symbol: {status['symbol']}")
                print(f"Side: {status['side']}")
                print(f"Status: {status['status']}")
                print(f"Order Type: {'Perpetual' if status.get('is_perp', False) else 'Spot'}")
                print(f"Total Quantity: {status['total_quantity']}")
                print(f"Duration: {status['duration_minutes']} minutes")
                print(f"Slices: {status['slices_executed']}/{status['num_slices']} ({status['completion_percentage']:.1f}%)")
                print(f"Quantity per Slice: {status['quantity_per_slice']}")
                print(f"Executed: {status['total_executed']}/{status['total_quantity']} ({(status['total_executed']/status['total_quantity']*100) if status['total_quantity'] > 0 else 0:.1f}%)")
                if status['average_price'] > 0:
                    print(f"Average Execution Price: {status['average_price']}")
                if status['start_time']:
                    print(f"Start Time: {status['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                if status['end_time']:
                    print(f"Expected End Time: {status['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                if status['errors']:
                    print("\nErrors:")
                    for error in status['errors']:
                        print(f"  - {error}")
            else:
                print(f"\nTWAP execution {twap_id} not found")
            
        except Exception as e:
            print(f"\nError getting TWAP status: {str(e)}")

    def do_twap_list(self, arg):
        """
        List all TWAP executions
        Usage: twap_list
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # Get the list
            twap_list = self.order_handler.list_twaps()
            
            # Display active TWAPs
            print("\n=== Active TWAP Executions ===")
            if twap_list["active"]:
                for twap in twap_list["active"]:
                    print(f"ID: {twap['id']}")
                    print(f"  Symbol: {twap['symbol']}")
                    print(f"  Side: {twap['side']}")
                    print(f"  Type: {'Perpetual' if twap.get('is_perp', False) else 'Spot'}")
                    print(f"  Progress: {twap['slices_executed']}/{twap['num_slices']} slices ({twap['completion_percentage']:.1f}%)")
                    print(f"  Executed: {twap['total_executed']}/{twap['total_quantity']}")
                    if twap['average_price'] > 0:
                        print(f"  Avg Price: {twap['average_price']}")
                    print()
            else:
                print("No active TWAP executions\n")
            
            # Display completed TWAPs
            print("=== Completed TWAP Executions ===")
            if twap_list["completed"]:
                for twap in twap_list["completed"]:
                    print(f"ID: {twap['id']}")
                    print(f"  Symbol: {twap['symbol']}")
                    print(f"  Side: {twap['side']}")
                    print(f"  Type: {'Perpetual' if twap.get('is_perp', False) else 'Spot'}")
                    print(f"  Completed: {twap['slices_executed']}/{twap['num_slices']} slices")
                    print(f"  Executed: {twap['total_executed']}/{twap['total_quantity']}")
                    if twap['average_price'] > 0:
                        print(f"  Avg Price: {twap['average_price']}")
                    print()
            else:
                print("No completed TWAP executions")
            
        except Exception as e:
            print(f"\nError listing TWAPs: {str(e)}")

    def do_twap_stop_all(self, arg):
        """
        Stop all active TWAP executions
        Usage: twap_stop_all
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # Stop all TWAPs
            count = self.order_handler.stop_all_twaps()
            
            print(f"\nStopped {count} TWAP executions")
            
        except Exception as e:
            print(f"\nError stopping TWAPs: {str(e)}")

    def do_twap_clean(self, arg):
        """
        Clean up completed TWAP executions
        Usage: twap_clean
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # Clean up completed TWAPs
            count = self.order_handler.clean_completed_twaps()
            
            print(f"\nCleaned up {count} completed TWAP executions")
            
        except Exception as e:
            print(f"\nError cleaning TWAPs: {str(e)}")

# =====================================Strategy Selector=========================================

    # These methods should be added to the ElysiumTerminalUI class in terminal_ui.py

    def __init__(self, api_connector, order_handler, config_manager):
        super().__init__()
        self.prompt = '>>> '
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.authenticated = False
        self.last_command_output = ""
        
        # Initialize strategy selector
        from strategy_selector import StrategySelector
        self.strategy_selector = StrategySelector(api_connector, order_handler, config_manager)

    def do_select_strategy(self, arg):
        """
        Select and configure a trading strategy
        Usage: select_strategy [strategy_name]
        Example: select_strategy pure_mm
        
        If no strategy name is provided, a list of available strategies will be displayed.
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # If no specific strategy is provided, list available strategies
            if not arg.strip():
                strategies = self.strategy_selector.list_strategies()
                
                if not strategies:
                    print("\nNo trading strategies available.")
                    print("Please make sure strategy files are in the 'strategies' directory.")
                    return
                
                print("\n=== Available Trading Strategies ===")
                
                for i, strategy in enumerate(strategies):
                    print(f"{i+1}. {strategy['name']}")
                    print(f"   Module: {strategy['module']}")
                    print(f"   Description: {strategy['description']}")
                    print()
                
                print("To select a strategy, use: select_strategy <module_name>")
                print("Example: select_strategy pure_mm")
                return
            
            # A specific strategy was requested
            strategy_name = arg.strip()
            
            # Check if strategy exists
            strategies = self.strategy_selector.list_strategies()
            strategy_exists = any(s['module'] == strategy_name for s in strategies)
            
            if not strategy_exists:
                print(f"\nStrategy '{strategy_name}' not found.")
                print("Use 'select_strategy' to see available strategies.")
                return
            
            # Get strategy parameters
            params = self.strategy_selector.get_strategy_params(strategy_name)
            
            if not params:
                print(f"\nStrategy '{strategy_name}' has no configurable parameters.")
                
                # Confirm starting with default parameters
                confirm = input("Do you want to start this strategy with default settings? (y/n): ")
                if confirm.lower() == 'y':
                    success = self.strategy_selector.start_strategy(strategy_name)
                    if success:
                        print(f"\nStarted strategy: {strategy_name}")
                        print("Use 'strategy_status' to check status.")
                        print("Use 'stop_strategy' to stop the strategy.")
                    else:
                        print(f"\nFailed to start strategy: {strategy_name}")
                return
            
            # Show current parameters and allow customization
            print(f"\n=== '{strategy_name}' Parameters ===")
            
            # Display parameters in a more user-friendly way
            for param_name, param_data in params.items():
                if isinstance(param_data, dict) and "value" in param_data:
                    value = param_data["value"]
                    description = param_data.get("description", "")
                    print(f"{param_name}: {value} - {description}")
                else:
                    print(f"{param_name}: {param_data}")
            
            # Ask if user wants to customize
            customize = input("\nDo you want to customize these parameters? (y/n): ")
            
            custom_params = {}
            
            if customize.lower() == 'y':
                for param_name, param_data in params.items():
                    if isinstance(param_data, dict) and "value" in param_data:
                        current_value = param_data["value"]
                        param_type = param_data.get("type", "str")
                        description = param_data.get("description", "")
                        
                        # Show the current value and description
                        prompt = f"{param_name} ({description}) [{current_value}]: "
                        
                        # Get user input
                        user_input = input(prompt)
                        
                        # Use current value if no input
                        if not user_input.strip():
                            custom_params[param_name] = {"value": current_value}
                            continue
                        
                        # Convert input to the correct type
                        try:
                            if param_type == "float":
                                value = float(user_input)
                            elif param_type == "int":
                                value = int(user_input)
                            elif param_type == "bool":
                                value = user_input.lower() in ('yes', 'true', 't', 'y', '1')
                            else:
                                value = user_input
                            
                            custom_params[param_name] = {"value": value}
                        except ValueError:
                            print(f"Invalid value for {param_name}. Using default: {current_value}")
                            custom_params[param_name] = {"value": current_value}
                    else:
                        # Simple parameter without metadata
                        current_value = param_data
                        prompt = f"{param_name} [{current_value}]: "
                        user_input = input(prompt)
                        
                        if not user_input.strip():
                            custom_params[param_name] = current_value
                        else:
                            custom_params[param_name] = user_input
            else:
                # Use default parameters
                for param_name, param_data in params.items():
                    if isinstance(param_data, dict) and "value" in param_data:
                        custom_params[param_name] = {"value": param_data["value"]}
                    else:
                        custom_params[param_name] = param_data
            
            # Confirm starting the strategy
            confirm = input("\nStart strategy with these parameters? (y/n): ")
            if confirm.lower() == 'y':
                success = self.strategy_selector.start_strategy(strategy_name, custom_params)
                if success:
                    print(f"\nStarted strategy: {strategy_name}")
                    print("Use 'strategy_status' to check status.")
                    print("Use 'stop_strategy' to stop the strategy.")
                else:
                    print(f"\nFailed to start strategy: {strategy_name}")
            
        except Exception as e:
            print(f"\nError selecting strategy: {str(e)}")

    def do_strategy_status(self, arg):
        """
        Check the status of the currently running strategy
        Usage: strategy_status
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            active_strategy = self.strategy_selector.get_active_strategy()
            
            if not active_strategy:
                print("\nNo active trading strategy running.")
                print("Use 'select_strategy' to start a strategy.")
                return
            
            print(f"\n=== Active Strategy: {active_strategy['name']} ===")
            print(f"Module: {active_strategy['module']}")
            print(f"Status: {'Running' if active_strategy['running'] else 'Stopped'}")
            
            # Get strategy instance for more detailed status
            strategy_instance = self.strategy_selector.active_strategy["instance"]
            
            if hasattr(strategy_instance, 'get_status'):
                print(f"Current state: {strategy_instance.get_status()}")
            
            if hasattr(strategy_instance, 'get_performance_metrics'):
                metrics = strategy_instance.get_performance_metrics()
                if metrics:
                    print("\nPerformance Metrics:")
                    for key, value in metrics.items():
                        print(f"  {key}: {value}")
            
        except Exception as e:
            print(f"\nError checking strategy status: {str(e)}")

    def do_stop_strategy(self, arg):
        """
        Stop the currently running strategy
        Usage: stop_strategy
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            active_strategy = self.strategy_selector.get_active_strategy()
            
            if not active_strategy:
                print("\nNo active trading strategy to stop.")
                return
            
            print(f"\nStopping strategy: {active_strategy['name']}")
            
            success = self.strategy_selector.stop_strategy()
            
            if success:
                print("Strategy stopped successfully.")
            else:
                print("Failed to stop strategy.")
            
        except Exception as e:
            print(f"\nError stopping strategy: {str(e)}")

    def do_strategy_params(self, arg):
        """
        View or modify parameters of a strategy
        Usage: strategy_params [strategy_name]
        
        If no strategy name is provided, shows parameters of the active strategy.
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            strategy_name = arg.strip()
            
            # If no strategy name provided, use active strategy
            if not strategy_name:
                active_strategy = self.strategy_selector.get_active_strategy()
                
                if not active_strategy:
                    print("\nNo active strategy. Specify a strategy name or start a strategy first.")
                    return
                
                strategy_name = active_strategy['module']
            
            # Get strategy parameters
            params = self.strategy_selector.get_strategy_params(strategy_name)
            
            if not params:
                print(f"\nStrategy '{strategy_name}' has no configurable parameters or doesn't exist.")
                return
            
            print(f"\n=== '{strategy_name}' Parameters ===")
            
            for param_name, param_data in params.items():
                if isinstance(param_data, dict) and "value" in param_data:
                    value = param_data["value"]
                    description = param_data.get("description", "")
                    print(f"{param_name}: {value} - {description}")
                else:
                    print(f"{param_name}: {param_data}")
            
        except Exception as e:
            print(f"\nError getting strategy parameters: {str(e)}")

    def do_help_strategies(self, arg):
        """
        Show help for trading strategies
        Usage: help_strategies
        """
        print("\n=== Trading Strategies Help ===")
        print("\nElysium supports various automated trading strategies.")
        print("You can select, configure, and monitor these strategies using these commands:")
        
        print("\nCommands:")
        print("  select_strategy     - Select and configure a trading strategy")
        print("  strategy_status     - Check the status of the currently running strategy")
        print("  stop_strategy       - Stop the currently running strategy")
        print("  strategy_params     - View parameters of a strategy")
        
        print("\nBasic Workflow:")
        print("  1. Connect to the exchange using 'connect'")
        print("  2. View available strategies with 'select_strategy'")
        print("  3. Select and configure a strategy with 'select_strategy <name>'")
        print("  4. Monitor the strategy with 'strategy_status'")
        print("  5. Stop the strategy when done with 'stop_strategy'")
        
        print("\nAvailable Strategies:")
        strategies = self.strategy_selector.list_strategies()
        
        if not strategies:
            print("  No trading strategies available.")
            print("  Please make sure strategy files are in the 'strategies' directory.")
            return
        
        for strategy in strategies:
            print(f"  - {strategy['name']} ({strategy['module']})")
            print(f"    {strategy['description']}")