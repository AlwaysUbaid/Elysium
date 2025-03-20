import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
import sys
import os

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main import app
import json
import time

client = TestClient(app)

# Test data
TEST_WALLET = "0x4f7116a3B69b14480b0C0890d63bd4B3d0984EE6"
TEST_SECRET = "0x992df5cae22a4b8e3844f73e14756f11a2662b7f2e792ce78fd85abb63150d51"

@pytest.fixture(autouse=True)
def setup_connection():
    """Setup connection before each test"""
    try:
        # Connect to testnet
        payload = {
            "network": "testnet",
            "credentials": {
                "wallet_address": TEST_WALLET,
                "secret_key": TEST_SECRET
            }
        }
        response = client.post("/connect", json=payload)
        print(f"Connection response: {response.json()}")
        if response.status_code != 200:
            print(f"Connection failed: {response.json()}")
        time.sleep(1)  # Wait for connection to stabilize
    except Exception as e:
        print(f"Setup error: {str(e)}")
        raise

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/")
    print(f"Health check response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_connect():
    """Test connection endpoint"""
    payload = {
        "network": "testnet",
        "credentials": {
            "wallet_address": TEST_WALLET,
            "secret_key": TEST_SECRET
        }
    }
    response = client.post("/connect", json=payload)
    print(f"Connect response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_balances():
    """Test balances endpoint"""
    response = client.get("/balances")
    print(f"Balances response: {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert "spot" in data
    assert "perp" in data

def test_open_orders():
    """Test open orders endpoint"""
    response = client.get("/open-orders")
    print(f"Open orders response: {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert "orders" in data

def test_spot_market_buy():
    """Test spot market buy endpoint"""
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "slippage": 0.05
    }
    response = client.post("/api/v1/spot/market-buy", json=payload)
    print(f"Market buy response: {response.json()}")
    assert response.status_code in [200, 400, 422]  # 422 is for validation errors
    data = response.json()
    if response.status_code == 200:
        assert "success" in data
        assert data["success"] is True
    else:
        assert "detail" in data

def test_spot_market_sell():
    """Test spot market sell endpoint"""
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "slippage": 0.05
    }
    response = client.post("/api/v1/spot/market-sell", json=payload)
    print(f"Market sell response: {response.json()}")
    assert response.status_code in [200, 400, 422]
    data = response.json()
    if response.status_code == 200:
        assert "success" in data
        assert data["success"] is True
    else:
        assert "detail" in data

def test_spot_limit_buy():
    """Test spot limit buy endpoint"""
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "price": 50000.0
    }
    response = client.post("/api/v1/spot/limit-buy", json=payload)
    print(f"Limit buy response: {response.json()}")
    assert response.status_code in [200, 400, 422]
    data = response.json()
    if response.status_code == 200:
        assert "success" in data
        assert data["success"] is True
    else:
        assert "detail" in data

def test_spot_limit_sell():
    """Test spot limit sell endpoint"""
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "price": 51000.0
    }
    response = client.post("/api/v1/spot/limit-sell", json=payload)
    print(f"Limit sell response: {response.json()}")
    assert response.status_code in [200, 400, 422]
    data = response.json()
    if response.status_code == 200:
        assert "success" in data
        assert data["success"] is True
    else:
        assert "detail" in data

def test_spot_cancel_order():
    """Test spot cancel order endpoint"""
    # First get open orders
    response = client.get("/open-orders")
    print(f"Open orders for cancel: {response.json()}")
    if response.status_code == 200 and response.json().get("orders"):
        order_id = response.json()["orders"][0]["order_id"]
        payload = {
            "symbol": "BTC/USDT",
            "order_id": order_id
        }
        response = client.post("/api/v1/spot/cancel-order", json=payload)
        print(f"Cancel order response: {response.json()}")
        assert response.status_code in [200, 400, 422]
        data = response.json()
        
        if response.status_code == 422:
            # Handle validation error
            assert "detail" in data
            assert isinstance(data["detail"], list)
            assert any("order_id" in error["loc"] for error in data["detail"])
        else:
            # Handle successful response
            assert "success" in data
            assert "message" in data
            if "data" in data:
                assert "status" in data["data"]
                assert "network" in data["data"]

def test_spot_cancel_all_orders():
    """Test spot cancel all orders endpoint"""
    payload = {"symbol": "BTC/USDT"}  # Add required symbol parameter
    response = client.post("/api/v1/spot/cancel-all-orders", json=payload)
    print(f"Cancel all orders response: {response.json()}")
    assert response.status_code in [200, 400, 422]
    data = response.json()
    if response.status_code == 200:
        assert "success" in data
        assert data["success"] is True
    else:
        assert "detail" in data

def test_invalid_symbol():
    """Test invalid symbol format"""
    payload = {
        "symbol": "INVALID",
        "size": 0.001,
        "slippage": 0.05
    }
    response = client.post("/api/v1/spot/market-buy", json=payload)
    print(f"Invalid symbol response: {response.json()}")
    assert response.status_code in [400, 422]  # Both 400 and 422 are valid for validation errors
    data = response.json()
    assert "detail" in data or "message" in data

def test_invalid_size():
    """Test invalid order size"""
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.00001,  # Too small
        "slippage": 0.05
    }
    response = client.post("/api/v1/spot/market-buy", json=payload)
    print(f"Invalid size response: {response.json()}")
    assert response.status_code in [400, 422]  # Both 400 and 422 are valid for validation errors
    data = response.json()
    assert "detail" in data or "message" in data

def test_connection_errors(monkeypatch):
    """Test connection error handling"""
    # Mock api_connector.is_connected to return False
    from api.spot_api import api_connector
    monkeypatch.setattr(api_connector, "is_connected", lambda: False)
    
    # Test not connected
    response = client.post("/api/v1/spot/market-buy", json={"symbol": "BTC/USDT", "size": 0.1})
    assert response.status_code == 400
    data = response.json()
    assert "Not connected to exchange" in data["detail"]["message"]
    assert "required_action" in data["detail"]

    # Mock order handler not configured
    monkeypatch.setattr(api_connector, "is_connected", lambda: True)
    from api.spot_api import order_handler
    monkeypatch.setattr(order_handler, "exchange", None)
    monkeypatch.setattr(order_handler, "info", None)
    
    response = client.post("/api/v1/spot/market-buy", json={"symbol": "BTC/USDT", "size": 0.1})
    assert response.status_code == 400
    data = response.json()
    assert "Order handler not configured" in data["detail"]["message"]

def test_validation_errors():
    """Test request validation errors"""
    # Test invalid size
    response = client.post("/api/v1/spot/market-buy", json={
        "symbol": "BTC/USDT",
        "size": 0.00001  # Too small
    })
    assert response.status_code == 422
    data = response.json()
    assert "size" in str(data)

    # Test invalid price
    response = client.post("/api/v1/spot/limit-buy", json={
        "symbol": "BTC/USDT",
        "size": 0.1,
        "price": 0.00001  # Too small
    })
    assert response.status_code == 422
    data = response.json()
    assert "price" in str(data)

    # Test invalid slippage
    response = client.post("/api/v1/spot/market-buy", json={
        "symbol": "BTC/USDT",
        "size": 0.1,
        "slippage": 2.0  # Too high
    })
    assert response.status_code == 422
    data = response.json()
    assert "slippage" in str(data)

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac

@pytest.mark.asyncio
async def test_order_handler_errors(monkeypatch, async_client):
    """Test order handler error handling"""
    from api.spot_api import order_handler
    
    # Mock market buy error
    monkeypatch.setattr(order_handler, "market_buy", lambda *args, **kwargs: {"success": False, "error": "Order failed"})
    response = await async_client.post("/api/v1/spot/market-buy", json={
        "symbol": "BTC/USDT",
        "size": 0.1,
        "slippage": 0.1
    })
    assert response.status_code == 400
    data = response.json()
    assert "Order failed" in data["detail"]

    # Mock market sell error
    monkeypatch.setattr(order_handler, "market_sell", lambda *args, **kwargs: {"success": False, "error": "Order failed"})
    response = await async_client.post("/api/v1/spot/market-sell", json={
        "symbol": "BTC/USDT",
        "size": 0.1,
        "slippage": 0.1
    })
    assert response.status_code == 400
    data = response.json()
    assert "Order failed" in data["detail"]

    # Mock limit buy error
    monkeypatch.setattr(order_handler, "limit_buy", lambda *args, **kwargs: {"success": False, "error": "Order failed"})
    response = await async_client.post("/api/v1/spot/limit-buy", json={
        "symbol": "BTC/USDT",
        "size": 0.1,
        "price": 50000.0
    })
    assert response.status_code == 400
    data = response.json()
    assert "Order failed" in data["detail"]

    # Mock limit sell error
    monkeypatch.setattr(order_handler, "limit_sell", lambda *args, **kwargs: {"success": False, "error": "Order failed"})
    response = await async_client.post("/api/v1/spot/limit-sell", json={
        "symbol": "BTC/USDT",
        "size": 0.1,
        "price": 50000.0
    })
    assert response.status_code == 400
    data = response.json()
    assert "Order failed" in data["detail"] 