# Elysium Trading Platform

A modular, extensible trading platform for Hyperliquid exchange supporting multiple order types, strategies, and interfaces.

## Features

- Connect to Hyperliquid exchange (both mainnet and testnet)
- Multiple order types:
  - Spot and perpetual market/limit orders
  - Scaled orders across price ranges
  - Time-Weighted Average Price (TWAP) execution
  - Grid trading strategies
- Interactive terminal UI
- Telegram bot interface
- Trading strategy framework

## Project Structure

The project is organized into several modules to enhance maintainability and extensibility:

```
elysium/
├── api/                  # API connectivity
│   ├── __init__.py
│   ├── api_connector.py  # Connect to exchange API
│   └── constants.py      # API URLs and constants
├── core/                 # Core functionality
│   ├── __init__.py
│   ├── config_manager.py # Handle configuration
│   └── utils.py          # Utility functions
├── order_execution/      # Order execution strategies
│   ├── __init__.py
│   ├── simple_orders.py  # Basic spot and perp orders
│   ├── scaled_orders.py  # Scaled order strategies
│   ├── twap_orders.py    # TWAP order execution
│   └── grid_trading.py   # Grid trading functionality
├── strategies/           # Trading strategies
│   ├── __init__.py
│   ├── strategy_selector.py   # Strategy selection system
│   └── pure_mm.py        # Pure market making strategy
├── ui/                   # User interfaces
│   ├── __init__.py
│   ├── terminal_ui.py    # CLI interface
│   └── telegram_bot.py   # Telegram bot interface
├── elysium.py            # Main entry point
├── order_handler.py      # Order coordination
└── README.md             # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/elysium.git
   cd elysium
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. For Telegram bot functionality (optional):
   ```
   pip install python-telegram-bot==13.7 urllib3==1.26.15 httpx==0.23.0
   ```

## Configuration

Create a file named `dontshareconfig.py` with your API keys:

```python
# Mainnet credentials
mainnet_wallet = "YOUR_MAINNET_WALLET_ADDRESS"
mainnet_secret = "YOUR_MAINNET_SECRET_KEY"

# Testnet credentials (optional)
testnet_wallet = "YOUR_TESTNET_WALLET_ADDRESS"
testnet_secret = "YOUR_TESTNET_SECRET_KEY"

# Telegram bot configuration (optional)
telegram_token = "YOUR_TELEGRAM_BOT_TOKEN"
telegram_admin_ids = [YOUR_TELEGRAM_USER_ID]
```

## Usage

### Running the Terminal UI

```
python elysium.py
```

Options:
- `-t, --testnet`: Connect to testnet instead of mainnet
- `-v, --verbose`: Enable verbose logging
- `--log-file PATH`: Specify a log file
- `--no-telegram`: Disable Telegram bot
- `--telegram-only`: Run only the Telegram bot (no terminal UI)

### Terminal UI Commands

Basic commands:
- `connect [mainnet|testnet]`: Connect to Hyperliquid exchange
- `balance`: Show account balance
- `positions`: Show open positions
- `orders`: List open orders
- `cancel <symbol> <order_id>`: Cancel a specific order
- `cancel_all [symbol]`: Cancel all orders, optionally for a specific symbol

Simple orders:
- `buy <symbol> <size> [slippage]`: Execute a market buy order
- `sell <symbol> <size> [slippage]`: Execute a market sell order
- `limit_buy <symbol> <size> <price>`: Place a limit buy order
- `limit_sell <symbol> <size> <price>`: Place a limit sell order

Perpetual orders:
- `perp_buy <symbol> <size> [leverage] [slippage]`: Execute a perpetual market buy
- `perp_sell <symbol> <size> [leverage] [slippage]`: Execute a perpetual market sell
- `perp_limit_buy <symbol> <size> <price> [leverage]`: Place a perpetual limit buy
- `perp_limit_sell <symbol> <size> <price> [leverage]`: Place a perpetual limit sell
- `close_position <symbol> [slippage]`: Close a position
- `set_leverage <symbol> <leverage>`: Set leverage for a symbol

Scaled orders:
- `scaled_buy <symbol> <total> <num> <start> <end> [skew]`: Place multiple buy orders
- `scaled_sell <symbol> <total> <num> <start> <end> [skew]`: Place multiple sell orders
- `market_scaled_buy <symbol> <total> <num> [percent] [skew]`: Place market-aware buy orders
- `market_scaled_sell <symbol> <total> <num> [percent] [skew]`: Place market-aware sell orders

Grid trading:
- `grid_create <symbol> <upper> <lower> <num> <investment> [is_perp] [leverage] [tp] [sl]`: Create grid
- `grid_start <grid_id>`: Start a grid strategy
- `grid_stop <grid_id>`: Stop a grid strategy
- `grid_status <grid_id>`: Check grid status
- `grid_list`: List all grid strategies
- `grid_stop_all`: Stop all active grid strategies
- `grid_clean`: Clean up completed grid strategies

TWAP execution:
- `twap_create <symbol> <side> <quantity> <duration> <slices> [price] [is_perp] [leverage]`: Create TWAP
- `twap_start <twap_id>`: Start TWAP execution
- `twap_stop <twap_id>`: Stop TWAP execution
- `twap_status <twap_id>`: Check TWAP status
- `twap_list`: List all TWAP executions
- `twap_stop_all`: Stop all active TWAP executions

### Telegram Bot Commands

- `/start`: Start the bot
- `/help`: Show help menu
- `/connect`: Connect to the exchange
- `/status`: Show connection status
- `/balance`: Show account balance
- `/positions`: Show positions
- `/orders`: Show open orders
- `/price <symbol>`: Check price
- `/trade`: Start trading dialog
- `/menu`: Show commands menu

## Trading Strategies

The platform includes a strategy framework that allows you to create and run custom strategies:

- Pure Market Making: Places buy and sell orders around the mid price to capture the spread

To implement your own strategy:
1. Create a new file in the `strategies` directory
2. Inherit from `TradingStrategy` class
3. Implement the required methods

## License

[MIT License](LICENSE)

## Disclaimer

This software is for educational purposes only. Use at your own risk. Trading cryptocurrency carries significant financial risk.