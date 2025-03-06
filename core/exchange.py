# Exchange module
"""
Exchange connection manager for Hyperliquid API interaction.
Handles authentication, order placement, and API requests.
"""

import logging
from typing import Dict, Any, Optional, List

import eth_account
from eth_account.signers.local import LocalAccount

from hyperliquid.exchange import Exchange as HyperliquidExchange
from hyperliquid.info import Info
from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL
from hyperliquid.utils.types import BuilderInfo

from elysium.utils.constants import DEFAULT_SLIPPAGE
from elysium.rebates.rebate_manager import RebateManager


class ExchangeManager:
    """
    Manages exchange connections and provides a unified interface
    for interacting with exchange APIs.
    """

    def __init__(self,
                 wallet: LocalAccount,
                 account_address: Optional[str] = None,
                 base_url: str = MAINNET_API_URL,
                 use_rebates: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the exchange manager.

        Args:
            wallet: Ethereum wallet for signing transactions
            account_address: Optional account address (if different from wallet)
            base_url: API URL (mainnet or testnet)
            use_rebates: Whether to use the rebate system
            logger: Optional logger instance
        """
        self.wallet = wallet
        self.account_address = account_address or wallet.address
        self.base_url = base_url
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Initialize exchange connection
        self.exchange = HyperliquidExchange(
            wallet=wallet,
            base_url=base_url,
            account_address=self.account_address
        )

        # Initialize info client
        self.info = Info(base_url=base_url)

        # Initialize rebate manager if enabled
        self.rebate_manager = RebateManager(self.exchange, self.info) if use_rebates else None
        self.use_rebates = use_rebates

        self.logger.info(f"Exchange manager initialized for account: {self.account_address}")

    def place_order(self,
                    coin: str,
                    is_buy: bool,
                    size: float,
                    price: float,
                    order_type: Dict[str, Any],
                    reduce_only: bool = False,
                    use_rebate: bool = True) -> Dict[str, Any]:
        """
        Place an order on the exchange.

        Args:
            coin: Trading pair symbol
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            price: Order price
            order_type: Order type configuration (limit, market, etc.)
            reduce_only: Whether this order should be reduce-only
            use_rebate: Whether to apply rebate optimizations to this order

        Returns:
            Order response from the exchange
        """
        builder_info = None

        # Apply rebate optimization if enabled
        if self.use_rebates and use_rebate and self.rebate_manager:
            builder_info = self.rebate_manager.select_best_builder(
                coin=coin,
                order_type=str(order_type),
                is_buy=is_buy,
                size=size
            )

        # Place the order
        response = self.exchange.order(
            name=coin,
            is_buy=is_buy,
            sz=size,
            limit_px=price,
            order_type=order_type,
            reduce_only=reduce_only,
            builder=builder_info
        )

        # Log the result
        if response.get("status") == "ok":
            self.logger.info(
                f"Order placed: {coin} {'BUY' if is_buy else 'SELL'} {size} @ {price}"
            )
            # Update rebate metrics if used
            if builder_info and self.rebate_manager:
                self.rebate_manager.update_builder_metrics(
                    builder_address=builder_info["b"],
                    success=True,
                    fees_paid=0.0  # Will be updated with actual fees later
                )
        else:
            self.logger.error(f"Order failed: {response}")

        return response

    def market_order(self,
                     coin: str,
                     is_buy: bool,
                     size: float,
                     slippage: float = DEFAULT_SLIPPAGE,
                     reduce_only: bool = False,
                     use_rebate: bool = True) -> Dict[str, Any]:
        """
        Place a market order by creating an aggressive IOC limit order.

        Args:
            coin: Trading pair symbol
            is_buy: Whether this is a buy (True) or sell (False) order
            size: Order size
            slippage: Maximum acceptable slippage (default: 0.05 or 5%)
            reduce_only: Whether this order should be reduce-only
            use_rebate: Whether to apply rebate optimizations

        Returns:
            Order response from the exchange
        """
        # Get current market price
        mid_price = float(self.info.all_mids().get(coin, 0))
        if mid_price == 0:
            self.logger.error(f"Could not get price for {coin}")
            return {"status": "error", "message": f"Could not get price for {coin}"}

        # Calculate aggressive price with slippage
        price = mid_price * (1 + slippage) if is_buy else mid_price * (1 - slippage)

        # Place IOC order (Immediate-or-Cancel)
        return self.place_order(
            coin=coin,
            is_buy=is_buy,
            size=size,
            price=price,
            order_type={"limit": {"tif": "Ioc"}},
            reduce_only=reduce_only,
            use_rebate=use_rebate
        )

    def cancel_order(self, coin: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order by its ID.

        Args:
            coin: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation response from the exchange
        """
        response = self.exchange.cancel(coin, order_id)

        if response.get("status") == "ok":
            self.logger.info(f"Order {order_id} cancelled for {coin}")
        else:
            self.logger.error(f"Failed to cancel order {order_id}: {response}")

        return response

    def cancel_all_orders(self, coin: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Cancel all open orders, optionally filtered by coin.

        Args:
            coin: Optional coin to filter by (if None, cancels all orders)

        Returns:
            List of cancellation responses
        """
        open_orders = self.info.open_orders(self.account_address)
        results = []

        for order in open_orders:
            if coin is None or order.get("coin") == coin:
                result = self.cancel_order(order.get("coin"), order.get("oid"))
                results.append(result)

        return results

    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get account balance information.

        Returns:
            Account balance data
        """
        return {
            "spot": self.info.spot_user_state(self.account_address),
            "perp": self.info.user_state(self.account_address)
        }