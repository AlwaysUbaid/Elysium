# Constants module
"""
Constants used across the Elysium trading framework.
"""

# API URLs
MAINNET_API_URL = "https://api.hyperliquid.xyz"
TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"
LOCAL_API_URL = "http://localhost:3001"
MAINNET_WS_URL = "wss://api.hyperliquid.xyz/ws"
TESTNET_WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"

# Default values
DEFAULT_SLIPPAGE = 0.05  # 5% slippage for market orders
DEFAULT_ORDER_TIMEOUT = 30.0  # 30 seconds timeout for order operations
DEFAULT_TICK_INTERVAL = 1.0  # 1 second tick interval for strategy loop
DEFAULT_ORDER_REFRESH_TIME = 60.0  # 60 seconds order refresh time
DEFAULT_MAX_ORDERS_PER_SIDE = 1  # Default maximum number of orders per side

# Limits
MAX_RETRY_ATTEMPTS = 3  # Maximum number of retries for API calls
MAX_BATCH_SIZE = 10  # Maximum batch size for order operations

# Order types
ORDER_TYPE_LIMIT = "limit"
ORDER_TYPE_MARKET = "market"
ORDER_TYPE_STOP = "stop"
ORDER_TYPE_TAKE_PROFIT = "take_profit"

# Time in force options
TIF_GTC = "Gtc"  # Good till cancelled
TIF_IOC = "Ioc"  # Immediate or cancel
TIF_ALO = "Alo"  # Add liquidity only (post only)

# Log levels
LOG_LEVEL_DEBUG = 10
LOG_LEVEL_INFO = 20
LOG_LEVEL_WARNING = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50