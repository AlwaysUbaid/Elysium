import logging
import time
from typing import Dict, Optional, List, Union, Any

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

class OrderHandler:
    """Handles all order execution for Elysium Trading Platform"""
    
    def __init__(self, exchange: Optional[Exchange], info: Optional[Info]):
        self.exchange = exchange
        self.info = info
        self.wallet_address = None
        self.logger = logging.getLogger(__name__)
        
    def market_buy(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a market buy order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Executing market buy: {size} {symbol}")
            result = self.exchange.market_open(symbol, True, size, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Market buy executed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Market buy error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error in market buy: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def market_sell(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a market sell order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Executing market sell: {size} {symbol}")
            result = self.exchange.market_open(symbol, False, size, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Market sell executed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Market sell error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error in market sell: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit buy order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Placing limit buy: {size} {symbol} @ {price}")
            result = self.exchange.order(symbol, True, size, price, {"limit": {"tif": "Gtc"}})
            
            if result["status"] == "ok":
                status = result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.logger.info(f"Limit buy placed: order ID {oid}")
            return result
        except Exception as e:
            self.logger.error(f"Error in limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit sell order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Placing limit sell: {size} {symbol} @ {price}")
            result = self.exchange.order(symbol, False, size, price, {"limit": {"tif": "Gtc"}})
            
            if result["status"] == "ok":
                status = result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.logger.info(f"Limit sell placed: order ID {oid}")
            return result
        except Exception as e:
            self.logger.error(f"Error in limit sell: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel a specific order
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            result = self.exchange.cancel(symbol, order_id)
            
            if result["status"] == "ok":
                self.logger.info(f"Order {order_id} cancelled successfully")
            else:
                self.logger.error(f"Failed to cancel order {order_id}: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter cancellations
            
        Returns:
            Dictionary with cancellation results
        """
        if not self.exchange or not self.info or not self.wallet_address:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Cancelling all orders{' for ' + symbol if symbol else ''}")
            open_orders = self.info.open_orders(self.wallet_address)
            
            results = {"cancelled": 0, "failed": 0, "details": []}
            for order in open_orders:
                if symbol is None or order["coin"] == symbol:
                    result = self.cancel_order(order["coin"], order["oid"])
                    if result["status"] == "ok":
                        results["cancelled"] += 1
                    else:
                        results["failed"] += 1
                    results["details"].append(result)
                    
            self.logger.info(f"Cancelled {results['cancelled']} orders, {results['failed']} failed")
            return {"status": "ok", "data": results}
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter results
            
        Returns:
            List of open orders
        """
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
            
        try:
            open_orders = self.info.open_orders(self.wallet_address)
            
            if symbol:
                open_orders = [order for order in open_orders if order["coin"] == symbol]
                
            return open_orders
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            return []
    
    def market_close_position(self, symbol: str, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Close an entire position for a symbol
        
        Args:
            symbol: Trading pair symbol
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Closing position for {symbol}")
            result = self.exchange.market_close(symbol, None, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Position closed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Position close error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return {"status": "error", "message": str(e)}