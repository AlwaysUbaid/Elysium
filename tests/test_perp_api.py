import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock

# Test data
TEST_MARKET_ORDER = {
    "symbol": "BTC",
    "size": 0.1,
    "leverage": 5,
    "slippage": 0.1
}

TEST_LIMIT_ORDER = {
    "symbol": "BTC",
    "size": 0.1,
    "price": 50000.0,
    "leverage": 5
}

TEST_SET_LEVERAGE = {
    "symbol": "BTC",
    "leverage": 5
}

class BaseTestOrder:
    """Base class for order tests"""
    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_dependencies):
        """Test successful order"""
        response = await async_client.post(self.endpoint, json=self.test_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["order_id"] == self.expected_order_id
        assert data["data"]["network"] == "testnet"

    @pytest.mark.asyncio
    async def test_invalid_symbol(self, async_client):
        """Test with invalid symbol"""
        invalid_order = self.test_data.copy()
        invalid_order["symbol"] = "INVALID"
        response = await async_client.post(self.endpoint, json=invalid_order)
        assert response.status_code == 422
        assert "Invalid trading pair format" in response.text

    @pytest.mark.asyncio
    async def test_invalid_leverage(self, async_client):
        """Test with invalid leverage"""
        invalid_order = self.test_data.copy()
        invalid_order["leverage"] = 0
        response = await async_client.post(self.endpoint, json=invalid_order)
        assert response.status_code == 422
        assert "Input should be greater than 0" in response.text

    @pytest.mark.asyncio
    async def test_order_handler_error(self, async_client, mock_dependencies):
        """Test when order handler raises an error"""
        mock_dependencies["order_handler"].__getattr__(self.order_handler_method).side_effect = Exception("Order failed")
        response = await async_client.post(self.endpoint, json=self.test_data)
        assert response.status_code == 400
        assert "Order failed" in response.text

class TestPerpMarketBuy(BaseTestOrder):
    endpoint = "/api/v1/perp/market-buy"
    test_data = TEST_MARKET_ORDER
    expected_order_id = 201
    order_handler_method = "perp_market_buy"

    @pytest.mark.asyncio
    async def test_invalid_slippage(self, async_client):
        """Test with invalid slippage"""
        invalid_order = self.test_data.copy()
        invalid_order["slippage"] = 0
        response = await async_client.post(self.endpoint, json=invalid_order)
        assert response.status_code == 422
        assert "Input should be greater than 0" in response.text

class TestPerpMarketSell(BaseTestOrder):
    endpoint = "/api/v1/perp/market-sell"
    test_data = TEST_MARKET_ORDER
    expected_order_id = 202
    order_handler_method = "perp_market_sell"

    @pytest.mark.asyncio
    async def test_invalid_slippage(self, async_client):
        """Test with invalid slippage"""
        invalid_order = self.test_data.copy()
        invalid_order["slippage"] = 0
        response = await async_client.post(self.endpoint, json=invalid_order)
        assert response.status_code == 422
        assert "Input should be greater than 0" in response.text

class TestPerpLimitBuy(BaseTestOrder):
    endpoint = "/api/v1/perp/limit-buy"
    test_data = TEST_LIMIT_ORDER
    expected_order_id = 203
    order_handler_method = "perp_limit_buy"

class TestPerpLimitSell(BaseTestOrder):
    endpoint = "/api/v1/perp/limit-sell"
    test_data = TEST_LIMIT_ORDER
    expected_order_id = 204
    order_handler_method = "perp_limit_sell"

class TestSetLeverage(BaseTestOrder):
    endpoint = "/api/v1/perp/set-leverage"
    test_data = TEST_SET_LEVERAGE
    expected_order_id = None
    order_handler_method = "_set_leverage"

    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_dependencies):
        """Test successful leverage setting"""
        response = await async_client.post(self.endpoint, json=self.test_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["leverage"] == 5
        assert data["data"]["network"] == "testnet"

class TestConnectionErrors:
    """Test connection-related errors"""
    @pytest.mark.asyncio
    async def test_not_connected(self, async_client, mock_dependencies):
        """Test when API is not connected"""
        mock_dependencies["api_connector"].is_connected.return_value = False
        response = await async_client.post("/api/v1/perp/market-buy", json=TEST_MARKET_ORDER)
        assert response.status_code == 400
        assert "Not connected to exchange" in response.text

    @pytest.mark.asyncio
    async def test_order_handler_not_configured(self, async_client, mock_dependencies):
        """Test when order handler is not configured"""
        mock_dependencies["order_handler"].wallet_address = None
        response = await async_client.post("/api/v1/perp/market-buy", json=TEST_MARKET_ORDER)
        assert response.status_code == 400
        assert "Wallet address not set" in response.text

    @pytest.mark.asyncio
    async def test_wallet_not_set(self, async_client, mock_dependencies):
        """Test when wallet address is not set"""
        mock_dependencies["order_handler"].wallet_address = None
        response = await async_client.post("/api/v1/perp/market-buy", json=TEST_MARKET_ORDER)
        assert response.status_code == 400
        assert "Wallet address not set" in response.text 