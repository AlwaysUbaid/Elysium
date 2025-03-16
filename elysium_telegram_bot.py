import os
import sys
import logging
import json
import time
import re
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

# Telegram imports
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackContext,
    Filters, CallbackQueryHandler, ConversationHandler
)

# Import Elysium components
from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation handlers
SELECTING_NETWORK, PASSWORD_AUTH, PASSWORD_SETUP, CONFIRM_PASSWORD, SYMBOL, SIDE, AMOUNT, PRICE, CONFIRMATION = range(9)

class ElysiumTelegramBot:
    """Telegram bot for Elysium Trading Platform"""
    
    def __init__(self, api_connector, order_handler, config_manager, logger):
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.logger = logger
        
        # Bot state
        self.connected = False
        self.is_testnet = False
        self.authenticated_users = set()  # Track authenticated users
        self.connection_contexts = {}  # Store connection context per user
        self.trading_context = {}
        
        # Initialize Telegram token
        try:
            import dontshareconfig as ds
            self.telegram_token = getattr(ds, 'telegram_token', None)
            self.admin_user_ids = getattr(ds, 'telegram_admin_ids', [])
        except ImportError:
            self.logger.warning("dontshareconfig.py not found. Telegram bot will use environment variables")
            self.telegram_token = os.environ.get('TELEGRAM_TOKEN')
            admin_ids_str = os.environ.get('ADMIN_USER_IDS', '')
            self.admin_user_ids = list(map(int, admin_ids_str.split(','))) if admin_ids_str else []
        
        if not self.telegram_token:
            self.logger.error("No Telegram token found! Telegram bot will not start.")
            return
        
        # Initialize Telegram updater
        self.updater = Updater(self.telegram_token)
        self.dispatcher = self.updater.dispatcher
        
        # Register handlers
        self._register_handlers()
        
        self.logger.info("Elysium Telegram Bot initialized")
    
    def _register_handlers(self):
        """Register all command and message handlers"""
        # Welcome handler
        self.dispatcher.add_handler(CommandHandler("start", self.cmd_start))
        
        # Authentication conversation
        auth_conv = ConversationHandler(
            entry_points=[
                CommandHandler("connect", self.select_network),
                CallbackQueryHandler(self.select_network_callback, pattern='^network_')
            ],
            states={
                SELECTING_NETWORK: [
                    CallbackQueryHandler(self.select_network_callback, pattern='^network_')
                ],
                PASSWORD_AUTH: [
                    MessageHandler(Filters.text & ~Filters.command, self.password_auth)
                ],
                PASSWORD_SETUP: [
                    MessageHandler(Filters.text & ~Filters.command, self.password_setup)
                ],
                CONFIRM_PASSWORD: [
                    MessageHandler(Filters.text & ~Filters.command, self.confirm_password)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(auth_conv)
        
        # Main menu handler
        self.dispatcher.add_handler(CommandHandler("menu", self.show_main_menu))
        
        # Account info commands
        self.dispatcher.add_handler(CommandHandler("balance", self.cmd_balance))
        self.dispatcher.add_handler(CommandHandler("positions", self.cmd_positions))
        self.dispatcher.add_handler(CommandHandler("orders", self.cmd_orders))
        
        # Help and status
        self.dispatcher.add_handler(CommandHandler("help", self.cmd_help))
        self.dispatcher.add_handler(CommandHandler("status", self.cmd_status))
        
        # Advanced menu
        self.dispatcher.add_handler(CommandHandler("advanced", self.show_advanced_menu))
        
        # Trading handlers (accessible from both menus)
        spot_order_conv = ConversationHandler(
            entry_points=[CommandHandler("spot", self.spot_start)],
            states={
                SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.spot_symbol)],
                SIDE: [MessageHandler(Filters.text & ~Filters.command, self.spot_side)],
                AMOUNT: [MessageHandler(Filters.text & ~Filters.command, self.spot_amount)],
                PRICE: [MessageHandler(Filters.text & ~Filters.command, self.spot_price)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.spot_confirm, pattern='^confirm$'),
                    CallbackQueryHandler(self.spot_cancel, pattern='^cancel$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(spot_order_conv)
        
        perp_order_conv = ConversationHandler(
            entry_points=[CommandHandler("perp", self.perp_start)],
            states={
                SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.perp_symbol)],
                SIDE: [MessageHandler(Filters.text & ~Filters.command, self.perp_side)],
                AMOUNT: [MessageHandler(Filters.text & ~Filters.command, self.perp_amount)],
                PRICE: [MessageHandler(Filters.text & ~Filters.command, self.perp_price)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.perp_confirm, pattern='^confirm$'),
                    CallbackQueryHandler(self.perp_cancel, pattern='^cancel$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(perp_order_conv)
        
        # Close position handler
        self.dispatcher.add_handler(CommandHandler("close", self.cmd_close_position))
        
        # Menu callbacks
        self.dispatcher.add_handler(CallbackQueryHandler(self.menu_callback))
        
        # Error handler
        self.dispatcher.add_error_handler(self.error_handler)
    
    def start(self):
        """Start the bot in a separate thread"""
        if not hasattr(self, 'updater'):
            self.logger.error("Telegram bot not properly initialized")
            return
        
        self.logger.info("Starting Elysium Telegram Bot")
        self.updater.start_polling()
    
    def stop(self):
        """Stop the bot"""
        if hasattr(self, 'updater'):
            self.logger.info("Stopping Elysium Telegram Bot")
            self.updater.stop()
    
    def update_connection_status(self, connected, is_testnet=False):
        """Update the connection status when the main app connects"""
        self.connected = connected
        self.is_testnet = is_testnet
    
    def _is_authorized(self, user_id):
        """Check if a user is authorized to use this bot"""
        return user_id in self.admin_user_ids
    
    def _is_authenticated(self, user_id):
        """Check if user is authenticated (after password)"""
        return user_id in self.authenticated_users
    
    def _check_auth(self, update: Update, context: CallbackContext):
        """Check if the user is authorized and authenticated"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return False
            
        if not self._is_authenticated(user_id):
            update.message.reply_text(
                "You need to connect and authenticate first.\n"
                "Use /connect to start."
            )
            return False
            
        return True
    
    def _check_connection(self, update: Update, context: CallbackContext):
        """Check if the bot is connected to the exchange"""
        if not self.connected:
            if hasattr(update, 'message') and update.message:
                update.message.reply_text("❌ Not connected to exchange. Use /connect first.")
            else:
                update.callback_query.answer("Not connected to exchange")
                update.callback_query.edit_message_text("❌ Not connected to exchange. Use /connect first.")
            return False
        return True
    
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
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        update.message.reply_text(
            f"🚀 *Welcome to Elysium Trading Bot!*\n\n"
            f"This bot allows you to control your Elysium trading platform remotely.\n\n"
            f"To get started:\n"
            f"1. Use /connect to connect to an exchange\n"
            f"2. Use /menu to see available commands\n"
            f"3. Use /help for detailed instructions",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def select_network(self, update: Update, context: CallbackContext):
        """Start connection by selecting network"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return ConversationHandler.END
        
        keyboard = [
            [
                InlineKeyboardButton("Mainnet", callback_data="network_mainnet"),
                InlineKeyboardButton("Testnet", callback_data="network_testnet")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "Please select a network to connect to:",
            reply_markup=reply_markup
        )
        return SELECTING_NETWORK
    
    def select_network_callback(self, update: Update, context: CallbackContext):
        """Handle network selection"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        if not self._is_authorized(user_id):
            query.edit_message_text("⛔ You are not authorized to use this bot.")
            return ConversationHandler.END
        
        network = query.data.split("_")[1]
        self.connection_contexts[user_id] = {"network": network}
        
        # Check if password is already set
        if self.config_manager.get('password_hash'):
            query.edit_message_text(
                f"Selected {network.upper()}. Please enter your password:"
            )
            return PASSWORD_AUTH
        else:
            query.edit_message_text(
                "First-time setup. Please create a password:"
            )
            return PASSWORD_SETUP
    
    def password_auth(self, update: Update, context: CallbackContext):
        """Authenticate with existing password"""
        user_id = update.effective_user.id
        password = update.message.text
        
        # Delete the message containing the password for security
        try:
            context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            self.logger.warning(f"Could not delete password message: {str(e)}")
        
        if self.config_manager.verify_password(password):
            # Connect to the exchange
            network = self.connection_contexts[user_id]["network"]
            self._connect_to_exchange(update, context, network == "testnet")
            
            # Mark as authenticated
            self.authenticated_users.add(user_id)
            
            # Show main menu
            self.show_main_menu(update, context)
            return ConversationHandler.END
        else:
            update.message.reply_text(
                "❌ Incorrect password. Please try again:"
            )
            return PASSWORD_AUTH
    
    def password_setup(self, update: Update, context: CallbackContext):
        """Set up a new password"""
        user_id = update.effective_user.id
        password = update.message.text
        
        # Delete the message containing the password for security
        try:
            context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            self.logger.warning(f"Could not delete password message: {str(e)}")
        
        self.connection_contexts[user_id]["new_password"] = password
        
        update.message.reply_text(
            "Please confirm your password:"
        )
        return CONFIRM_PASSWORD
    
    def confirm_password(self, update: Update, context: CallbackContext):
        """Confirm new password"""
        user_id = update.effective_user.id
        confirm_password = update.message.text
        new_password = self.connection_contexts[user_id]["new_password"]
        
        # Delete the message containing the password for security
        try:
            context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            self.logger.warning(f"Could not delete password message: {str(e)}")
        
        if confirm_password == new_password:
            # Set the password
            self.config_manager.set_password(new_password)
            
            # Connect to the exchange
            network = self.connection_contexts[user_id]["network"]
            self._connect_to_exchange(update, context, network == "testnet")
            
            # Mark as authenticated
            self.authenticated_users.add(user_id)
            
            # Show main menu
            self.show_main_menu(update, context)
            return ConversationHandler.END
        else:
            update.message.reply_text(
                "❌ Passwords don't match. Please start again with /connect"
            )
            return ConversationHandler.END
    
    def _connect_to_exchange(self, update, context, use_testnet=False):
        """Connect to the exchange"""
        network_name = "testnet" if use_testnet else "mainnet"
        
        message = update.message if hasattr(update, 'message') and update.message else None
        user_id = update.effective_user.id
        
        if message:
            message.reply_text(f"🔄 Connecting to Hyperliquid {network_name}...")
        
        try:
            # Import credentials from dontshareconfig
            import dontshareconfig as ds
            
            if use_testnet:
                wallet_address = ds.testnet_wallet
                secret_key = ds.testnet_secret
            else:
                wallet_address = ds.mainnet_wallet
                secret_key = ds.mainnet_secret
            
            success = self.api_connector.connect_hyperliquid(wallet_address, secret_key, use_testnet)
            
            if success:
                self.connected = True
                self.is_testnet = use_testnet
                
                # Initialize order handler if needed
                if self.order_handler.exchange is None:
                    self.order_handler.exchange = self.api_connector.exchange
                    self.order_handler.info = self.api_connector.info
                    self.order_handler.wallet_address = wallet_address
                
                if message:
                    message.reply_text(
                        f"✅ Successfully connected to Hyperliquid {network_name}\n"
                        f"Address: `{wallet_address[:6]}...{wallet_address[-4:]}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                return True
            else:
                if message:
                    message.reply_text(f"❌ Failed to connect to Hyperliquid {network_name}")
                return False
        except Exception as e:
            self.logger.error(f"Error connecting to {network_name}: {str(e)}")
            if message:
                message.reply_text(f"❌ Error connecting to {network_name}: {str(e)}")
            return False
    
    def show_main_menu(self, update: Update, context: CallbackContext):
        """Show the main menu with basic operations"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            if hasattr(update, 'message') and update.message:
                update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        if not self._is_authenticated(user_id):
            if hasattr(update, 'message') and update.message:
                update.message.reply_text(
                    "Please connect and authenticate first.\n"
                    "Use /connect to start."
                )
            return
        
        keyboard = [
            [KeyboardButton("💰 Balance"), KeyboardButton("📊 Positions")],
            [KeyboardButton("📝 Orders"), KeyboardButton("❌ Close Position")],
            [KeyboardButton("🔄 Status"), KeyboardButton("⚙️ Advanced")]
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=False
        )
        
        connection_status = "Connected" if self.connected else "Not connected"
        network = "testnet" if self.is_testnet else "mainnet"
        network_emoji = "🧪" if self.is_testnet else "🌐"
        
        message = (
            f"*Elysium Trading Bot - Main Menu*\n\n"
            f"Status: {connection_status}\n"
            f"Network: {network_emoji} {network.upper()}\n\n"
            f"Choose an option from the menu below:"
        )
        
        if hasattr(update, 'message') and update.message:
            update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            query = update.callback_query
            query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Main menu activated.",
                reply_markup=reply_markup
            )
    
    def show_advanced_menu(self, update: Update, context: CallbackContext):
        """Show advanced trading options"""
        if not self._check_auth(update, context):
            return
        
        keyboard = [
            [
                InlineKeyboardButton("📈 Spot Market Buy", callback_data="action_spot_buy"),
                InlineKeyboardButton("📉 Spot Market Sell", callback_data="action_spot_sell")
            ],
            [
                InlineKeyboardButton("📊 Perp Market Buy", callback_data="action_perp_buy"),
                InlineKeyboardButton("📊 Perp Market Sell", callback_data="action_perp_sell")
            ],
            [
                InlineKeyboardButton("📝 Limit Orders", callback_data="action_limit"),
                InlineKeyboardButton("🔄 TWAP", callback_data="action_twap")
            ],
            [
                InlineKeyboardButton("⚖️ Set Leverage", callback_data="action_leverage"),
                InlineKeyboardButton("❌ Cancel Orders", callback_data="action_cancel")
            ],
            [
                InlineKeyboardButton("« Back to Main Menu", callback_data="action_main_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "*Advanced Trading Options*\n\n"
            "These options provide more control over your trading activities.\n"
            "Select an option:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    def menu_callback(self, update: Update, context: CallbackContext):
        """Handle menu button callbacks"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        if not self._is_authorized(user_id) or not self._is_authenticated(user_id):
            query.edit_message_text("⛔ You need to authenticate first. Use /connect")
            return
        
        action = query.data.split("_", 1)[1]
        
        # Handle basic actions
        if action == "main_menu":
            self.show_main_menu(update, context)
        elif action == "spot_buy":
            query.edit_message_text("Let's place a spot market buy order.")
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Use /spot to start the order process"
            )
        elif action == "spot_sell":
            query.edit_message_text("Let's place a spot market sell order.")
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Use /spot to start the order process"
            )
        elif action == "perp_buy":
            query.edit_message_text("Let's place a perpetual market buy order.")
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Use /perp to start the order process"
            )
        elif action == "perp_sell":
            query.edit_message_text("Let's place a perpetual market sell order.")
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Use /perp to start the order process"
            )
        # Add handlers for other advanced actions...
        else:
            query.edit_message_text(f"Action {action} not implemented yet")
    
    def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        update.message.reply_text(
            "*Elysium Trading Bot Commands:*\n\n"
            "*Basic Commands:*\n"
            "/connect - Connect to exchange\n"
            "/menu - Show main menu\n"
            "/help - Show this help message\n"
            "/status - Show connection status\n\n"
            
            "*Account Info:*\n"
            "/balance - Show account balance\n"
            "/positions - Show open positions\n"
            "/orders - Show open orders\n\n"
            
            "*Trading:*\n"
            "/spot - Create spot market/limit order\n"
            "/perp - Create perpetual market/limit order\n"
            "/close <symbol> - Close a position\n\n"
            
            "*Advanced:*\n"
            "/advanced - Show advanced trading options\n",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        status = "Connected" if self.connected else "Not connected"
        network = "testnet" if self.is_testnet else "mainnet"
        
        message = f"*Elysium Bot Status:*\n\n"
        message += f"Status: {status}\n"
        
        if self.connected:
            message += f"Network: {network.upper()}\n"
            message += f"Address: `{self.api_connector.wallet_address[:6]}...{self.api_connector.wallet_address[-4:]}`\n"
            
            # Add position summary if available
            try:
                positions = self.order_handler.get_positions()
                if positions:
                    message += "\n*Open Positions:*\n"
                    for pos in positions:
                        symbol = pos.get("symbol", "")
                        size = pos.get("size", 0)
                        side = "Long" if size > 0 else "Short"
                        entry = self._format_number(pos.get("entry_price", 0))
                        pnl = self._format_number(pos.get("unrealized_pnl", 0))
                        message += f"• {symbol}: {side} {abs(size)} @ {entry} (PnL: {pnl})\n"
            except Exception as e:
                self.logger.error(f"Error getting positions for status: {str(e)}")
        
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    def cmd_balance(self, update: Update, context: CallbackContext):
        """Handle /balance command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        update.message.reply_text("🔄 Fetching balance information...")
        
        try:
            balances = self.api_connector.get_balances()
            
            message = "*Account Balances:*\n\n"
            
            # Format spot balances
            if balances.get("spot"):
                message += "*Spot Balances:*\n"
                for balance in balances["spot"]:
                    if float(balance.get("total", 0)) > 0:
                        message += (
                            f"• {balance.get('asset')}: "
                            f"{self._format_number(balance.get('available', 0))} available, "
                            f"{self._format_number(balance.get('total', 0))} total\n"
                        )
                message += "\n"
            
            # Format perpetual account
            if balances.get("perp"):
                message += "*Perpetual Account:*\n"
                message += f"• Account Value: ${self._format_number(balances['perp'].get('account_value', 0))}\n"
                message += f"• Margin Used: ${self._format_number(balances['perp'].get('margin_used', 0))}\n"
                message += f"• Position Value: ${self._format_number(balances['perp'].get('position_value', 0))}\n"
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger.error(f"Error fetching balance: {str(e)}")
            update.message.reply_text(f"❌ Error fetching balance: {str(e)}")
    
    def cmd_positions(self, update: Update, context: CallbackContext):
        """Handle /positions command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        update.message.reply_text("🔄 Fetching position information...")
        
        try:
            positions = self.api_connector.get_positions()
            
            if not positions:
                update.message.reply_text("No open positions")
                return
            
            message = "*Open Positions:*\n\n"
            for pos in positions:
                symbol = pos.get("symbol", "")
                size = pos.get("size", 0)
                side = "Long" if size > 0 else "Short"
                entry = self._format_number(pos.get("entry_price", 0))
                mark = self._format_number(pos.get("mark_price", 0))
                liq = self._format_number(pos.get("liquidation_price", 0))
                pnl = self._format_number(pos.get("unrealized_pnl", 0))
                
                message += (
                    f"*{symbol}:*\n"
                    f"• Side: {side}\n"
                    f"• Size: {abs(size)}\n"
                    f"• Entry: {entry}\n"
                    f"• Mark: {mark}\n"
                    f"• Liq Price: {liq}\n"
                    f"• Unrealized PnL: {pnl}\n\n"
                )
                
                # Add close button for each position
                keyboard = [
                    [InlineKeyboardButton(f"Close {symbol} Position", callback_data=f"close_{symbol}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            update.message.reply_text(f"❌ Error fetching positions: {str(e)}")
    
    def cmd_orders(self, update: Update, context: CallbackContext):
        """Handle /orders command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        update.message.reply_text("🔄 Fetching open orders...")
        
        try:
            orders = self.api_connector.get_open_orders()
            
            if not orders:
                update.message.reply_text("No open orders")
                return
            
            message = "*Open Orders:*\n\n"
            for order in orders:
                symbol = order.get("coin", "")
                side = "Buy" if order.get("side", "") == "B" else "Sell"
                size = self._format_number(float(order.get("sz", 0)))
                price = self._format_number(float(order.get("limitPx", 0)))
                order_id = order.get("oid", 0)
                
                message += (
                    f"*{symbol}:*\n"
                    f"• Side: {side}\n"
                    f"• Size: {size}\n"
                    f"• Price: {price}\n"
                    f"• Order ID: {order_id}\n\n"
                )
                
                # Add cancel button for each order
                keyboard = [
                    [InlineKeyboardButton(f"Cancel Order #{order_id}", callback_data=f"cancel_{symbol}_{order_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error fetching orders: {str(e)}")
            update.message.reply_text(f"❌ Error fetching orders: {str(e)}")
    
    def cmd_close_position(self, update: Update, context: CallbackContext):
        """Handle /close command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        # Get the list of positions
        try:
            positions = self.api_connector.get_positions()
            
            if not positions:
                update.message.reply_text("No open positions to close")
                return
            
            if context.args and len(context.args) > 0:
                # Direct close using command argument
                symbol = context.args[0].upper()
                self._close_position(update, context, symbol)
            else:
                # Show position selection menu
                keyboard = []
                for pos in positions:
                    symbol = pos.get("symbol", "")
                    size = pos.get("size", 0)
                    side = "Long" if size > 0 else "Short"
                    keyboard.append([
                        InlineKeyboardButton(
                            f"Close {symbol} ({side} {abs(size)})", 
                            callback_data=f"close_{symbol}"
                        )
                    ])
                
                keyboard.append([InlineKeyboardButton("Cancel", callback_data="close_cancel")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                update.message.reply_text(
                    "Select a position to close:",
                    reply_markup=reply_markup
                )
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            update.message.reply_text(f"❌ Error getting positions: {str(e)}")
    
    def _close_position(self, update, context, symbol):
        """Close a specific position"""
        try:
            # Display processing message
            message = update.message if hasattr(update, 'message') and update.message else None
            if message:
                processing_msg = message.reply_text(f"🔄 Closing position for {symbol}...")
            
            # Execute the close
            result = self.order_handler.close_position(symbol)
            
            # Format response
            if result["status"] == "ok":
                details = ""
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            details = f"Filled: {filled['totalSz']} @ {filled['avgPx']}"
                
                response_text = f"✅ Position for {symbol} closed successfully\n{details}"
            else:
                response_text = f"❌ Failed to close position: {result.get('message', 'Unknown error')}"
            
            # Send or edit message
            if hasattr(update, 'callback_query') and update.callback_query:
                update.callback_query.edit_message_text(response_text)
            elif message:
                if 'processing_msg' in locals():
                    context.bot.edit_message_text(
                        chat_id=message.chat_id,
                        message_id=processing_msg.message_id,
                        text=response_text
                    )
                else:
                    message.reply_text(response_text)
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            error_text = f"❌ Error closing position: {str(e)}"
            
            if hasattr(update, 'callback_query') and update.callback_query:
                update.callback_query.edit_message_text(error_text)
            elif hasattr(update, 'message') and update.message:
                update.message.reply_text(error_text)
    
    # Spot order conversation handlers
    def spot_start(self, update: Update, context: CallbackContext):
        """Start the spot order conversation"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return ConversationHandler.END
        
        user_id = update.effective_user.id
        self.trading_context[user_id] = {
            "type": "spot",
            "symbol": None,
            "side": None,
            "amount": None,
            "price": None,
            "is_market": False
        }
        
        update.message.reply_text(
            "Creating a new spot order.\n\n"
            "Please enter the trading symbol (e.g., ETH):"
        )
        return SYMBOL
    
    def spot_symbol(self, update: Update, context: CallbackContext):
        """Handle symbol input for spot order"""
        user_id = update.effective_user.id
        symbol = update.message.text.strip().upper()
        
        self.trading_context[user_id]["symbol"] = symbol
        
        keyboard = [
            [KeyboardButton("BUY"), KeyboardButton("SELL")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        update.message.reply_text(
            f"Symbol set to {symbol}.\n\n"
            f"Please select the side (buy or sell):",
            reply_markup=reply_markup
        )
        return SIDE
    
    def spot_side(self, update: Update, context: CallbackContext):
        """Handle side input for spot order"""
        user_id = update.effective_user.id
        side = update.message.text.strip().lower()
        
        if side not in ["buy", "sell"]:
            update.message.reply_text(
                "Invalid side. Please enter 'buy' or 'sell':"
            )
            return SIDE
        
        self.trading_context[user_id]["side"] = side
        
        update.message.reply_text(
            f"Side set to {side}.\n\n"
            f"Please enter the amount:"
        )
        return AMOUNT
    
    def spot_amount(self, update: Update, context: CallbackContext):
        """Handle amount input for spot order"""
        user_id = update.effective_user.id
        amount_text = update.message.text.strip()
        
        try:
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as e:
            update.message.reply_text(
                f"Invalid amount: {str(e)}. Please enter a valid positive number:"
            )
            return AMOUNT
        
        self.trading_context[user_id]["amount"] = amount
        
        keyboard = [
            [KeyboardButton("MARKET")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        update.message.reply_text(
            f"Amount set to {amount}.\n\n"
            f"Please enter the price (or type 'MARKET' for a market order):",
            reply_markup=reply_markup
        )
        return PRICE
    
    def spot_price(self, update: Update, context: CallbackContext):
        """Handle price input for spot order"""
        user_id = update.effective_user.id
        price_text = update.message.text.strip().upper()
        
        if price_text == "MARKET":
            self.trading_context[user_id]["is_market"] = True
            self.trading_context[user_id]["price"] = None
        else:
            try:
                price = float(price_text)
                if price <= 0:
                    raise ValueError("Price must be positive")
                self.trading_context[user_id]["price"] = price
                self.trading_context[user_id]["is_market"] = False
            except ValueError as e:
                update.message.reply_text(
                    f"Invalid price: {str(e)}. Please enter a valid positive number or 'MARKET':"
                )
                return PRICE
        
        # Create confirmation message
        trade_details = self.trading_context[user_id]
        symbol = trade_details["symbol"]
        side = trade_details["side"].upper()
        amount = trade_details["amount"]
        
        if trade_details["is_market"]:
            order_type = "MARKET"
            price_text = "Market Price"
        else:
            order_type = "LIMIT"
            price_text = str(trade_details["price"])
        
        message = (
            f"*Order Confirmation:*\n\n"
            f"Type: Spot {order_type}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Amount: {amount}\n"
            f"Price: {price_text}\n\n"
            f"Please confirm your order:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("Confirm", callback_data="confirm"),
                InlineKeyboardButton("Cancel", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return CONFIRMATION
    
    def spot_confirm(self, update: Update, context: CallbackContext):
        """Handle order confirmation for spot order"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        trade_details = self.trading_context[user_id]
        symbol = trade_details["symbol"]
        side = trade_details["side"]
        amount = trade_details["amount"]
        price = trade_details["price"]
        is_market = trade_details["is_market"]
        
        try:
            result = None
            if is_market:
                if side == "buy":
                    result = self.order_handler.market_buy(symbol, amount)
                else:
                    result = self.order_handler.market_sell(symbol, amount)
            else:
                if side == "buy":
                    result = self.order_handler.limit_buy(symbol, amount, price)
                else:
                    result = self.order_handler.limit_sell(symbol, amount, price)
            
            if result and result["status"] == "ok":
                order_type = "market" if is_market else "limit"
                query.edit_message_text(
                    f"✅ {order_type.capitalize()} {side} order for {amount} {symbol} executed successfully!"
                )
            else:
                error_msg = result.get("message", "Unknown error") if result else "Unknown error"
                query.edit_message_text(
                    f"❌ Order failed: {error_msg}"
                )
        except Exception as e:
            self.logger.error(f"Error executing spot order: {str(e)}")
            query.edit_message_text(
                f"❌ Error executing order: {str(e)}"
            )
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        return ConversationHandler.END
    
    def spot_cancel(self, update: Update, context: CallbackContext):
        """Handle order cancellation for spot order"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        query.edit_message_text("Order cancelled")
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        return ConversationHandler.END
    
    # Perp order conversation handlers
    def perp_start(self, update: Update, context: CallbackContext):
        """Start the perpetual order conversation"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return ConversationHandler.END
        
        user_id = update.effective_user.id
        self.trading_context[user_id] = {
            "type": "perp",
            "symbol": None,
            "side": None,
            "amount": None,
            "price": None,
            "is_market": False,
            "leverage": 1  # Default leverage
        }
        
        update.message.reply_text(
            "Creating a new perpetual order.\n\n"
            "Please enter the trading symbol (e.g., BTC):"
        )
        return SYMBOL
    
    def perp_symbol(self, update: Update, context: CallbackContext):
        """Handle symbol input for perp order"""
        user_id = update.effective_user.id
        symbol = update.message.text.strip().upper()
        
        self.trading_context[user_id]["symbol"] = symbol
        
        # Create keyboard for common leverage options
        keyboard = [
            [KeyboardButton("BUY 1x"), KeyboardButton("SELL 1x")],
            [KeyboardButton("BUY 3x"), KeyboardButton("SELL 3x")],
            [KeyboardButton("BUY 5x"), KeyboardButton("SELL 5x")],
            [KeyboardButton("BUY 10x"), KeyboardButton("SELL 10x")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        update.message.reply_text(
            f"Symbol set to {symbol}.\n\n"
            f"Please select the side and leverage (e.g., 'BUY 5x' or 'SELL 10x'):",
            reply_markup=reply_markup
        )
        return SIDE
    
    def perp_side(self, update: Update, context: CallbackContext):
        """Handle side and leverage input for perp order"""
        user_id = update.effective_user.id
        text = update.message.text.strip().lower()
        
        # Parse side and leverage
        import re
        match = re.match(r"(buy|sell)(?:\s+(\d+)x?)?", text)
        if not match:
            update.message.reply_text(
                "Invalid format. Please enter 'buy [leverage]x' or 'sell [leverage]x':"
            )
            return SIDE
        
        side = match.group(1)
        leverage = int(match.group(2)) if match.group(2) else 1
        
        self.trading_context[user_id]["side"] = side
        self.trading_context[user_id]["leverage"] = leverage
        
        update.message.reply_text(
            f"Side set to {side} with {leverage}x leverage.\n\n"
            f"Please enter the contract size:"
        )
        return AMOUNT
    
    def perp_amount(self, update: Update, context: CallbackContext):
        """Handle amount input for perp order"""
        user_id = update.effective_user.id
        amount_text = update.message.text.strip()
        
        try:
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as e:
            update.message.reply_text(
                f"Invalid amount: {str(e)}. Please enter a valid positive number:"
            )
            return AMOUNT
        
        self.trading_context[user_id]["amount"] = amount
        
        keyboard = [
            [KeyboardButton("MARKET")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        update.message.reply_text(
            f"Contract size set to {amount}.\n\n"
            f"Please enter the price (or type 'MARKET' for a market order):",
            reply_markup=reply_markup
        )
        return PRICE
    
    def perp_price(self, update: Update, context: CallbackContext):
        """Handle price input for perp order"""
        user_id = update.effective_user.id
        price_text = update.message.text.strip().upper()
        
        if price_text == "MARKET":
            self.trading_context[user_id]["is_market"] = True
            self.trading_context[user_id]["price"] = None
        else:
            try:
                price = float(price_text)
                if price <= 0:
                    raise ValueError("Price must be positive")
                self.trading_context[user_id]["price"] = price
                self.trading_context[user_id]["is_market"] = False
            except ValueError as e:
                update.message.reply_text(
                    f"Invalid price: {str(e)}. Please enter a valid positive number or 'MARKET':"
                )
                return PRICE
        
        # Create confirmation message
        trade_details = self.trading_context[user_id]
        symbol = trade_details["symbol"]
        side = trade_details["side"].upper()
        amount = trade_details["amount"]
        leverage = trade_details["leverage"]
        
        if trade_details["is_market"]:
            order_type = "MARKET"
            price_text = "Market Price"
        else:
            order_type = "LIMIT"
            price_text = str(trade_details["price"])
        
        message = (
            f"*Order Confirmation:*\n\n"
            f"Type: Perpetual {order_type}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Size: {amount}\n"
            f"Leverage: {leverage}x\n"
            f"Price: {price_text}\n\n"
            f"Please confirm your order:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("Confirm", callback_data="confirm"),
                InlineKeyboardButton("Cancel", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return CONFIRMATION
    
    def perp_confirm(self, update: Update, context: CallbackContext):
        """Handle order confirmation for perp order"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        trade_details = self.trading_context[user_id]
        symbol = trade_details["symbol"]
        side = trade_details["side"]
        amount = trade_details["amount"]
        price = trade_details["price"]
        leverage = trade_details["leverage"]
        is_market = trade_details["is_market"]
        
        try:
            result = None
            if is_market:
                if side == "buy":
                    result = self.order_handler.perp_market_buy(symbol, amount, leverage)
                else:
                    result = self.order_handler.perp_market_sell(symbol, amount, leverage)
            else:
                if side == "buy":
                    result = self.order_handler.perp_limit_buy(symbol, amount, price, leverage)
                else:
                    result = self.order_handler.perp_limit_sell(symbol, amount, price, leverage)
            
            if result and result["status"] == "ok":
                order_type = "market" if is_market else "limit"
                query.edit_message_text(
                    f"✅ Perpetual {order_type} {side} order for {amount} {symbol} with {leverage}x leverage executed successfully!"
                )
            else:
                error_msg = result.get("message", "Unknown error") if result else "Unknown error"
                query.edit_message_text(
                    f"❌ Order failed: {error_msg}"
                )
        except Exception as e:
            self.logger.error(f"Error executing perpetual order: {str(e)}")
            query.edit_message_text(
                f"❌ Error executing order: {str(e)}"
            )
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        return ConversationHandler.END
    
    def perp_cancel(self, update: Update, context: CallbackContext):
        """Handle order cancellation for perp order"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        query.edit_message_text("Order cancelled")
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        return ConversationHandler.END
    
    def cancel_conversation(self, update: Update, context: CallbackContext):
        """Generic handler to cancel any conversation"""
        user_id = update.effective_user.id
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        update.message.reply_text("Operation cancelled")
        return ConversationHandler.END
    
    def error_handler(self, update: Update, context: CallbackContext):
        """Log errors and send a message to the user"""
        self.logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if update.effective_message:
                update.effective_message.reply_text(
                    "❌ Sorry, an error occurred while processing your request."
                )
        except Exception as e:
            self.logger.error(f"Error in error handler: {str(e)}")


def notify_telegram_bot(telegram_bot, message):
    """Send notification to all admin users via Telegram bot"""
    if telegram_bot is None:
        return
    
    try:
        for user_id in telegram_bot.admin_user_ids:
            telegram_bot.updater.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        telegram_bot.logger.error(f"Error sending Telegram notification: {str(e)}")