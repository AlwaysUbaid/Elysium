# Elysium

```
 ███████╗██╗  ██╗   ██╗███████╗██╗██╗   ██╗███╗   ███╗
 ██╔════╝██║  ╚██╗ ██╔╝██╔════╝██║██║   ██║████╗ ████║
 █████╗  ██║   ╚████╔╝ ███████╗██║██║   ██║██╔████╔██║
 ██╔══╝  ██║    ╚██╔╝  ╚════██║██║██║   ██║██║╚██╔╝██║
 ███████╗███████╗██║   ███████║██║╚██████╔╝██║ ╚═╝ ██║
 ╚══════╝╚══════╝╚═╝   ╚══════╝╚═╝ ╚═════╝ ╚═╝     ╚═╝
                                                      
 ✧ Advanced Automated Trading Framework for Hyperliquid ✧
```

## Advanced Automated Trading Framework for Hyperliquid

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Elysium is a modular, high-performance trading framework built on the Hyperliquid Python SDK that enables sophisticated trading strategies with builder rebate optimization.

## Features

- **Modular Architecture**: Clean separation of concerns with a component-based design
- **Strategy Selector**: Dynamically select and configure trading strategies
- **Rebate Optimization**: Built-in builder rebate management for fee reduction
- **Risk Management**: Advanced position and risk monitoring
- **High Performance**: Designed for low-latency trading operations
- **Extensible Design**: Easy to add new strategies and components

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/elysium.git
cd elysium

# Set up a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

1. Create a configuration file:

```bash
cp config.example.json config.json
# Edit config.json with your settings
```

2. Run the main application:

```bash
python main.py
```

## Project Structure

```
elysium_v1.0/
│
├── __init__.py
├── config.py                    # Configuration handling
├── main.py                      # Entry point for the application
│
├── core/                        # Core modules
│   ├── __init__.py
│   ├── exchange.py              # Exchange connection management
│   ├── position_manager.py      # Manages positions and risk
│   ├── order_executor.py        # Executes and tracks orders
│   └── logger.py                # Logging functionality
│
├── data/                        # Data handling
│   ├── __init__.py
│   ├── market_data.py           # Market data fetching and processing
│   ├── user_data.py             # User account data 
│   └── persistence.py           # Data persistence utilities
│
├── strategies/                  # Strategy implementations
│   ├── __init__.py
│   ├── base_strategy.py         # Abstract base strategy class
│   ├── market_making/
│   │   ├── __init__.py
│   │   └── basic_mm.py          # Basic market making strategy
│   ├── arb/
│   │   ├── __init__.py
│   │   └── cross_exchange.py    # Cross-exchange arbitrage
│   └── trend_following/
│       ├── __init__.py
│       └── momentum.py          # Momentum-based strategy
│
├── utils/                       # Utility functions
│   ├── __init__.py
│   ├── constants.py             # Constants used across the app
│   ├── helpers.py               # Helper functions
│   └── validators.py            # Input validation
│
└── rebates/                     # Builder rebate implementations
    ├── __init__.py
    ├── rebate_manager.py        # Manages rebate selection and application
    └── rebate_strategies.py     # Different rebate strategies
```

## Configuration

Elysium uses a JSON configuration file for easy setup:

```json
{
  "exchange": {
    "base_url": "https://api.hyperliquid.xyz",
    "account_address": "YOUR_ADDRESS",
    "private_key": "YOUR_PRIVATE_KEY"
  },
  "strategy": {
    "name": "basic_market_making",
    "params": {
      "coin": "ETH",
      "order_size": 0.1,
      "min_spread": 0.002,
      "max_spread": 0.005
    }
  },
  "rebates": {
    "default_builder": "0x8c967E73E7B15087c42A10D344cFf4c96D877f1D",
    "default_fee_rate": 1,
    "strategy": "performance_based"
  },
  "risk": {
    "max_position": 5.0,
    "max_drawdown": 0.1
  }
}
```

## Available Strategies

### Market Making
- **Basic Market Making**: Simple spread-based market making
- **Advanced Market Making**: With inventory skew and volatility adjustment

### Trend Following
- **Momentum**: Based on price momentum signals
- **Moving Average**: Using moving average crossovers

### Arbitrage
- **Cross-Exchange**: Arbitrage between Hyperliquid and other exchanges

## Rebate Strategies

- **Default**: Use a default builder for all orders
- **Round-Robin**: Cycle through multiple builders
- **Performance-Based**: Choose builders based on historical performance
- **Market-Adaptive**: Adapt builder selection to market conditions

## Contributing

We welcome contributions to Elysium! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the [Hyperliquid Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)
- Inspired by [Hummingbot](https://github.com/hummingbot/hummingbot)'s architecture

## Disclaimer

Trading cryptocurrencies involves significant risk. This software is provided for educational and informational purposes only. You are responsible for your trading decisions and should understand the risks involved.
