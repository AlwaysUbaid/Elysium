import os
import logging
import json
from pathlib import Path
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

# Telegram imports
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackContext,
    Filters, CallbackQueryHandler, ConversationHandler
)

# Hyperliquid API imports
import hyperliquid
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(
    CONNECT_WALLET, CONNECT_SECRET, SELECTING_NETWORK,
    SYMBOL, SIDE, AMOUNT, LEVERAGE, PRICE, CONFIRMATION,
    ENTER_SYMBOL, VIEW_ORDERS, CANCEL_ORDER
) = range(12)

# User data storage
DATA_DIR = Path("user_data")
DATA_DIR.mkdir(exist_ok=True)

class HyperliquidTelegramBot:
    """Telegram bot for interacting with the Hyperliquid exchange"""
    
    def __init__(self, token):
        self.token = token
        self.user_connections = {}  # Store connection info for each user
        self.user_contexts = {}     # Store conversation contexts
        
        # Initialize bot
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher
        
        # Register handlers
        self._register_handlers()
        
        logger.info("Hyperliquid Telegram Bot initialized")
    
    def _register_handlers(self):
        """Register all command and message handlers"""
        # Welcome & Help handlers
        self.dispatcher.add_handler(CommandHandler("start", self.cmd_start))
        self.dispatcher.add_handler(CommandHandler("help", self.cmd_help))
        
        # Connection command handlers
        connect_handler = ConversationHandler(
            entry_points=[
                CommandHandler("connect", self.cmd_connect),
                CommandHandler("connect_mainnet", self.cmd_connect_mainnet),
                CommandHandler("connect_testnet", self.cmd_connect_testnet)
            ],
            states={
                CONNECT_WALLET: [MessageHandler(Filters.text & ~Filters.command, self.handle_wallet_input)],
                CONNECT_SECRET: [MessageHandler(Filters.text & ~Filters.command, self.handle_secret_input)],
                SELECTING_NETWORK: [
                    CallbackQueryHandler(self.handle_network_selection, pattern='^(mainnet|testnet)$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(connect_handler)
        
        # Switch network command
        self.dispatcher.add_handler(CommandHandler("switch_network", self.cmd_switch_network))
        
        # Status and info commands
        self.dispatcher.add_handler(CommandHandler("status", self.cmd_status))
        self.dispatcher.add_handler(CommandHandler("balance", self.cmd_balance))
        self.dispatcher.add_handler(CommandHandler("positions", self.cmd_positions))
        
        # Price command
        self.dispatcher.add_handler(CommandHandler("price", self.cmd_price))
        
        # Trading commands
        self.dispatcher.add_handler(CommandHandler("buy", self.cmd_buy))
        self.dispatcher.add_handler(CommandHandler("sell", self.cmd_sell))
        
        # Order management
        self.dispatcher.add_handler(CommandHandler("orders", self.cmd_orders))
        
        # Conversation handler for placing orders
        order_conv = ConversationHandler(
            entry_points=[
                CommandHandler("trade", self.start_trade_conversation),
                CallbackQueryHandler(self.start_trade_callback, pattern='^trade_')
            ],
            states={
                SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.handle_symbol_input)],
                SIDE: [CallbackQueryHandler(self.handle_side_selection, pattern='^(buy|sell)$')],
                AMOUNT: [MessageHandler(Filters.text & ~Filters.command, self.handle_amount_input)],
                LEVERAGE: [MessageHandler(Filters.text & ~Filters.command, self.handle_leverage_input)],
                PRICE: [MessageHandler(Filters.text & ~Filters.command, self.handle_price_input)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.handle_order_confirmation, pattern='^(confirm|cancel)$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(order_conv)
        
        # Cancellation handler
        cancel_order_conv = ConversationHandler(
            entry_points=[CommandHandler("cancel_order", self.start_cancel_order)],
            states={
                ENTER_SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.handle_cancel_symbol)],
                VIEW_ORDERS: [CallbackQueryHandler(self.handle_cancel_order_selection, pattern='^cancel_')],
                CONFIRMATION: [
                    CallbackQueryHandler(self.handle_cancel_confirmation, pattern='^(confirm|cancel)$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(cancel_order_conv)
        
        # Close position command
        self.dispatcher.add_handler(CommandHandler("close", self.cmd_close_position))
        
        # Enable market button
        self.dispatcher.add_handler(CommandHandler("menu", self.cmd_show_menu))
        
        # Callback queries
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Error handler
        self.dispatcher.add_error_handler(self.error_handler)
    
    def start(self):
        """Start the bot"""
        self.updater.start_polling()
        self.updater.idle()
    
    def load_user_data(self, user_id: int) -> Dict:
        """Load user data from disk"""
        user_file = DATA_DIR / f"user_{user_id}.json"
        if user_file.exists():
            try:
                with open(user_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading user data: {e}")
        return {}
    
    def save_user_data(self, user_id: int, data: Dict):
        """Save user data to disk"""
        user_file = DATA_DIR / f"user_{user_id}.json"
        try:
            with open(user_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving user data: {e}")
    
    def connect_exchange(self, user_id: int, wallet_address: str, secret_key: str, use_testnet: bool = False) -> bool:
        """Connect to the Hyperliquid exchange"""
        try:
            # Determine API URL
            api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
            
            # Initialize eth account
            from eth_account import Account
            wallet = Account.from_key(secret_key)
            
            # Initialize exchange and info clients
            exchange = Exchange(
                wallet,
                api_url,
                account_address=wallet_address
            )
            info = Info(api_url)
            
            # Test connection by getting user state
            user_state = info.user_state(wallet_address)
            
            # Store connection info
            self.user_connections[user_id] = {
                "wallet_address": wallet_address,
                "wallet": wallet,
                "exchange": exchange,
                "info": info,
                "is_testnet": use_testnet,
                "connected_at": datetime.now().isoformat()
            }
            
            # Save wallet and network info (not the secret key) to disk
            user_data = self.load_user_data(user_id)
            user_data.update({
                "wallet_address": wallet_address,
                "is_testnet": use_testnet,
                "last_connected_at": datetime.now().isoformat()
            })
            self.save_user_data(user_id, user_data)
            
            logger.info(f"User {user_id} connected to Hyperliquid {'testnet' if use_testnet else 'mainnet'}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to exchange: {str(e)}")
            return False
    
    def get_exchange_connection(self, user_id: int) -> Optional[Dict]:
        """Get exchange connection for a user"""
        return self.user_connections.get(user_id)
    
    def _format_number(self, number, decimal_places=2):
        """Format a number with appropriate decimal places"""
        if number < 0.001:
            return f"{number:.8f}"
        elif number < 1:
            return f"{number:.6f}"
        elif number < 10:
            return f"{number:.4f}"
        else:
            return f"{number:.2f}"
    
    # Command handlers
    def cmd_start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        
        # Check if user has connected before
        user_data = self.load_user_data(user.id)
        wallet_address = user_data.get("wallet_address")
        
        if wallet_address:
            # User has connected before
            message = (
                f"Welcome back to Hyperliquid Trading Bot, {user.first_name}!\n\n"
                f"Your last connected wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`\n\n"
                f"Use /connect to connect with new credentials or\n"
                f"Use /menu to show the trading menu\n"
                f"Use /help to see all available commands"
            )
        else:
            # First time user
            message = (
                f"Welcome to Hyperliquid Trading Bot, {user.first_name}!\n\n"
                f"To get started, you need to connect to the Hyperliquid exchange.\n\n"
                f"Use /connect_mainnet for mainnet\n"
                f"Use /connect_testnet for testnet\n"
                f"Use /help to see all available commands"
            )
        
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        message = (
            "*Hyperliquid Trading Bot Commands*\n\n"
            "*Connection:*\n"
            "/connect - Start connection process\n"
            "/connect_mainnet - Connect to mainnet\n"
            "/connect_testnet - Connect to testnet\n"
            "/switch_network - Switch between mainnet and testnet\n"
            "/status - Check connection status\n\n"
            
            "*Account Information:*\n"
            "/balance - View your account balance\n"
            "/positions - View your open positions\n"
            "/orders - View your open orders\n\n"
            
            "*Market Data:*\n"
            "/price <symbol> - Get current price for a symbol\n\n"
            
            "*Trading:*\n"
            "/trade - Start trading conversation\n"
            "/buy <symbol> <amount> <price> - Place a buy order\n"
            "/sell <symbol> <amount> <price> - Place a sell order\n"
            "/close <symbol> - Close a position\n"
            "/cancel_order - Cancel an open order\n\n"
            
            "*Menu:*\n"
            "/menu - Show trading menu with buttons\n"
        )
        
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    def cmd_connect(self, update: Update, context: CallbackContext):
        """Handle /connect command"""
        update.message.reply_text(
            "Please enter your wallet address:"
        )
        return CONNECT_WALLET
    
    def cmd_connect_mainnet(self, update: Update, context: CallbackContext):
        """Handle /connect_mainnet command"""
        # Store in context that we're connecting to mainnet
        if not context.user_data:
            context.user_data = {}
        context.user_data["is_testnet"] = False
        
        update.message.reply_text(
            "Connecting to *MAINNET*\n\n"
            "Please enter your wallet address:",
            parse_mode=ParseMode.MARKDOWN
        )
        return CONNECT_WALLET
    
    def cmd_connect_testnet(self, update: Update, context: CallbackContext):
        """Handle /connect_testnet command"""
        # Store in context that we're connecting to testnet
        if not context.user_data:
            context.user_data = {}
        context.user_data["is_testnet"] = True
        
        update.message.reply_text(
            "Connecting to *TESTNET*\n\n"
            "Please enter your wallet address:",
            parse_mode=ParseMode.MARKDOWN
        )
        return CONNECT_WALLET
    
    def handle_wallet_input(self, update: Update, context: CallbackContext):
        """Handle wallet address input"""
        wallet_address = update.message.text.strip()
        
        # Validate wallet address (basic check)
        if not wallet_address.startswith("0x") or len(wallet_address) != 42:
            update.message.reply_text(
                "❌ Invalid wallet address. It should be a 42-character hex string starting with '0x'.\n"
                "Please try again:"
            )
            return CONNECT_WALLET
        
        # Store wallet address in context
        if not context.user_data:
            context.user_data = {}
        context.user_data["wallet_address"] = wallet_address
        
        # Ask for secret key
        update.message.reply_text(
            "Please enter your secret key:\n\n"
            "⚠️ *This message will be deleted after processing for security*",
            parse_mode=ParseMode.MARKDOWN
        )
        return CONNECT_SECRET
    
    def handle_secret_input(self, update: Update, context: CallbackContext):
        """Handle secret key input"""
        secret_key = update.message.text.strip()
        
        # Delete the message containing the secret for security
        try:
            update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message with secret: {e}")
        
        # Store secret key in context (will not be persisted to disk)
        if not context.user_data:
            context.user_data = {}
        context.user_data["secret_key"] = secret_key
        
        # If network is not specified yet, ask user to select
        if "is_testnet" not in context.user_data:
            keyboard = [
                [
                    InlineKeyboardButton("Mainnet", callback_data="mainnet"),
                    InlineKeyboardButton("Testnet", callback_data="testnet")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                "Please select a network:",
                reply_markup=reply_markup
            )
            return SELECTING_NETWORK
        else:
            # Network is already specified, proceed with connection
            wallet_address = context.user_data.get("wallet_address")
            is_testnet = context.user_data.get("is_testnet", False)
            
            # Show connecting message
            connecting_message = update.message.reply_text(
                f"🔄 Connecting to Hyperliquid {'Testnet' if is_testnet else 'Mainnet'}..."
            )
            
            # Connect to exchange
            success = self.connect_exchange(
                update.effective_user.id,
                wallet_address,
                secret_key,
                is_testnet
            )
            
            if success:
                connecting_message.edit_text(
                    f"✅ Successfully connected to Hyperliquid {'Testnet' if is_testnet else 'Mainnet'}\n\n"
                    f"Wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`\n\n"
                    f"Use /menu to start trading",
                    parse_mode=ParseMode.MARKDOWN
                )
                self.send_menu(update, context)
            else:
                connecting_message.edit_text(
                    f"❌ Failed to connect to Hyperliquid. Please check your credentials and try again."
                )
            
            # Clear sensitive data from context
            if "secret_key" in context.user_data:
                del context.user_data["secret_key"]
            
            return ConversationHandler.END
    
    def handle_network_selection(self, update: Update, context: CallbackContext):
        """Handle network selection callback"""
        query = update.callback_query
        query.answer()
        
        selected_network = query.data
        is_testnet = selected_network == "testnet"
        
        # Store network selection in context
        if not context.user_data:
            context.user_data = {}
        context.user_data["is_testnet"] = is_testnet
        
        # Get credentials from context
        wallet_address = context.user_data.get("wallet_address")
        secret_key = context.user_data.get("secret_key")
        
        if not wallet_address or not secret_key:
            query.edit_message_text(
                "❌ Missing credentials. Please start again with /connect"
            )
            return ConversationHandler.END
        
        # Show connecting message
        query.edit_message_text(
            f"🔄 Connecting to Hyperliquid {'Testnet' if is_testnet else 'Mainnet'}..."
        )
        
        # Connect to exchange
        success = self.connect_exchange(
            update.effective_user.id,
            wallet_address,
            secret_key,
            is_testnet
        )
        
        if success:
            query.edit_message_text(
                f"✅ Successfully connected to Hyperliquid {'Testnet' if is_testnet else 'Mainnet'}\n\n"
                f"Wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`\n\n"
                f"Use /menu to start trading",
                parse_mode=ParseMode.MARKDOWN
            )
            # Send the menu keyboard
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Here's the trading menu:",
                reply_markup=self.get_menu_keyboard()
            )
        else:
            query.edit_message_text(
                f"❌ Failed to connect to Hyperliquid. Please check your credentials and try again."
            )
        
        # Clear sensitive data from context
        if "secret_key" in context.user_data:
            del context.user_data["secret_key"]
        
        return ConversationHandler.END
    
    def cmd_switch_network(self, update: Update, context: CallbackContext):
        """Handle /switch_network command"""
        user_id = update.effective_user.id
        connection = self.get_exchange_connection(user_id)
        
        if not connection:
            update.message.reply_text(
                "❌ You are not connected to any network. Use /connect first."
            )
            return
        
        # Get current network info
        is_currently_testnet = connection.get("is_testnet", False)
        wallet_address = connection.get("wallet_address")
        
        # Ask for confirmation
        keyboard = [
            [
                InlineKeyboardButton(
                    f"Switch to {'Mainnet' if is_currently_testnet else 'Testnet'}", 
                    callback_data=f"switch_to_{'mainnet' if is_currently_testnet else 'testnet'}"
                )
            ],
            [
                InlineKeyboardButton("Cancel", callback_data="switch_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"You are currently connected to *{'Testnet' if is_currently_testnet else 'Mainnet'}*\n\n"
            f"Do you want to switch to *{'Mainnet' if is_currently_testnet else 'Testnet'}*?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user_id = update.effective_user.id
        connection = self.get_exchange_connection(user_id)
        
        if not connection:
            # Check if user has saved data
            user_data = self.load_user_data(user_id)
            wallet_address = user_data.get("wallet_address")
            
            if wallet_address:
                update.message.reply_text(
                    "❌ You are currently disconnected.\n\n"
                    f"Last connected wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`\n\n"
                    "Use /connect to reconnect.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                update.message.reply_text(
                    "❌ You are not connected to any network. Use /connect first."
                )
            return
        
        # Get connection details
        wallet_address = connection.get("wallet_address")
        is_testnet = connection.get("is_testnet", False)
        connected_at = connection.get("connected_at")
        
        # Format connected time
        connected_time = "Unknown"
        if connected_at:
            try:
                connected_datetime = datetime.fromisoformat(connected_at)
                connected_time = connected_datetime.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        
        # Get additional status info
        try:
            info = connection.get("info")
            user_state = info.user_state(wallet_address)
            
            # Get account value
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            margin_used = float(margin_summary.get("totalMarginUsed", 0))
            
            # Get position count
            positions = []
            for asset_position in user_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                if float(position.get("szi", 0)) != 0:
                    positions.append(position)
            
            # Format status message
            message = (
                f"*Hyperliquid Status*\n\n"
                f"Network: {'Testnet' if is_testnet else 'Mainnet'}\n"
                f"Wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`\n"
                f"Connected at: {connected_time}\n\n"
                f"Account value: ${self._format_number(account_value)}\n"
                f"Margin used: ${self._format_number(margin_used)}\n"
                f"Open positions: {len(positions)}\n\n"
                f"Use /balance for detailed balance info\n"
                f"Use /positions to view open positions"
            )
        except Exception as e:
            logger.error(f"Error getting status info: {str(e)}")
            message = (
                f"*Hyperliquid Status*\n\n"
                f"Network: {'Testnet' if is_testnet else 'Mainnet'}\n"
                f"Wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`\n"
                f"Connected at: {connected_time}\n\n"
                f"❌ Error fetching account details: {str(e)}"
            )
        
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    def cmd_balance(self, update: Update, context: CallbackContext):
        """Handle /balance command"""
        user_id = update.effective_user.id
        connection = self.get_exchange_connection(user_id)
        
        if not connection:
            update.message.reply_text(
                "❌ You are not connected to any network. Use /connect first."
            )
            return
        
        # Get connection details
        wallet_address = connection.get("wallet_address")
        info = connection.get("info")
        
        try:
            # Show loading message
            loading_message = update.message.reply_text("🔄 Fetching balance information...")
            
            # Get spot balances
            spot_balances = []
            try:
                spot_state = info.spot_user_state(wallet_address)
                for balance in spot_state.get("balances", []):
                    if float(balance.get("total", 0)) > 0:
                        spot_balances.append({
                            "asset": balance.get("coin", ""),
                            "available": float(balance.get("available", 0)),
                            "total": float(balance.get("total", 0)),
                            "in_orders": float(balance.get("total", 0)) - float(balance.get("available", 0))
                        })
            except Exception as e:
                logger.error(f"Error fetching spot balances: {str(e)}")
            
            # Get perpetual account info
            perp_state = info.user_state(wallet_address)
            margin_summary = perp_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            margin_used = float(margin_summary.get("totalMarginUsed", 0))
            position_value = float(margin_summary.get("totalNtlPos", 0))
            
            # Format balance message
            message = f"*Hyperliquid Balance*\n\n"
            
            # Add spot balances if any
            if spot_balances:
                message += "*Spot Balances:*\n"
                for balance in spot_balances:
                    message += (
                        f"• {balance['asset']}: "
                        f"{self._format_number(balance['available'])} available, "
                        f"{self._format_number(balance['total'])} total\n"
                    )
                message += "\n"
            
            # Add perpetual account info
            message += "*Perpetual Account:*\n"
            message += f"• Account Value: ${self._format_number(account_value)}\n"
            message += f"• Margin Used: ${self._format_number(margin_used)} ({(margin_used/account_value*100) if account_value else 0:.2f}%)\n"
            message += f"• Position Value: ${self._format_number(position_value)}\n\n"
            
            message += "Use /positions to view open positions"
            
            # Edit loading message with results
            loading_message.edit_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            update.message.reply_text(f"❌ Error fetching balance: {str(e)}")
    
    def cmd_positions(self, update: Update, context: CallbackContext):
        """Handle /positions command"""
        user_id = update.effective_user.id
        connection = self.get_exchange_connection(user_id)
        
        if not connection:
            update.message.reply_text(
                "❌ You are not connected to any network. Use /connect first."
            )
            return
        
        # Get connection details
        wallet_address = connection.get("wallet_address")
        info = connection.get("info")
        
        try:
            # Show loading message
            loading_message = update.message.reply_text("🔄 Fetching position information...")
            
            # Get positions
            positions = []
            perp_state = info.user_state(wallet_address)
            for asset_position in perp_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                if float(position.get("szi", 0)) != 0:
                    positions.append({
                        "symbol": position.get("coin", ""),
                        "size": float(position.get("szi", 0)),
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0)),
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0))
                    })
            
            if not positions:
                loading_message.edit_text("No open positions")
                return
            
            # Format positions message
            message = f"*Open Positions*\n\n"
            
            for pos in positions:
                symbol = pos["symbol"]
                size = pos["size"]
                side = "Long" if size > 0 else "Short"
                entry = self._format_number(pos["entry_price"])
                mark = self._format_number(pos["mark_price"])
                liq = self._format_number(pos["liquidation_price"])
                pnl = self._format_number(pos["unrealized_pnl"])
                pnl_pct = (pos["mark_price"] / pos["entry_price"] - 1) * 100 * (1 if size > 0 else -1)
                
                message += (
                    f"*{symbol}:*\n"
                    f"• Side: {side}\n"
                    f"• Size: {abs(size)}\n"
                    f"• Entry: {entry}\n"
                    f"• Mark: {mark}\n"
                    f"• Liq Price: {liq}\n"
                    f"• PnL: {pnl} ({pnl_pct:.2f}%)\n\n"
                )
            
            # Add close position buttons
            keyboard = []
            for pos in positions:
                symbol = pos["symbol"]
                keyboard.append([
                    InlineKeyboardButton(f"Close {symbol}", callback_data=f"close_{symbol}")
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Edit loading message with results
            loading_message.edit_text(
                message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )