"""
Market data handling for the Elysium trading platform.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Callable


class MarketData:
    """
    Handles market data retrieval and processing.
    """

    def __init__(self, info, logger: Optional[logging.Logger] = None):
        """
        Initialize the market data handler.
        
        Args:
            info: Hyperliquid Info instance
            logger: Optional logger instance
        """
        self.info = info
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.subscriptions = {}
        self.orderbooks = {}
        self.midprices = {}
        
    def get_mid_price(self, symbol: str, force_refresh: bool = False) -> float:
        """
        Get current mid price for a symbol.
        
        Args:
            symbol: Trading symbol
            force_refresh: Whether to force a refresh from the API
            
        Returns:
            Mid price or 0 if not available
        """
        try:
            if force_refresh or symbol not in self.midprices:
                # Get all midprices
                mids = self.info.all_mids()
                
                # Clean up the symbol for Hyperliquid API
                clean_symbol = symbol.replace('/', '')
                if symbol.startswith('@'):
                    # This is an index-based symbol, need to handle specially
                    if symbol == '@140':  # HWTR/USDC
                        # Use HWTR midprice if available
                        if "HWTR" in mids:
                            self.midprices[symbol] = float(mids["HWTR"])
                            return self.midprices[symbol]
                
                # Try to get the mid price
                if symbol in mids:
                    self.midprices[symbol] = float(mids[symbol])
                else:
                    # Symbol not found, try to check if it's in a different format
                    for key, value in mids.items():
                        if key.lower() == clean_symbol.lower():
                            self.midprices[symbol] = float(value)
                            return self.midprices[symbol]
                    
                    # If still not found, return 0
                    return 0.0
            
            return self.midprices.get(symbol, 0.0)
            
        except Exception as e:
            self.logger.error(f"Error getting mid price for {symbol}: {str(e)}")
            return 0.0
    
    def get_best_bid_ask(self, symbol: str) -> Tuple[float, float]:
        """
        Get best bid and ask for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Tuple of (best_bid, best_ask) or (0, 0) if not available
        """
        try:
            orderbook = self.info.l2_snapshot(symbol)
            
            if orderbook and "levels" in orderbook and len(orderbook["levels"]) >= 2:
                bids = orderbook["levels"][0]
                asks = orderbook["levels"][1]
                
                if bids and asks:
                    best_bid = float(bids[0]["px"])
                    best_ask = float(asks[0]["px"])
                    return best_bid, best_ask
            
            return 0.0, 0.0
            
        except Exception as e:
            self.logger.error(f"Error getting best bid/ask for {symbol}: {str(e)}")
            return 0.0, 0.0
    
    def subscribe_to_orderbook(self, symbol: str, callback: Callable[[Dict[str, Any]], None]) -> int:
        """
        Subscribe to orderbook updates for a symbol.
        
        Args:
            symbol: Trading symbol
            callback: Callback function for updates
            
        Returns:
            Subscription ID or -1 if failed
        """
        try:
            subscription_id = self.info.subscribe(
                {"type": "l2Book", "coin": symbol},
                callback
            )
            
            if subscription_id > 0:
                self.subscriptions[symbol] = subscription_id
                self.logger.info(f"Subscribed to orderbook for {symbol}")
            
            return subscription_id
            
        except Exception as e:
            self.logger.error(f"Error subscribing to orderbook for {symbol}: {str(e)}")
            return -1
    
    def unsubscribe_from_orderbook(self, symbol: str) -> bool:
        """
        Unsubscribe from orderbook updates for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if symbol in self.subscriptions:
                subscription_id = self.subscriptions[symbol]
                result = self.info.unsubscribe(
                    {"type": "l2Book", "coin": symbol},
                    subscription_id
                )
                
                if result:
                    del self.subscriptions[symbol]
                    self.logger.info(f"Unsubscribed from orderbook for {symbol}")
                
                return result
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error unsubscribing from orderbook for {symbol}: {str(e)}")
            return False