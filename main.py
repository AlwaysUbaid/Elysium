from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uvicorn

# Import core modules
from core.config_manager import ConfigManager
from core.utils import setup_logging
from api.api_connector import ApiConnector
from order_handler import OrderHandler

# Initialize FastAPI app
app = FastAPI(
    title="Elysium Trading Platform API",
    description="API for the Elysium Trading Platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
config_manager = ConfigManager("elysium_config.json")
api_connector = ApiConnector()
order_handler = OrderHandler()

# Request/Response Models
class Credentials(BaseModel):
    wallet_address: str = Field(
        ...,
        description="Your Ethereum wallet address (e.g., 0x123...)",
        example="0x1234567890abcdef1234567890abcdef12345678"
    )
    secret_key: str = Field(
        ...,
        description="Your wallet's private key",
        example="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )

class ConnectionRequest(BaseModel):
    network: str = Field(
        default="mainnet",
        description="Network to connect to (mainnet or testnet)",
        example="mainnet"
    )
    credentials: Credentials = Field(
        ...,
        description="Wallet credentials (required for both mainnet and testnet)"
    )

class OrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol (e.g., BTC)")
    side: str = Field(..., description="Order side (buy or sell)")
    quantity: float = Field(..., description="Order quantity")
    price: Optional[float] = Field(None, description="Order price (required for limit orders)")
    order_type: str = Field(default="market", description="Order type (market or limit)")

class ConfigUpdate(BaseModel):
    key: str = Field(..., description="Configuration key to update")
    value: Any = Field(..., description="New value for the configuration key")

class SpotBalance(BaseModel):
    asset: str = Field(..., description="Asset symbol (e.g., BTC)")
    available: float = Field(..., description="Available balance")
    total: float = Field(..., description="Total balance")
    in_orders: float = Field(..., description="Balance in open orders")

class PerpBalance(BaseModel):
    account_value: float = Field(..., description="Total account value")
    margin_used: float = Field(..., description="Margin used for positions")
    position_value: float = Field(..., description="Total position value")

class BalancesResponse(BaseModel):
    spot: List[SpotBalance] = Field(..., description="List of spot balances")
    perp: PerpBalance = Field(..., description="Perpetual trading balances")

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "message": "Elysium Trading Platform API"}

@app.post("/connect", response_model=Dict[str, str])
async def connect(request: ConnectionRequest):
    """
    Connect to either mainnet or testnet of the exchange.
    
    For both mainnet and testnet:
    - Requires wallet credentials (wallet_address and secret_key)
    
    ⚠️ Security Note: Never share your secret_key with anyone!
    """
    try:
        success = api_connector.connect_hyperliquid(
            wallet_address=request.credentials.wallet_address,
            secret_key=request.credentials.secret_key,
            use_testnet=(request.network == "testnet")
        )
        
        if success:
            return {"status": "success", "message": f"Connected to {request.network}"}
        raise HTTPException(status_code=400, detail="Connection failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status", response_model=Dict[str, str])
async def get_status():
    """Check if connected to the exchange and which network is being used"""
    try:
        is_connected = api_connector.is_connected()
        return {
            "status": "connected" if is_connected else "disconnected",
            "network": "testnet" if api_connector.is_testnet() else "mainnet"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/balances", response_model=BalancesResponse)
async def get_balances():
    """Get both spot and perpetual trading balances"""
    try:
        if not api_connector.is_connected():
            raise HTTPException(status_code=400, detail="Not connected to exchange")
        
        balances = api_connector.get_balances()
        
        spot_balances = [
            SpotBalance(
                asset=balance["asset"],
                available=balance["available"],
                total=balance["total"],
                in_orders=balance["in_orders"]
            )
            for balance in balances["spot"]
        ]
        
        perp_balance = PerpBalance(
            account_value=balances["perp"]["account_value"],
            margin_used=balances["perp"]["margin_used"],
            position_value=balances["perp"]["position_value"]
        )
        
        return BalancesResponse(spot=spot_balances, perp=perp_balance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/order", response_model=Dict[str, Any])
async def place_order(order: OrderRequest):
    """Place a new order on the exchange (market or limit)"""
    try:
        if not api_connector.is_connected():
            raise HTTPException(status_code=400, detail="Not connected to exchange")
        
        result = order_handler.place_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            order_type=order.order_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/positions", response_model=List[Dict[str, Any]])
async def get_positions():
    """Get all currently open trading positions"""
    try:
        if not api_connector.is_connected():
            raise HTTPException(status_code=400, detail="Not connected to exchange")
        return api_connector.get_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/balance", response_model=Dict[str, Any])
async def get_balance():
    """Get the current account balance"""
    try:
        if not api_connector.is_connected():
            raise HTTPException(status_code=400, detail="Not connected to exchange")
        return api_connector.get_balance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config", response_model=Dict[str, Any])
async def get_config():
    """Get all current configuration settings"""
    try:
        return config_manager.get_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/config", response_model=Dict[str, str])
async def update_config(config_update: ConfigUpdate):
    """Update a specific configuration setting"""
    try:
        config_manager.set(config_update.key, config_update.value)
        return {"status": "success", "message": f"Updated config: {config_update.key}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger = setup_logging("INFO")
    logger.info("Starting Elysium Trading Platform API")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 