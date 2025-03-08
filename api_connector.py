import logging
from typing import Dict, Optional, Any, List
import hyperliquid

import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

class ApiConnector:
    """Handles connections to trading APIs and exchanges"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.wallet: Optional[LocalAccount] = None
        self.wallet_address: Optional[str] = None
        self.exchange: Optional[Exchange] = None
        self.info: Optional[Info] = None
        
    def connect_hyperliquid(self, wallet_address: str, secret_key: str, 
                           use_testnet: bool = False) -> bool:
        """
        Connect to Hyperliquid exchange
        
        Args:
            wallet_address: Wallet address for authentication
            secret_key: Secret key for authentication 
            use_testnet: Whether to use testnet (default is mainnet)
            
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.wallet_address = wallet_address
            api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
            
            # Initialize wallet
            self.wallet = eth_account.Account.from_key(secret_key)
            
            # Initialize exchange and info
            self.exchange = Exchange(
                self.wallet,
                api_url,
                account_address=self.wallet_address
            )
            self.info = Info(api_url)
            
            # Test connection by getting balances
            user_state = self.info.user_state(self.wallet_address)
            
            self.logger.info(f"Successfully connected to Hyperliquid {'(testnet)' if use_testnet else ''}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to Hyperliquid: {str(e)}")
            return False
    
    def get_balances(self) -> Dict[str, Any]:
        """Get all balances (spot and perpetual)"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return {"spot": [], "perp": {}}
        
        try:
            spot_state = self.info.spot_user_state(self.wallet_address)
            perp_state = self.info.user_state(self.wallet_address)
            
            # Format spot balances
            spot_balances = []
            for balance in spot_state.get("balances", []):
                spot_balances.append({
                    "asset": balance.get("coin", ""),
                    "available": float(balance.get("available", 0)),
                    "total": float(balance.get("total", 0)),
                    "in_orders": float(balance.get("total", 0)) - float(balance.get("available", 0))
                })
            
            # Format perpetual balances
            margin_summary = perp_state.get("marginSummary", {})
            perp_balances = {
                "account_value": float(margin_summary.get("accountValue", 0)),
                "margin_used": float(margin_summary.get("totalMarginUsed", 0)),
                "position_value": float(margin_summary.get("totalNtlPos", 0))
            }
            
            return {
                "spot": spot_balances,
                "perp": perp_balances
            }
        except Exception as e:
            self.logger.error(f"Error fetching balances: {str(e)}")
            return {"spot": [], "perp": {}}
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
        
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
                        "margin_used": float(position.get("marginUsed", 0))
                    })
            
            return positions
        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            return []
    
    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for a specific symbol"""
        if not self.info:
            self.logger.error("Not connected to exchange")
            return {}
        
        try:
            # Get order book
            order_book = self.info.l2_snapshot(symbol)
            
            # Get mid price from all_mids
            all_mids = self.info.all_mids()
            mid_price = all_mids.get(symbol, 0)
            
            return {
                "order_book": order_book,
                "mid_price": float(mid_price)
            }
        except Exception as e:
            self.logger.error(f"Error fetching market data: {str(e)}")
            return {}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders, optionally filtered by symbol"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            open_orders = self.info.open_orders(self.wallet_address)
            
            if symbol:
                open_orders = [order for order in open_orders if order["coin"] == symbol]
            
            return open_orders
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {str(e)}")
            return []
    
    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade history"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            fills = self.info.user_fills(self.wallet_address)
            return fills[:limit]
        except Exception as e:
            self.logger.error(f"Error fetching trade history: {str(e)}")
            return []