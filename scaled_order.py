import logging
import time
from typing import Dict, Optional, List, Union, Any

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

import order_handler
from order_handler import OrderHandler

class scaledOrder:
    def __init__(self, exchange: Optional[Exchange], info: Optional[Info]):
        self.exchange = exchange
        self.info = info
        self.wallet_address = None
        self.logger = logging.getLogger(__name__)

    def scaledExe(self, symbol: str, isBuy:bool, size: float, nOrders:float, startPrice:float, endPrice:float, skew:float) -> Dict[str, Any]:
        """
        Place a scaled buy order

        Args:
            symbol: Trading pair symbol
            isBuy: if true, them buy, if false, then sell
            size: Order size
            nOrders:
            startPrice: start price
            endPrice: end price
            skew : skew

        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
        try:
            self.logger.info(f"Placing scaled order: {size} {symbol} {nOrders}@ {startPrice}-{endPrice}")
            diff = (endPrice-startPrice)/nOrders
            currentPrice = startPrice
            if isBuy == True:
                results = [order_handler.OrderHandler.limit_buy(self, symbol, size/nOrders, currentPrice) for _ in range(nOrders)]
                currentPrice = startPrice + diff
            elif isBuy == True:
                results = [order_handler.OrderHandler.limit_buy(self, symbol, size / nOrders, currentPrice) for _ in range(nOrders)]
                currentPrice = startPrice + diff
            return results
        except Exception as e:
            self.logger.error(f"Error in limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
