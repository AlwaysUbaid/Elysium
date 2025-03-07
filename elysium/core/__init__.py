# Initialize the module
"""
Core module for Elysium trading platform.

This module contains the core components for exchange connection,
authentication, wallet management, and other essential functionality.
"""

import eth_account
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple

from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.utils.signing import get_timestamp_ms

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("elysium.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ElysiumExchange:
    """Main exchange connection class for Elysium."""

    def __init__(self, wallet_address: str, secret_key: str, use_testnet: bool = False):
        """
        Initialize exchange connection.

        Args:
            wallet_address: Wallet address for the Hyperliquid account
            secret_key: Private key for the wallet
            use_testnet: Whether to use testnet instead of mainnet
        """
        self.wallet_address = wallet_address
        self.api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
        self.use_testnet = use_testnet

        # Initialize wallet and exchange
        self.wallet: LocalAccount = eth_account.Account.from_key(secret_key)
        self.exchange = Exchange(
            self.wallet,
            self.api_url,
            account_address=wallet_address
        )
        self.info = Info(self.api_url)

        logger.info(f"Initialized Elysium exchange connection for address: {self.wallet_address}")
        logger.info(f"Connected to: {'Testnet' if use_testnet else 'Mainnet'}")

    def get_balances(self) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """
        Get account balances across spot and perpetual markets.

        Returns:
            Tuple containing spot balances and perpetual account summary
        """
        try:
            spot_balances: Dict[str, float] = {}
            spot_state = self.info.spot_user_state(self.wallet_address)

            for balance in spot_state.get("balances", []):
                coin = balance.get("coin", "")
                if coin:
                    spot_balances[coin] = {
                        "available": float(balance.get("available", 0)),
                        "total": float(balance.get("total", 0))
                    }

            perp_state = self.info.user_state(self.wallet_address)
            perp_summary = perp_state.get("marginSummary", {})

            return spot_balances, perp_summary

        except Exception as e:
            logger.error(f"Error fetching balances: {str(e)}")
            return {}, {}

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.

        Returns:
            List of position dictionaries
        """
        try:
            perp_state = self.info.user_state(self.wallet_address)
            positions = []

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
                        "margin_used": float(position.get("marginUsed", 0)),
                    })

            return positions

        except Exception as e:
            logger.error(f"Error fetching positions: {str(e)}")
            return []

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get open orders.

        Returns:
            List of open order dictionaries
        """
        try:
            orders = self.info.open_orders(self.wallet_address)
            formatted_orders = []

            for order in orders:
                formatted_orders.append({
                    "symbol": order.get("coin", ""),
                    "side": "Buy" if order.get("side", "") == "B" else "Sell",
                    "size": float(order.get("sz", 0)),
                    "price": float(order.get("limitPx", 0)),
                    "order_id": order.get("oid", 0),
                    "timestamp": datetime.fromtimestamp(order.get("timestamp", 0) / 1000)
                })

            return formatted_orders

        except Exception as e:
            logger.error(f"Error fetching open orders: {str(e)}")
            return []

    def place_limit_order(self, symbol: str, is_buy: bool, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit order.

        Args:
            symbol: Trading symbol (e.g., "ETH" or "@140" for HWTR/USDC)
            is_buy: True for buy, False for sell
            size: Order size
            price: Order price

        Returns:
            Order result dictionary
        """
        try:
            order_result = self.exchange.order(
                symbol,
                is_buy,
                size,
                price,
                {"limit": {"tif": "Gtc"}}
            )

            if order_result["status"] == "ok":
                logger.info(f"Placed {'buy' if is_buy else 'sell'} order: {size} {symbol} @ {price}")
            else:
                logger.error(f"Order placement failed: {order_result}")

            return order_result

        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return {"status": "error", "message": str(e)}

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel

        Returns:
            Cancel result dictionary
        """
        try:
            cancel_result = self.exchange.cancel(symbol, order_id)

            if cancel_result["status"] == "ok":
                logger.info(f"Cancelled order {order_id} for {symbol}")
            else:
                logger.error(f"Order cancellation failed: {cancel_result}")

            return cancel_result

        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
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
            open_orders = self.info.open_orders(self.wallet_address)
            cancelled_count = 0

            for order in open_orders:
                if symbol is None or order["coin"] == symbol:
                    cancel_result = self.exchange.cancel(order["coin"], order["oid"])
                    if cancel_result["status"] == "ok":
                        cancelled_count += 1
                        logger.info(f"Cancelled order {order['oid']} for {order['coin']}")

            return cancelled_count

        except Exception as e:
            logger.error(f"Error cancelling orders: {str(e)}")
            return 0