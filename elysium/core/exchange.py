"""
Exchange connection manager for Hyperliquid API interaction.
Handles authentication, order placement, and API requests.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

import eth_account
from eth_account.signers.local import LocalAccount

from hyperliquid.exchange import Exchange as HyperliquidExchange
from hyperliquid.info import Info
from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL


class ExchangeManager:
    """
    Manages exchange connections and provides a unified interface
    for interacting with the Hyperliquid API.
    """

    def __init__(self,
             wallet_address: str = None,
             private_key: str = None,
             wallet = None,  # Add this parameter
             account_address: Optional[str] = None,
             base_url: str = None,
             use_testnet: bool = True,
             use_rebates: bool = True,
             logger: Optional[logging.Logger] = None):
        """
        Initialize the exchange manager.

        Args:
            wallet_address: Wallet address for the account
            private_key: Private key for the wallet
            wallet: Direct wallet object (alternative to private_key)
            account_address: Optional account address if different from wallet
            base_url: API URL (if None, will use testnet or mainnet based on use_testnet)
            use_testnet: Whether to use testnet instead of mainnet
            use_rebates: Whether to use the rebate system
            logger: Optional logger instance
        """
        # Store the wallet_address parameter
        self.wallet_address = wallet_address
        self.use_testnet = use_testnet
        self.base_url = base_url or (TESTNET_API_URL if use_testnet else MAINNET_API_URL)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # Initialize wallet
        if wallet:
            self.wallet = wallet
        elif private_key:
            self.wallet = eth_account.Account.from_key(private_key)
        else:
            raise ValueError("Either wallet or private_key must be provided")
            
        # Use provided account address or wallet address
        self.account_address = account_address or self.wallet_address or self.wallet.address
        
        # Initialize exchange connection
        self.exchange = HyperliquidExchange(
            wallet=self.wallet,
            base_url=self.base_url,
            account_address=self.account_address
        )

        # Initialize info client
        self.info = Info(base_url=self.base_url)
        
        self.logger.info(f"Exchange manager initialized for account: {self.account_address}")

    def get_balances(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Get account balances across spot and perpetual markets.

        Returns:
            Tuple containing spot balances and perpetual account summary
        """
        try:
            # Get spot balances
            spot_state = self.info.spot_user_state(self.account_address)
            
            # Get perpetual state
            perp_state = self.info.user_state(self.account_address)
            
            return spot_state, perp_state
        except Exception as e:
            self.logger.error(f"Error fetching balances: {str(e)}")
            return {}, {}

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.

        Returns:
            List of positions
        """
        try:
            perp_state = self.info.user_state(self.account_address)
            positions = []

            for asset_position in perp_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                # Only include non-zero positions
                if float(position.get("szi", 0)) != 0:
                    positions.append({
                        "symbol": position.get("coin", ""),
                        "size": float(position.get("szi", 0)),
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0) if "markPx" in position else 0),
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0)),
                    })

            return positions
        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            return []

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get open orders.

        Returns:
            List of open orders
        """
        try:
            orders = self.info.open_orders(self.account_address)
            formatted_orders = []

            for order in orders:
                formatted_orders.append({
                    "symbol": order.get("coin", ""),
                    "side": "Buy" if order.get("side", "") == "B" else "Sell",
                    "size": float(order.get("sz", 0)),
                    "price": float(order.get("limitPx", 0)),
                    "order_id": order.get("oid", 0),
                    "timestamp": order.get("timestamp", 0)
                })

            return formatted_orders
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {str(e)}")
            return []

    def place_limit_order(self, 
                         symbol: str, 
                         is_buy: bool, 
                         size: float, 
                         price: float,
                         post_only: bool = False,
                         reduce_only: bool = False) -> Dict[str, Any]:
        """
        Place a limit order.

        Args:
            symbol: Trading pair symbol
            is_buy: Whether this is a buy order
            size: Order size
            price: Limit price
            post_only: Whether the order must be maker only (ALO)
            reduce_only: Whether the order should only reduce position

        Returns:
            Order response
        """
        try:
            # Determine time-in-force option
            tif = "Alo" if post_only else "Gtc"
            
            # Place the order
            order_result = self.exchange.order(
                name=symbol,
                is_buy=is_buy,
                sz=size,
                limit_px=price,
                order_type={"limit": {"tif": tif}},
                reduce_only=reduce_only
            )
            
            if order_result["status"] == "ok":
                self.logger.info(f"Placed {'buy' if is_buy else 'sell'} order for {size} {symbol} @ {price}")
            else:
                self.logger.error(f"Order placement failed: {order_result}")
                
            return order_result
        except Exception as e:
            self.logger.error(f"Error placing limit order: {str(e)}")
            return {"status": "error", "message": str(e)}

    def place_market_order(self,
                          symbol: str,
                          is_buy: bool,
                          size: float,
                          slippage: float = 0.05,  # 5% default slippage for market orders
                          reduce_only: bool = False) -> Dict[str, Any]:
        """
        Place a market order (implemented as an aggressive IOC limit order).

        Args:
            symbol: Trading pair symbol
            is_buy: Whether this is a buy order
            size: Order size
            slippage: Maximum acceptable slippage (default: 0.05 or 5%)
            reduce_only: Whether the order should only reduce position

        Returns:
            Order response
        """
        try:
            # Get aggressive Market Price
            return self.exchange.market_open(
                name=symbol,
                is_buy=is_buy,
                sz=size,
                slippage=slippage,
                reduce_only=reduce_only
            )
        except Exception as e:
            self.logger.error(f"Error placing market order: {str(e)}")
            return {"status": "error", "message": str(e)}

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        try:
            cancel_result = self.exchange.cancel(symbol, order_id)
            
            if cancel_result["status"] == "ok":
                self.logger.info(f"Cancelled order {order_id} for {symbol}")
            else:
                self.logger.error(f"Order cancellation failed: {cancel_result}")
                
            return cancel_result
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"status": "error", "message": str(e)}

    def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders by

        Returns:
            Number of orders cancelled
        """
        try:
            open_orders = self.info.open_orders(self.account_address)
            cancelled_count = 0
            
            for order in open_orders:
                if symbol is None or order["coin"] == symbol:
                    cancel_result = self.exchange.cancel(order["coin"], order["oid"])
                    if cancel_result["status"] == "ok":
                        cancelled_count += 1
                        self.logger.info(f"Cancelled order {order['oid']} for {order['coin']}")
            
            return cancelled_count
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")
            return 0

    def subscribe_to_orderbook(self, symbol: str, callback) -> int:
        """
        Subscribe to orderbook updates for a symbol.

        Args:
            symbol: Trading pair symbol
            callback: Callback function for updates

        Returns:
            Subscription ID
        """
        try:
            subscription_id = self.info.subscribe(
                {"type": "l2Book", "coin": symbol},
                callback
            )
            self.logger.info(f"Subscribed to orderbook for {symbol}")
            return subscription_id
        except Exception as e:
            self.logger.error(f"Error subscribing to orderbook: {str(e)}")
            return -1