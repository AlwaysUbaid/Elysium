# Elysium Trading Platform

Elysium is a simplified command-line trading platform for executing trades on the Hyperliquid exchange. This tool provides a streamlined interface for performing market and limit orders, checking balances, and managing your trading activities.

## Features

- Connect to Hyperliquid mainnet or testnet
- View account balances and positions
- Execute market buy/sell orders
- Place limit buy/sell orders
- Cancel specific or all open orders
- View trading history

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/elysium-trading.git
   cd elysium-trading
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

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

**Important**: Never share your private keys or commit the `dontshareconfig.py` file to version control.

## Usage

Run the application:

```
python elysium.py
```

### First-Time Setup

On your first run, you'll be prompted to create a password for accessing the application.

### Basic Commands

Once inside the CLI, here are the core commands:

- `connect [mainnet|testnet]` - Connect to the specified Hyperliquid network
- `balance` - Show your current balances
- `positions` - Show your open positions
- `orders [symbol]` - List your open orders (optionally for a specific symbol)

### Trading Commands

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

- Cancel orders:
  ```
  cancel <symbol> <order_id>
  cancel_all [symbol]
  ```

### Additional Commands

- `help` - Display available commands
- `clear` - Clear the screen
- `exit` or `Ctrl+D` - Exit the application

## Important Notes

1. **Minimum Order Value**: Orders must have a minimum value of $10. Make sure the quantity × price of your order meets this requirement.

2. **Slippage**: For market orders, slippage is specified as a decimal (e.g., 0.03 for 3%).

3. **Symbol Format**: Use the correct format for symbols (e.g., `SUBWAY/USDC`, `ETH/USDC`).

4. **Network Selection**: Be careful when switching between mainnet and testnet. Ensure you're trading on the intended network.

## Troubleshooting

If you encounter issues:

1. Check that you're connected to the exchange with `connect mainnet` or `connect testnet`
2. Verify you have sufficient funds for trading
3. Ensure your order meets the minimum value requirement ($10)
4. Double-check the symbol format

## License

This project is licensed under the MIT License - see the LICENSE file for details.
