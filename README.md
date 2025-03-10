# Elysium Trading Platform

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HyperLiquid](https://img.shields.io/badge/HyperLiquid-API-green.svg)](https://hyperliquid.xyz)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()

A professional command-line trading platform built for executing trades on the HyperLiquid exchange with simplicity and efficiency.

![Elysium Terminal](./poster.png)

## ✨ Features

- 🔄 Connect to HyperLiquid mainnet or testnet with different wallet credentials
- 💰 View account balances and positions with clear formatting
- 📊 Execute spot market buy/sell orders with customizable slippage
- 📈 Place spot limit buy/sell orders at your desired price
- 📉 Execute perpetual futures trading with customizable leverage
- 🚫 Easily cancel specific or all open orders
- 📜 View your complete trading history
- 🔐 Secure password protection for application access

## 🔜 Coming Soon

- 📐 **Scaled Orders** - Automate the creation of multiple orders at different price levels
- ⏱️ **TWAP Orders** - Time-Weighted Average Price execution strategy
- 📱 **Mobile Notifications** - Get alerts for order fills and liquidation warnings
- 📊 **Advanced Charting** - Interactive charts with technical indicators

## 🛠️ Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/elysium-trading.git
   cd elysium-trading
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

Before running Elysium, you need to create a `dontshareconfig.py` file containing your API credentials:

1. Create a new file named `dontshareconfig.py` in the project root
2. Add the following content to the file, replacing the empty strings with your actual credentials:

```python
# dontshareconfig.py - DO NOT COMMIT THIS FILE TO VERSION CONTROL
# Mainnet account credentials
mainnet_wallet = ""  # Your mainnet wallet address
mainnet_secret = ""  # Your mainnet private key
# Testnet account credentials
testnet_wallet = ""  # Your testnet wallet address
testnet_secret = ""  # Your testnet private key
```

**⚠️ Important**: Never share your private keys or commit the `dontshareconfig.py` file to version control.

## 🚀 Usage

Run the application:

```bash
python elysium.py
```

### First-Time Setup

On your first run, you'll be prompted to create a password for accessing the application.

### Basic Commands

Once inside the CLI, here are the core commands:

- `connect [mainnet|testnet]` - Connect to the specified HyperLiquid network
- `balance` - Show your current balances
- `positions` - Show your open positions
- `orders [symbol]` - List your open orders (optionally for a specific symbol)

### Spot Trading Commands

- Market orders:
  ```
  buy <symbol> <quantity> [slippage]
  sell <symbol> <quantity> [slippage]
  ```
  Example: `buy SUBWAY/USDC 10 0.03` (buys 10 SUBWAY with 3% slippage)

- Limit orders:
  ```
  limit_buy <symbol> <quantity> <price>
  limit_sell <symbol> <quantity> <price>
  ```
  Example: `limit_buy ETH/USDC 0.1 3500` (places a buy order for 0.1 ETH at $3500)

### Perpetual Trading Commands

- Market orders with leverage:
  ```
  perp_buy <symbol> <size> [leverage] [slippage]
  perp_sell <symbol> <size> [leverage] [slippage]
  ```
  Example: `perp_buy BTC 0.01 5 0.03` (buys 0.01 BTC with 5x leverage and 3% slippage)

- Limit orders with leverage:
  ```
  perp_limit_buy <symbol> <size> <price> [leverage]
  perp_limit_sell <symbol> <size> <price> [leverage]
  ```
  Example: `perp_limit_buy BTC 0.01 50000 5` (places limit buy for 0.01 BTC at $50,000 with 5x leverage)

- Position management:
  ```
  close_position <symbol> [slippage]
  set_leverage <symbol> <leverage>
  ```

### Order Management

- Cancel orders:
  ```
  cancel <symbol> <order_id>
  cancel_all [symbol]
  ```

### Additional Commands

- `help` - Display available commands
- `clear` - Clear the screen
- `exit` or `Ctrl+D` - Exit the application

## 📝 Important Notes

1. **Minimum Order Value**: Orders must have a minimum value of $10.

2. **Slippage**: For market orders, slippage is specified as a decimal (e.g., 0.03 for 3%).

3. **Symbol Format**: 
   - Spot trading: Use the format `SYMBOL/USDC` (e.g., `SUBWAY/USDC`, `ETH/USDC`)
   - Perpetual trading: Use the symbol name only (e.g., `BTC`, `ETH`)

4. **Leverage Risk**: Higher leverage increases liquidation risk. Use with caution.

## 🔧 Troubleshooting

If you encounter issues:

1. Check that you're connected to the exchange with `connect mainnet` or `connect testnet`
2. Verify you have sufficient funds for trading
3. Ensure your order meets the minimum value requirement ($10)
4. Double-check the symbol format
5. For issues with perpetual orders, verify your account has sufficient margin

## 📖 Example Workflow

```
>>> connect mainnet
Successfully connected to 0xb92e5A...

>>> balance
=== Current Balances ===
...

>>> perp_buy BTC 0.01 5
Executing perp market buy: 0.01 BTC with 5x leverage (slippage: 5.0%)
Perpetual market buy order executed successfully

>>> positions
=== Current Positions ===
...

>>> close_position BTC
Closing position for BTC (slippage: 5.0%)
Position closed successfully
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [HyperLiquid](https://hyperliquid.xyz) for their powerful trading API
- [eth-account](https://github.com/ethereum/eth-account) for Ethereum account management
- The open-source community for various tools and libraries used in this project

---

<p align="center">
  <sub>Built with ❤️ by $HWTR team</sub>
</p>
