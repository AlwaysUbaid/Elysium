from fastapi import HTTPException
from typing import Optional
import logging

from order_handler import OrderHandler
from api.api_connector import ApiConnector

# Setup logging
logger = logging.getLogger(__name__)

def check_connection(api_connector: Optional[ApiConnector], order_handler: Optional[OrderHandler]) -> None:
    """
    Check if connected to exchange and raise appropriate error if not
    
    Args:
        api_connector: The API connector instance
        order_handler: The order handler instance
        
    Raises:
        HTTPException: If connection checks fail
    """
    if not api_connector:
        logger.error("API connector not initialized")
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "API connector not initialized",
                "required_action": "Call POST /connect with your wallet credentials first",
                "current_network": "unknown"
            }
        )
        
    if not api_connector.is_connected():
        logger.error("Not connected to exchange")
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Not connected to exchange. Please connect first using the /connect endpoint",
                "required_action": "Call POST /connect with your wallet credentials first",
                "current_network": api_connector.is_testnet() and "testnet" or "mainnet"
            }
        )
    
    if not order_handler:
        logger.error("Order handler not initialized")
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Order handler not initialized",
                "required_action": "Call POST /connect with your wallet credentials first",
                "current_network": api_connector.is_testnet() and "testnet" or "mainnet"
            }
        )
    
    # Ensure order handler is properly configured for current network
    if not order_handler.exchange or not order_handler.info:
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        logger.error(f"Order handler not configured for {network}")
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"Order handler not configured for {network}. Please reconnect.",
                "required_action": "Call POST /connect again to reconfigure the order handler",
                "current_network": network
            }
        )
    
    # Ensure wallet address is set
    if not order_handler.wallet_address:
        logger.error("Wallet address not set")
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Wallet address not set. Please reconnect.",
                "required_action": "Call POST /connect again to set the wallet address",
                "current_network": api_connector.is_testnet() and "testnet" or "mainnet"
            }
        ) 