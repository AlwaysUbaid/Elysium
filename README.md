# Elysium Trading Platform

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HyperLiquid](https://img.shields.io/badge/HyperLiquid-API-green.svg)](https://hyperliquid.xyz)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)]()

A professional command-line trading platform built for executing trades on the HyperLiquid exchange with simplicity and efficiency.

![Elysium Terminal](./poster.png)

## ✨ Features

- 🔄 Connect to HyperLiquid mainnet or testnet with different wallet credentials
- 💰 View account balances and positions with clear formatting
- 📊 Execute spot market buy/sell orders with customizable slippage
- 📈 Place spot limit buy/sell orders at your desired price
- 📉 Execute perpetual futures trading with customizable leverage
- 📐 **Scaled Orders** - Create multiple orders at different price levels with custom distribution
- 📊 **Market-Aware Scaled Orders** - Automatically set price levels based on current market conditions
- ⏱️ **TWAP Orders** - Time-Weighted Average Price execution strategy
- 🚫 Easily cancel specific or all open orders
- 📜 View your complete trading history
- 🔐 Secure password protection for application access

## 🔜 Coming Soon

- 📱 **Mobile Notifications** - Get alerts for order fills and liquidation warnings
- 📊 **Advanced Charting** - Interactive charts with technical indicators
- 🤖 **Automated Strategies** - Implement custom trading strategies with triggers

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
  Example: `perp_limit_sell BTC 0.01 60000 5` (places limit sell for 0.01 BTC at $60,000 with 5x leverage)

- Position management:
  ```
  close_position <symbol> [slippage]
  set_leverage <symbol> <leverage>
  ```

### Advanced Order Strategies

#### Scaled Orders

Create multiple orders distributed across a price range:

- Spot scaled orders:
  ```
  scaled_buy <symbol> <total_size> <num_orders> <start_price> <end_price> [skew]
  scaled_sell <symbol> <total_size> <num_orders> <start_price> <end_price> [skew]
  ```
  Example: `scaled_buy ETH/USDC 0.5 5 3200 3000 0` (places 5 buy orders totaling 0.5 ETH from $3200 down to $3000 with equal distribution)

- Perpetual scaled orders:
  ```
  perp_scaled_buy <symbol> <total_size> <num_orders> <start_price> <end_price> [leverage] [skew]
  perp_scaled_sell <symbol> <total_size> <num_orders> <start_price> <end_price> [leverage] [skew]
  ```
  Example: `perp_scaled_buy BTC 0.1 5 65000 64000 5 1` (places 5 buy orders totaling 0.1 BTC from $65000 to $64000 with 5x leverage and moderate skew)

#### Market-Aware Scaled Orders

Place scaled orders automatically based on current market conditions:

```
market_scaled_buy <symbol> <total_size> <num_orders> [price_percent] [skew]
market_scaled_sell <symbol> <total_size> <num_orders> [price_percent] [skew]
```

Example: `market_scaled_buy PURR/USDC 10 5 2 0` (places 5 buy orders totaling 10 PURR from 2% below best ask to best bid)

#### TWAP Orders (Time-Weighted Average Price)

Execute orders over time to achieve a better average price:

```
twap_create <symbol> <side> <quantity> <duration_minutes> <num_slices> [price_limit] [is_perp] [leverage]
twap_start <twap_id>
twap_status <twap_id>
twap_stop <twap_id>
twap_list
```

Example: `twap_create ETH buy 0.5 30 5 3000` (creates a TWAP to buy 0.5 ETH over 30 minutes in 5 slices with a price limit of $3000)

### Order Management

- Cancel orders:
  ```
  cancel <symbol> <order_id>
  cancel_all [symbol]
  ```

### Help Commands

- `help` - Display available commands
- `help_scaled` - Detailed explanation of scaled orders
- `help_market_scaled` - Help for market-aware scaled orders
- `clear` - Clear the screen
- `exit` or `Ctrl+D` - Exit the application

## 📝 Important Notes

1. **Minimum Order Value**: Orders must have a minimum value of $10.

2. **Slippage**: For market orders, slippage is specified as a decimal (e.g., 0.03 for 3%).

3. **Symbol Format**: 
   - Spot trading: Use the format `SYMBOL/USDC` (e.g., `SUBWAY/USDC`, `ETH/USDC`)
   - Perpetual trading: Use the symbol name only (e.g., `BTC`, `ETH`)

4. **Leverage Risk**: Higher leverage increases liquidation risk. Use with caution.

5. **Skew Parameter**: For scaled orders, skew determines the size distribution:
   - `0.0` = Linear distribution (equal size for all orders)
   - `>0.0` = Exponential distribution (more weight to orders at better prices)
   - `1.0` = Moderate skew, `2.0` = Stronger skew, `3.0+` = Very aggressive skew

## 🔧 Troubleshooting

If you encounter issues:

1. Check that you're connected to the exchange with `connect mainnet` or `connect testnet`
2. Verify you have sufficient funds for trading
3. Ensure your order meets the minimum value requirement ($10)
4. Double-check the symbol format
5. For issues with perpetual orders, verify your account has sufficient margin
6. For scaled orders, confirm that your price range is reasonable for current market conditions

## 📖 Example Workflows

### Basic Trading

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

### Scaled Orders

```
>>> market_scaled_buy PURR/USDC 10 5 2 0

Current market for PURR/USDC:
Best bid: 5.6988
Best ask: 5.7557
Spread: 0.0569 (1.00%)

Placing 5 market-aware scaled buy orders for PURR/USDC:
Total size: 10.0
Price range: 5.635 to 5.6988
This places orders from 2% below best ask down to the best bid
Skew: 0.0

Do you want to proceed? (y/n): y

Successfully placed 5/5 orders
Order # | Size       | Price     
--------|------------|----------
1/5     | 2.00000000 | 5.63500000
2/5     | 2.00000000 | 5.65095000
3/5     | 2.00000000 | 5.66690000
4/5     | 2.00000000 | 5.68285000
5/5     | 2.00000000 | 5.69880000
```

### TWAP Execution

```
>>> twap_create ETH buy 0.5 30 5 3000
Created TWAP execution twap_20240311082145_1

>>> twap_start twap_20240311082145_1
Started TWAP execution twap_20240311082145_1

>>> twap_status twap_20240311082145_1
=== TWAP Execution Status: twap_20240311082145_1 ===
Symbol: ETH
Side: buy
Status: active
Order Type: Spot
Total Quantity: 0.5
Duration: 30 minutes
Slices: 2/5 (40.0%)
Executed: 0.2/0.5 (40.0%)
Average Execution Price: 2998.75
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