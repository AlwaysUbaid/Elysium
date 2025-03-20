import pytest
from unittest.mock import Mock, patch, AsyncMock
from api.api_connector import ApiConnector
from api.constants import MAINNET_API_URL, TESTNET_API_URL

@pytest.fixture
def api_connector():
    """Create a fresh ApiConnector instance for each test"""
    return ApiConnector()

def test_init(api_connector):
    """Test ApiConnector initialization"""
    assert api_connector.wallet is None
    assert api_connector.wallet_address is None
    assert api_connector.exchange is None
    assert api_connector.info is None
    assert api_connector._is_testnet is False

@pytest.mark.asyncio
async def test_connect_testnet_success(api_connector):
    """Test successful connection to testnet"""
    with patch('api.api_connector.Exchange') as mock_exchange, \
         patch('api.api_connector.Info') as mock_info:
        # Configure mocks
        mock_exchange_instance = AsyncMock()
        mock_info_instance = AsyncMock()
        mock_exchange.return_value = mock_exchange_instance
        mock_info.return_value = mock_info_instance
        mock_info_instance.user_state = AsyncMock(return_value={
            "status": "active",
            "marginSummary": {
                "accountValue": "1000.0",
                "totalMarginUsed": "100.0",
                "totalNtlPos": "500.0"
            }
        })
        
        # Test connection
        result = await api_connector.connect_testnet()
        
        # Verify results
        assert result is True
        assert api_connector._is_testnet is True
        assert api_connector.exchange is not None
        assert api_connector.info is not None
        assert api_connector.wallet_address is None
        mock_exchange.assert_called_once_with(None, TESTNET_API_URL)
        mock_info.assert_called_once_with(TESTNET_API_URL)
        mock_info_instance.user_state.assert_called_once_with("0x0")

@pytest.mark.asyncio
async def test_connect_testnet_failure(api_connector):
    """Test failed connection to testnet"""
    with patch('api.api_connector.Exchange', side_effect=Exception("Connection failed")):
        result = await api_connector.connect_testnet()
        assert result is False
        assert api_connector.exchange is None
        assert api_connector.info is None
        assert api_connector._is_testnet is False
        assert api_connector.wallet_address is None
        assert api_connector.wallet is None

@pytest.mark.asyncio
async def test_connect_mainnet_success(api_connector):
    """Test successful connection to mainnet"""
    credentials = {
        "wallet_address": "0x123",
        "secret_key": "0x456"
    }
    
    with patch('eth_account.Account') as mock_account, \
         patch('api.api_connector.Exchange') as mock_exchange, \
         patch('api.api_connector.Info') as mock_info:
        # Configure mocks
        mock_wallet = Mock()
        mock_exchange_instance = AsyncMock()
        mock_info_instance = AsyncMock()
        mock_account.from_key.return_value = mock_wallet
        mock_exchange.return_value = mock_exchange_instance
        mock_info.return_value = mock_info_instance
        mock_info_instance.user_state = AsyncMock(return_value={
            "status": "active",
            "marginSummary": {
                "accountValue": "1000.0",
                "totalMarginUsed": "100.0",
                "totalNtlPos": "500.0"
            }
        })
        
        # Test connection
        result = await api_connector.connect(credentials)
        
        # Verify results
        assert result is True
        assert api_connector._is_testnet is False
        assert api_connector.wallet is not None
        assert api_connector.exchange is not None
        assert api_connector.info is not None
        assert api_connector.wallet_address == credentials["wallet_address"]
        mock_account.from_key.assert_called_once_with(credentials["secret_key"])
        mock_exchange.assert_called_once_with(mock_wallet, MAINNET_API_URL, account_address=credentials["wallet_address"])
        mock_info.assert_called_once_with(MAINNET_API_URL)
        mock_info_instance.user_state.assert_called_once_with(credentials["wallet_address"])

@pytest.mark.asyncio
async def test_connect_mainnet_failure(api_connector):
    """Test failed connection to mainnet"""
    credentials = {
        "wallet_address": "0x123",
        "secret_key": "0x456"
    }
    
    with patch('eth_account.Account', side_effect=Exception("Invalid key")):
        result = await api_connector.connect(credentials)
        assert result is False
        assert api_connector.wallet is None
        assert api_connector.exchange is None
        assert api_connector.info is None
        assert api_connector._is_testnet is False
        assert api_connector.wallet_address is None

@pytest.mark.asyncio
async def test_connect_hyperliquid_success(api_connector):
    """Test successful connection to Hyperliquid"""
    wallet_address = "0x123"
    secret_key = "0x456"
    
    with patch('eth_account.Account') as mock_account, \
         patch('api.api_connector.Exchange') as mock_exchange, \
         patch('api.api_connector.Info') as mock_info:
        # Configure mocks
        mock_wallet = Mock()
        mock_exchange_instance = AsyncMock()
        mock_info_instance = AsyncMock()
        mock_account.from_key.return_value = mock_wallet
        mock_exchange.return_value = mock_exchange_instance
        mock_info.return_value = mock_info_instance
        mock_info_instance.user_state = AsyncMock(return_value={
            "status": "active",
            "marginSummary": {
                "accountValue": "1000.0",
                "totalMarginUsed": "100.0",
                "totalNtlPos": "500.0"
            }
        })
        
        # Test connection
        result = await api_connector.connect_hyperliquid(wallet_address, secret_key, use_testnet=True)
        
        # Verify results
        assert result is True
        assert api_connector._is_testnet is True
        assert api_connector.wallet is not None
        assert api_connector.exchange is not None
        assert api_connector.info is not None
        assert api_connector.wallet_address == wallet_address
        mock_account.from_key.assert_called_once_with(secret_key)
        mock_exchange.assert_called_once_with(mock_wallet, TESTNET_API_URL, account_address=wallet_address)
        mock_info.assert_called_once_with(TESTNET_API_URL)
        mock_info_instance.user_state.assert_called_once_with(wallet_address)

@pytest.mark.asyncio
async def test_connect_hyperliquid_wallet_failure(api_connector):
    """Test Hyperliquid connection failure due to wallet initialization"""
    wallet_address = "0x123"
    secret_key = "0x456"
    
    with patch('eth_account.Account', side_effect=Exception("Invalid key")):
        result = await api_connector.connect_hyperliquid(wallet_address, secret_key)
        assert result is False
        assert api_connector.wallet is None
        assert api_connector.exchange is None
        assert api_connector.info is None
        assert api_connector._is_testnet is False
        assert api_connector.wallet_address is None

@pytest.mark.asyncio
async def test_connect_hyperliquid_exchange_failure(api_connector):
    """Test Hyperliquid connection failure due to exchange initialization"""
    wallet_address = "0x123"
    secret_key = "0x456"
    
    with patch('eth_account.Account') as mock_account, \
         patch('api.api_connector.Exchange', side_effect=Exception("Exchange error")):
        mock_account.from_key.return_value = Mock()
        result = await api_connector.connect_hyperliquid(wallet_address, secret_key)
        assert result is False
        assert api_connector.wallet is None
        assert api_connector.exchange is None
        assert api_connector.info is None
        assert api_connector._is_testnet is False
        assert api_connector.wallet_address is None

@pytest.mark.asyncio
async def test_connect_hyperliquid_connection_test_failure(api_connector):
    """Test Hyperliquid connection failure due to connection test"""
    wallet_address = "0x123"
    secret_key = "0x456"
    
    with patch('eth_account.Account') as mock_account, \
         patch('api.api_connector.Exchange') as mock_exchange, \
         patch('api.api_connector.Info') as mock_info:
        mock_account.from_key.return_value = Mock()
        mock_exchange.return_value = AsyncMock()
        mock_info.return_value = AsyncMock()
        mock_info.return_value.user_state.side_effect = Exception("Connection test failed")
        
        result = await api_connector.connect_hyperliquid(wallet_address, secret_key)
        assert result is False
        assert api_connector.wallet is None
        assert api_connector.exchange is None
        assert api_connector.info is None
        assert api_connector._is_testnet is False
        assert api_connector.wallet_address is None

def test_is_testnet(api_connector):
    """Test is_testnet method"""
    assert api_connector.is_testnet() is False
    api_connector._is_testnet = True
    assert api_connector.is_testnet() is True

def test_is_connected(api_connector):
    """Test is_connected method"""
    assert api_connector.is_connected() is False
    
    api_connector.exchange = Mock()
    api_connector.info = Mock()
    assert api_connector.is_connected() is True
    
    api_connector.exchange = None
    assert api_connector.is_connected() is False
    
    api_connector.exchange = Mock()
    api_connector.info = None
    assert api_connector.is_connected() is False

@pytest.mark.asyncio
async def test_get_balances_not_connected(api_connector):
    """Test get_balances when not connected"""
    result = await api_connector.get_balances()
    assert result == {
        "spot": [],
        "perp": {
            "account_value": 0.0,
            "margin_used": 0.0,
            "position_value": 0.0
        }
    }

@pytest.mark.asyncio
async def test_get_balances_success(api_connector):
    """Test successful get_balances"""
    api_connector.info = AsyncMock()
    api_connector.wallet_address = "0x123"
    
    # Mock spot balances
    api_connector.info.spot_user_state = AsyncMock(return_value={
        "balances": [
            {
                "coin": "BTC",
                "available": "1.0",
                "total": "1.5"
            }
        ]
    })
    
    # Mock perp balances
    api_connector.info.user_state = AsyncMock(return_value={
        "marginSummary": {
            "accountValue": "1000.0",
            "totalMarginUsed": "100.0",
            "totalNtlPos": "500.0"
        }
    })
    
    result = await api_connector.get_balances()
    assert result["spot"] == [
        {
            "asset": "BTC",
            "available": 1.0,
            "total": 1.5,
            "in_orders": 0.5
        }
    ]
    assert result["perp"] == {
        "account_value": 1000.0,
        "margin_used": 100.0,
        "position_value": 500.0
    }

@pytest.mark.asyncio
async def test_get_balances_spot_error(api_connector):
    """Test get_balances with spot balance error"""
    api_connector.info = AsyncMock()
    api_connector.wallet_address = "0x123"
    
    # Mock spot balance error
    api_connector.info.spot_user_state = AsyncMock(side_effect=Exception("Spot error"))
    
    # Mock perp balances
    api_connector.info.user_state = AsyncMock(return_value={
        "marginSummary": {
            "accountValue": "1000.0",
            "totalMarginUsed": "100.0",
            "totalNtlPos": "500.0"
        }
    })
    
    result = await api_connector.get_balances()
    assert result["spot"] == []
    assert result["perp"] == {
        "account_value": 1000.0,
        "margin_used": 100.0,
        "position_value": 500.0
    }

@pytest.mark.asyncio
async def test_get_balances_perp_error(api_connector):
    """Test get_balances with perp balance error"""
    api_connector.info = AsyncMock()
    api_connector.wallet_address = "0x123"
    
    # Mock spot balances
    api_connector.info.spot_user_state = AsyncMock(return_value={
        "balances": [
            {
                "coin": "BTC",
                "available": "1.0",
                "total": "1.5"
            }
        ]
    })
    
    # Mock perp balance error
    api_connector.info.user_state = AsyncMock(side_effect=Exception("Perp error"))
    
    result = await api_connector.get_balances()
    assert result["spot"] == [
        {
            "asset": "BTC",
            "available": 1.0,
            "total": 1.5,
            "in_orders": 0.5
        }
    ]
    assert result["perp"] == {
        "account_value": 0.0,
        "margin_used": 0.0,
        "position_value": 0.0
    }

@pytest.mark.asyncio
async def test_get_positions_not_connected(api_connector):
    """Test get_positions when not connected"""
    result = await api_connector.get_positions()
    assert result == []

@pytest.mark.asyncio
async def test_get_positions_success(api_connector):
    """Test successful get_positions"""
    api_connector.info = AsyncMock()
    api_connector.wallet_address = "0x123"
    
    # Mock positions
    api_connector.info.user_state = AsyncMock(return_value={
        "assetPositions": [
            {
                "position": {
                    "coin": "BTC",
                    "szi": "1.0",
                    "entryPx": "50000.0",
                    "markPx": "51000.0",
                    "liquidationPx": "45000.0",
                    "unrealizedPnl": "1000.0",
                    "marginUsed": "100.0"
                }
            }
        ]
    })
    
    result = await api_connector.get_positions()
    assert result == [
        {
            "symbol": "BTC",
            "size": 1.0,
            "entry_price": 50000.0,
            "mark_price": 51000.0,
            "liquidation_price": 45000.0,
            "unrealized_pnl": 1000.0,
            "margin_used": 100.0
        }
    ]

@pytest.mark.asyncio
async def test_get_positions_error(api_connector):
    """Test get_positions with error"""
    api_connector.info = AsyncMock()
    api_connector.wallet_address = "0x123"
    
    # Mock error
    api_connector.info.user_state = AsyncMock(side_effect=Exception("Failed to get positions"))
    
    result = await api_connector.get_positions()
    assert result == []

@pytest.mark.asyncio
async def test_get_positions_zero_size(api_connector):
    """Test get_positions with zero size position"""
    api_connector.info = AsyncMock()
    api_connector.wallet_address = "0x123"
    
    # Mock zero size position
    api_connector.info.user_state = AsyncMock(return_value={
        "assetPositions": [
            {
                "position": {
                    "coin": "BTC",
                    "szi": "0.0",
                    "entryPx": "50000.0",
                    "markPx": "51000.0",
                    "liquidationPx": "45000.0",
                    "unrealizedPnl": "0.0",
                    "marginUsed": "0.0"
                }
            }
        ]
    })
    
    result = await api_connector.get_positions()
    assert result == [] 