import cmd
import os
import time
import threading
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

    Advanced Order Strategies:
    - scaled_buy          Place multiple buy orders across a price range
    - scaled_sell         Place multiple sell orders across a price range
    - market_scaled_buy   Place multiple buy orders based on current market prices
    - market_scaled_sell  Place multiple sell orders based on current market prices
    - perp_scaled_buy     Place multiple perpetual buy orders across a price range
    - perp_scaled_sell    Place multiple perpetual sell orders across a price range
    - help_scaled         Show detailed help for scaled orders
    - help_market_scaled  Show detailed help for market-aware scaled orders

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

    # ================================Scaled Order Part=====================================
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
    # ================================Scaled Market order=====================================
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