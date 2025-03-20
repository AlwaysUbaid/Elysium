from pydantic import BaseModel, Field, validator, confloat, conint
from typing import Dict, Any, Optional

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