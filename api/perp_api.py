from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator, confloat, conint
import re

from order_handler import OrderHandler
from api.api_connector import ApiConnector

router = APIRouter(prefix="/api/v1/perp", tags=["perp"])

# Constants for validation
MIN_ORDER_SIZE = 0.0001
MAX_ORDER_SIZE = 1000.0
MIN_PRICE = 0.0001
MAX_PRICE = 1000000.0
MIN_SLIPPAGE = 0.0
MAX_SLIPPAGE = 1.0
MIN_LEVERAGE = 1
MAX_LEVERAGE = 100

# These will be set by main.py
api_connector = None
order_handler = None

def set_instances(connector: ApiConnector, handler: OrderHandler):
    """Set the shared instances from main.py"""
    global api_connector, order_handler
    api_connector = connector
    order_handler = handler

def check_connection():
    """Check if connected to exchange and raise appropriate error if not"""
    if not api_connector.is_connected():
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Not connected to exchange. Please connect first using the /connect endpoint",
                "required_action": "Call POST /connect with your wallet credentials first",
                "current_network": api_connector.is_testnet() and "testnet" or "mainnet"
            }
        )
    
    # Ensure order handler is properly configured for current network
    if not order_handler.exchange or not order_handler.info:
        network = "testnet" if api_connector.is_testnet() else "mainnet"
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
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Wallet address not set. Please reconnect.",
                "required_action": "Call POST /connect again to set the wallet address",
                "current_network": api_connector.is_testnet() and "testnet" or "mainnet"
            }
        )

# Request Models
class MarketOrderRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (can be any arbitrary value)",
        example="BTC-PERP"
    )
    size: confloat(gt=MIN_ORDER_SIZE, le=MAX_ORDER_SIZE) = Field(
        ..., 
        description=f"Order size (between {MIN_ORDER_SIZE} and {MAX_ORDER_SIZE})",
        example=0.1
    )
    leverage: conint(ge=MIN_LEVERAGE, le=MAX_LEVERAGE) = Field(
        default=1,
        description=f"Leverage to use (between {MIN_LEVERAGE} and {MAX_LEVERAGE})",
        example=1
    )
    slippage: confloat(ge=MIN_SLIPPAGE, le=MAX_SLIPPAGE) = Field(
        default=0.05, 
        description=f"Maximum allowed slippage (between {MIN_SLIPPAGE} and {MAX_SLIPPAGE})",
        example=0.05
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Accept any non-empty string for perpetual trading pairs
        if not v or not isinstance(v, str):
            raise ValueError('Symbol must be a non-empty string')
        return v

class LimitOrderRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (can be any arbitrary value)",
        example="BTC-PERP"
    )
    size: confloat(gt=MIN_ORDER_SIZE, le=MAX_ORDER_SIZE) = Field(
        ..., 
        description=f"Order size (between {MIN_ORDER_SIZE} and {MAX_ORDER_SIZE})",
        example=0.1
    )
    price: confloat(gt=MIN_PRICE, le=MAX_PRICE) = Field(
        ..., 
        description=f"Order price (between {MIN_PRICE} and {MAX_PRICE})",
        example=50000.0
    )
    leverage: conint(ge=MIN_LEVERAGE, le=MAX_LEVERAGE) = Field(
        default=1,
        description=f"Leverage to use (between {MIN_LEVERAGE} and {MAX_LEVERAGE})",
        example=1
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Accept any non-empty string for perpetual trading pairs
        if not v or not isinstance(v, str):
            raise ValueError('Symbol must be a non-empty string')
        return v

class ClosePositionRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (can be any arbitrary value)",
        example="BTC-PERP"
    )
    slippage: confloat(ge=MIN_SLIPPAGE, le=MAX_SLIPPAGE) = Field(
        default=0.05, 
        description=f"Maximum allowed slippage (between {MIN_SLIPPAGE} and {MAX_SLIPPAGE})",
        example=0.05
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Accept any non-empty string for perpetual trading pairs
        if not v or not isinstance(v, str):
            raise ValueError('Symbol must be a non-empty string')
        return v

class SetLeverageRequest(BaseModel):
    symbol: str = Field(
        ..., 
        description="Trading pair symbol (can be any arbitrary value)",
        example="BTC-PERP"
    )
    leverage: conint(ge=MIN_LEVERAGE, le=MAX_LEVERAGE) = Field(
        ..., 
        description=f"Leverage to set (between {MIN_LEVERAGE} and {MAX_LEVERAGE})",
        example=1
    )

    @validator('symbol')
    def validate_symbol(cls, v):
        # Accept any non-empty string for perpetual trading pairs
        if not v or not isinstance(v, str):
            raise ValueError('Symbol must be a non-empty string')
        return v

# Response Models
class OrderResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")

@router.post("/market-buy", response_model=OrderResponse)
async def perp_market_buy(request: MarketOrderRequest):
    """
    Execute a perpetual market buy order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC/USDT')
    - size: Order size (0.0001-1000)
    - leverage: Leverage to use (1-100)
    - slippage: Maximum allowed slippage (0-1)
    """
    try:
        check_connection()
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        result = order_handler.perp_market_buy(
            symbol=request.symbol,
            size=request.size,
            leverage=request.leverage,
            slippage=request.slippage
        )
        return OrderResponse(
            success=True,
            message=f"Perpetual market buy order executed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/market-sell", response_model=OrderResponse)
async def perp_market_sell(request: MarketOrderRequest):
    """
    Execute a perpetual market sell order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC/USDT')
    - size: Order size (0.0001-1000)
    - leverage: Leverage to use (1-100)
    - slippage: Maximum allowed slippage (0-1)
    """
    try:
        check_connection()
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        result = order_handler.perp_market_sell(
            symbol=request.symbol,
            size=request.size,
            leverage=request.leverage,
            slippage=request.slippage
        )
        return OrderResponse(
            success=True,
            message=f"Perpetual market sell order executed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/limit-buy", response_model=OrderResponse)
async def perp_limit_buy(request: LimitOrderRequest):
    """
    Place a perpetual limit buy order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC/USDT')
    - size: Order size (0.0001-1000)
    - price: Order price (0.0001-1000000)
    - leverage: Leverage to use (1-100)
    """
    try:
        check_connection()
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        result = order_handler.perp_limit_buy(
            symbol=request.symbol,
            size=request.size,
            price=request.price,
            leverage=request.leverage
        )
        return OrderResponse(
            success=True,
            message=f"Perpetual limit buy order placed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/limit-sell", response_model=OrderResponse)
async def perp_limit_sell(request: LimitOrderRequest):
    """
    Place a perpetual limit sell order
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC/USDT')
    - size: Order size (0.0001-1000)
    - price: Order price (0.0001-1000000)
    - leverage: Leverage to use (1-100)
    """
    try:
        check_connection()
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        result = order_handler.perp_limit_sell(
            symbol=request.symbol,
            size=request.size,
            price=request.price,
            leverage=request.leverage
        )
        return OrderResponse(
            success=True,
            message=f"Perpetual limit sell order placed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/close-position", response_model=OrderResponse)
async def close_position(request: ClosePositionRequest):
    """
    Close an entire position for a symbol
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC/USDT')
    - slippage: Maximum allowed slippage (0-1)
    """
    try:
        check_connection()
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        result = order_handler.close_position(
            symbol=request.symbol,
            slippage=request.slippage
        )
        return OrderResponse(
            success=True,
            message=f"Position closed successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/set-leverage", response_model=OrderResponse)
async def set_leverage(request: SetLeverageRequest):
    """
    Set leverage for a symbol
    
    Parameters:
    - symbol: Trading pair (e.g., 'BTC/USDT')
    - leverage: Leverage to set (1-100)
    """
    try:
        check_connection()
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        result = order_handler._set_leverage(
            symbol=request.symbol,
            leverage=request.leverage
        )
        return OrderResponse(
            success=True,
            message=f"Leverage set successfully on {network}",
            data={
                **result,
                "network": network
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 