from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator, confloat, conint
from typing import Dict, Any, Optional
import logging

from order_handler import OrderHandler
from api.api_connector import ApiConnector
from api.models.perp_models import (
    PerpMarketOrderRequest,
    PerpLimitOrderRequest,
    SetLeverageRequest,
    OrderResponse
)
from api.utils.perp_utils import check_connection

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/perp",
    tags=["perpetual-trading"],
    responses={404: {"description": "Not found"}},
)

# Global instances
order_handler: Optional[OrderHandler] = None
api_connector: Optional[ApiConnector] = None

def set_instances(connector: ApiConnector, handler: OrderHandler) -> None:
    """
    Set the shared instances from main.py
    
    Args:
        connector: The API connector instance
        handler: The order handler instance
    """
    global api_connector, order_handler
    api_connector = connector
    order_handler = handler
    logger.info("Perpetual API instances set successfully")

# Request/Response Models
class PerpMarketOrderRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (e.g., 'BTC')",
        example="BTC"
    )
    size: confloat(gt=0) = Field(
        ..., 
        description="Order size",
        example=0.01
    )
    leverage: conint(gt=0, le=100) = Field(
        default=1, 
        description="Leverage to use (1-100)",
        example=5
    )
    slippage: confloat(ge=0, le=1) = Field(
        default=0.05, 
        description="Maximum allowed slippage (0-1)",
        example=0.05
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Additional validation for common trading pairs
        common_pairs = ['BTC', 'ETH', 'BNB', 'XRP']
        if v not in common_pairs:
            # If not a common pair, validate the format
            if not v.isalnum():
                raise ValueError('Invalid trading pair format. Use format like "BTC"')
        return v

class PerpLimitOrderRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (e.g., 'BTC')",
        example="BTC"
    )
    size: confloat(gt=0) = Field(
        ..., 
        description="Order size",
        example=0.01
    )
    price: confloat(gt=0) = Field(
        ..., 
        description="Order price",
        example=50000.0
    )
    leverage: conint(gt=0, le=100) = Field(
        default=1, 
        description="Leverage to use (1-100)",
        example=5
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Additional validation for common trading pairs
        common_pairs = ['BTC', 'ETH', 'BNB', 'XRP']
        if v not in common_pairs:
            # If not a common pair, validate the format
            if not v.isalnum():
                raise ValueError('Invalid trading pair format. Use format like "BTC"')
        return v

class SetLeverageRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (e.g., 'BTC')",
        example="BTC"
    )
    leverage: conint(gt=0, le=100) = Field(
        ..., 
        description="Leverage to set (1-100)",
        example=5
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Additional validation for common trading pairs
        common_pairs = ['BTC', 'ETH', 'BNB', 'XRP']
        if v not in common_pairs:
            # If not a common pair, validate the format
            if not v.isalnum():
                raise ValueError('Invalid trading pair format. Use format like "BTC"')
        return v

class OrderResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")

# API Endpoints
@router.post("/market-buy", response_model=OrderResponse)
async def perp_market_buy(request: PerpMarketOrderRequest) -> OrderResponse:
    """
    Execute a perpetual market buy order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC')
    - size: Order size (must be > 0)
    - leverage: Leverage to use (1-100)
    - slippage: Maximum allowed slippage (0-1)
    
    Returns:
        OrderResponse: Response containing order details and status
    """
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Executing perpetual market buy order for {request.symbol} on {network}")
        result = order_handler.perp_market_buy(
            symbol=request.symbol,
            size=request.size,
            leverage=request.leverage,
            slippage=request.slippage
        )
        
        logger.info(f"Perpetual market buy order executed successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"Perpetual market buy order executed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in perpetual market buy: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error executing perpetual market buy: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/market-sell", response_model=OrderResponse)
async def perp_market_sell(request: PerpMarketOrderRequest) -> OrderResponse:
    """
    Execute a perpetual market sell order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC')
    - size: Order size (must be > 0)
    - leverage: Leverage to use (1-100)
    - slippage: Maximum allowed slippage (0-1)
    
    Returns:
        OrderResponse: Response containing order details and status
    """
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Executing perpetual market sell order for {request.symbol} on {network}")
        result = order_handler.perp_market_sell(
            symbol=request.symbol,
            size=request.size,
            leverage=request.leverage,
            slippage=request.slippage
        )
        
        logger.info(f"Perpetual market sell order executed successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"Perpetual market sell order executed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in perpetual market sell: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error executing perpetual market sell: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/limit-buy", response_model=OrderResponse)
async def perp_limit_buy(request: PerpLimitOrderRequest) -> OrderResponse:
    """
    Place a perpetual limit buy order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC')
    - size: Order size (must be > 0)
    - price: Order price (must be > 0)
    - leverage: Leverage to use (1-100)
    
    Returns:
        OrderResponse: Response containing order details and status
    """
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Placing perpetual limit buy order for {request.symbol} on {network}")
        result = order_handler.perp_limit_buy(
            symbol=request.symbol,
            size=request.size,
            price=request.price,
            leverage=request.leverage
        )
        
        logger.info(f"Perpetual limit buy order placed successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"Perpetual limit buy order placed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in perpetual limit buy: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error placing perpetual limit buy: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/limit-sell", response_model=OrderResponse)
async def perp_limit_sell(request: PerpLimitOrderRequest) -> OrderResponse:
    """
    Place a perpetual limit sell order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC')
    - size: Order size (must be > 0)
    - price: Order price (must be > 0)
    - leverage: Leverage to use (1-100)
    
    Returns:
        OrderResponse: Response containing order details and status
    """
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Placing perpetual limit sell order for {request.symbol} on {network}")
        result = order_handler.perp_limit_sell(
            symbol=request.symbol,
            size=request.size,
            price=request.price,
            leverage=request.leverage
        )
        
        logger.info(f"Perpetual limit sell order placed successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"Perpetual limit sell order placed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in perpetual limit sell: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error placing perpetual limit sell: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/set-leverage", response_model=OrderResponse)
async def set_leverage(request: SetLeverageRequest) -> OrderResponse:
    """
    Set leverage for a perpetual trading pair
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC')
    - leverage: Leverage to set (1-100)
    
    Returns:
        OrderResponse: Response containing leverage setting details and status
    """
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Setting leverage for {request.symbol} on {network}")
        result = order_handler._set_leverage(
            symbol=request.symbol,
            leverage=request.leverage
        )
        
        logger.info(f"Leverage set successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"Leverage set successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in setting leverage: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error setting leverage: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) 