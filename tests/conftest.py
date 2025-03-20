import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from main import app

@pytest.fixture
async def async_client():
    """Create an async test client"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock dependencies for all tests"""
    with patch("api.perp_api.order_handler") as mock_order_handler, \
         patch("api.perp_api.api_connector") as mock_api_connector:
        
        # Setup basic mocks
        mock_order_handler.wallet_address = "0x1234567890abcdef"
        mock_order_handler.exchange = AsyncMock()
        mock_order_handler.info = AsyncMock()
        
        # Setup order methods with proper async return values
        mock_order_handler.perp_market_buy = AsyncMock(return_value={"success": True, "data": {"order_id": 201, "network": "testnet"}})
        mock_order_handler.perp_market_sell = AsyncMock(return_value={"success": True, "data": {"order_id": 202, "network": "testnet"}})
        mock_order_handler.perp_limit_buy = AsyncMock(return_value={"success": True, "data": {"order_id": 203, "network": "testnet"}})
        mock_order_handler.perp_limit_sell = AsyncMock(return_value={"success": True, "data": {"order_id": 204, "network": "testnet"}})
        mock_order_handler._set_leverage = AsyncMock(return_value={"success": True, "data": {"leverage": 5, "network": "testnet"}})
        
        # Setup API connector
        mock_api_connector.is_connected.return_value = True
        mock_api_connector.is_testnet.return_value = True
        
        yield {"order_handler": mock_order_handler, "api_connector": mock_api_connector} 