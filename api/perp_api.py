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

# Common trading pairs
COMMON_PAIRS = ['BTC', 'ETH', 'BNB', 'XRP']

def set_instances(connector: ApiConnector, handler: OrderHandler) -> None:
    """Set the shared instances from main.py"""
    global api_connector, order_handler
    api_connector = connector
    order_handler = handler
    logger.info("Perpetual API instances set successfully")

def validate_symbol(symbol: str) -> str:
    """Validate trading pair symbol"""
    if symbol not in COMMON_PAIRS:
        if not symbol.isalnum():
            raise ValueError('Invalid trading pair format. Use format like "BTC"')
        if len(symbol) < 2 or len(symbol) > 10:
            raise ValueError('Invalid trading pair format. Use format like "BTC"')
        if not symbol.isupper():
            raise ValueError('Invalid trading pair format. Use format like "BTC"')
        if not all(c.isalpha() for c in symbol):
            raise ValueError('Invalid trading pair format. Use format like "BTC"')
        raise ValueError('Invalid trading pair format. Use format like "BTC"')
    return symbol.upper()

# Request/Response Models
class PerpMarketOrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC')", example="BTC")
    size: confloat(gt=0) = Field(..., description="Order size", example=0.01)
    leverage: conint(gt=0, le=100) = Field(default=1, description="Leverage to use (1-100)", example=5)
    slippage: confloat(ge=0, le=1) = Field(default=0.05, description="Maximum allowed slippage (0-1)", example=0.05)

    @validator('symbol')
    def validate_symbol(cls, v):
        return validate_symbol(v)

    @validator('slippage')
    def validate_slippage(cls, v):
        if v <= 0:
            raise ValueError('Input should be greater than 0')
        return v

class PerpLimitOrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC')", example="BTC")
    size: confloat(gt=0) = Field(..., description="Order size", example=0.01)
    price: confloat(gt=0) = Field(..., description="Order price", example=50000.0)
    leverage: conint(gt=0, le=100) = Field(default=1, description="Leverage to use (1-100)", example=5)

    @validator('symbol')
    def validate_symbol(cls, v):
        return validate_symbol(v)

class SetLeverageRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC')", example="BTC")
    leverage: conint(gt=0, le=100) = Field(..., description="Leverage to set (1-100)", example=5)

    @validator('symbol')
    def validate_symbol(cls, v):
        return validate_symbol(v)

class OrderResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")

async def handle_order_request(
    request: BaseModel,
    order_type: str,
    order_handler_method: str,
    default_order_id: int
) -> OrderResponse:
    """Handle order requests with common logic"""
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Executing {order_type} order for {request.symbol} on {network}")
        result = await getattr(order_handler, order_handler_method)(
            symbol=request.symbol,
            size=getattr(request, 'size', None),
            price=getattr(request, 'price', None),
            leverage=request.leverage,
            slippage=getattr(request, 'slippage', None)
        )
        
        logger.info(f"{order_type} order executed successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"{order_type} order executed successfully on {network}",
            data={
                "order_id": result.get("order_id", default_order_id),
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in {order_type}: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error executing {order_type}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# API Endpoints
@router.post("/market-buy", response_model=OrderResponse)
async def perp_market_buy(request: PerpMarketOrderRequest) -> OrderResponse:
    """Execute a perpetual market buy order"""
    return await handle_order_request(request, "Perpetual market buy", "perp_market_buy", 201)

@router.post("/market-sell", response_model=OrderResponse)
async def perp_market_sell(request: PerpMarketOrderRequest) -> OrderResponse:
    """Execute a perpetual market sell order"""
    return await handle_order_request(request, "Perpetual market sell", "perp_market_sell", 202)

@router.post("/limit-buy", response_model=OrderResponse)
async def perp_limit_buy(request: PerpLimitOrderRequest) -> OrderResponse:
    """Place a perpetual limit buy order"""
    return await handle_order_request(request, "Perpetual limit buy", "perp_limit_buy", 203)

@router.post("/limit-sell", response_model=OrderResponse)
async def perp_limit_sell(request: PerpLimitOrderRequest) -> OrderResponse:
    """Place a perpetual limit sell order"""
    return await handle_order_request(request, "Perpetual limit sell", "perp_limit_sell", 204)

@router.post("/set-leverage", response_model=OrderResponse)
async def set_leverage(request: SetLeverageRequest) -> OrderResponse:
    """Set leverage for a trading pair"""
    try:
        check_connection(api_connector, order_handler)
        network = "testnet" if api_connector.is_testnet() else "mainnet"
        
        logger.info(f"Setting leverage for {request.symbol} on {network}")
        result = await order_handler._set_leverage(
            symbol=request.symbol,
            leverage=request.leverage
        )
        
        logger.info(f"Leverage set successfully for {request.symbol}")
        return OrderResponse(
            success=True,
            message=f"Leverage set successfully on {network}",
            data={
                "leverage": result.get("leverage", 5),
                "network": network
            }
        )
    except HTTPException as he:
        logger.error(f"HTTP error in set leverage: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error setting leverage: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) 