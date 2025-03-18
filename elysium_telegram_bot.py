import os
import sys
import logging
import json
import time
import re
import threading
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Telegram imports
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
SELECTING_NETWORK, PASSWORD_AUTH, PASSWORD_SETUP, CONFIRM_PASSWORD = range(4)
SYMBOL, SIDE, AMOUNT, PRICE, CONFIRMATION = range(4, 9)
GRID_SYMBOL, GRID_UPPER, GRID_LOWER, GRID_NUM, GRID_INVEST, GRID_TYPE, GRID_LEVERAGE, GRID_TP, GRID_SL = range(9, 18)
TWAP_SYMBOL, TWAP_SIDE, TWAP_QUANTITY, TWAP_DURATION, TWAP_SLICES, TWAP_PRICE, TWAP_TYPE, TWAP_LEVERAGE = range(18, 26)

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
        
        # For thread safety and synchronization
        self.state_lock = threading.Lock()
        self.command_queue = queue.Queue()  # Queue for commands between CLI and Telegram
        
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
            entry_points=[CommandHandler("connect", self.select_network)],
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
        
        # Market data commands
        self.dispatcher.add_handler(CommandHandler("price", self.cmd_price))
        
        # Trading menus
        self.dispatcher.add_handler(CommandHandler("trade_menu", self.show_trade_menu))
        self.dispatcher.add_handler(CommandHandler("advanced_menu", self.show_advanced_menu))
        self.dispatcher.add_handler(CommandHandler("grid_menu", self.show_grid_menu))
        self.dispatcher.add_handler(CommandHandler("twap_menu", self.show_twap_menu))
        
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
        
        # Grid trading conversation
        grid_conv = ConversationHandler(
            entry_points=[CommandHandler("create_grid", self.grid_start)],
            states={
                GRID_SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.grid_symbol)],
                GRID_UPPER: [MessageHandler(Filters.text & ~Filters.command, self.grid_upper)],
                GRID_LOWER: [MessageHandler(Filters.text & ~Filters.command, self.grid_lower)],
                GRID_NUM: [MessageHandler(Filters.text & ~Filters.command, self.grid_num)],
                GRID_INVEST: [MessageHandler(Filters.text & ~Filters.command, self.grid_invest)],
                GRID_TYPE: [
                    CallbackQueryHandler(self.grid_type, pattern='^(spot|perp)$')
                ],
                GRID_LEVERAGE: [MessageHandler(Filters.text & ~Filters.command, self.grid_leverage)],
                GRID_TP: [MessageHandler(Filters.text & ~Filters.command, self.grid_tp)],
                GRID_SL: [MessageHandler(Filters.text & ~Filters.command, self.grid_sl)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.grid_confirm, pattern='^confirm$'),
                    CallbackQueryHandler(self.grid_cancel, pattern='^cancel$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(grid_conv)
        
        # TWAP trading conversation
        twap_conv = ConversationHandler(
            entry_points=[CommandHandler("create_twap", self.twap_start)],
            states={
                TWAP_SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.twap_symbol)],
                TWAP_SIDE: [
                    CallbackQueryHandler(self.twap_side, pattern='^(buy|sell)$')
                ],
                TWAP_QUANTITY: [MessageHandler(Filters.text & ~Filters.command, self.twap_quantity)],
                TWAP_DURATION: [MessageHandler(Filters.text & ~Filters.command, self.twap_duration)],
                TWAP_SLICES: [MessageHandler(Filters.text & ~Filters.command, self.twap_slices)],
                TWAP_PRICE: [MessageHandler(Filters.text & ~Filters.command, self.twap_price)],
                TWAP_TYPE: [
                    CallbackQueryHandler(self.twap_type, pattern='^(spot|perp)$')
                ],
                TWAP_LEVERAGE: [MessageHandler(Filters.text & ~Filters.command, self.twap_leverage)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.twap_confirm, pattern='^confirm$'),
                    CallbackQueryHandler(self.twap_cancel, pattern='^cancel$')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(twap_conv)
        
        # Grid management commands
        self.dispatcher.add_handler(CommandHandler("grid_list", self.cmd_grid_list))
        self.dispatcher.add_handler(CommandHandler("grid_status", self.cmd_grid_status))
        self.dispatcher.add_handler(CommandHandler("grid_start", self.cmd_grid_start))
        self.dispatcher.add_handler(CommandHandler("grid_stop", self.cmd_grid_stop))
        
        # TWAP management commands
        self.dispatcher.add_handler(CommandHandler("twap_list", self.cmd_twap_list))
        self.dispatcher.add_handler(CommandHandler("twap_status", self.cmd_twap_status))
        self.dispatcher.add_handler(CommandHandler("twap_start", self.cmd_twap_start))
        self.dispatcher.add_handler(CommandHandler("twap_stop", self.cmd_twap_stop))
        
        # Close position handler
        self.dispatcher.add_handler(CommandHandler("close", self.cmd_close_position))
        
        # Menu callbacks
        self.dispatcher.add_handler(CallbackQueryHandler(self.menu_callback))
        
        # Text message handler for keyboard buttons
        self.dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command, 
            self.handle_text_message
        ))
        
        # Error handler
        self.dispatcher.add_error_handler(self.error_handler)
    
    def start(self):
        """Start the bot in a separate thread"""
        if not hasattr(self, 'updater'):
            self.logger.error("Telegram bot not properly initialized")
            return
        
        self.logger.info("Starting Elysium Telegram Bot")
        self.updater.start_polling()
        
        # Start the command processing thread
        self.command_processor_thread = threading.Thread(target=self._process_commands)
        self.command_processor_thread.daemon = True
        self.command_processor_thread.start()
    
    def stop(self):
        """Stop the bot"""
        if hasattr(self, 'updater'):
            self.logger.info("Stopping Elysium Telegram Bot")
            self.updater.stop()
    
    def _process_commands(self):
        """Process commands between CLI and Telegram"""
        while True:
            try:
                # Get command from queue (with timeout to allow checking for shutdown)
                try:
                    cmd, args = self.command_queue.get(timeout=1)
                    
                    # Process the command
                    if cmd == "update_connection":
                        connected, is_testnet = args
                        self._update_connection_status(connected, is_testnet)
                        
                    # Add more commands as needed
                    
                    # Mark task as done
                    self.command_queue.task_done()
                except queue.Empty:
                    # Queue is empty, just continue the loop
                    pass
                    
                # Sleep a bit to prevent high CPU usage
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error in command processor: {str(e)}")
                time.sleep(1)  # Prevent tight loop in case of errors
    
    def update_connection_status(self, connected, is_testnet=False):
        """
        Update the connection status when the main app connects
        This is thread-safe and uses the command queue
        """
        self.command_queue.put(("update_connection", (connected, is_testnet)))
    
    def _update_connection_status(self, connected, is_testnet=False):
        """Internal method to update connection status with thread safety"""
        with self.state_lock:
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
        with self.state_lock:
            connected = self.connected
        
        if not connected:
            if hasattr(update, 'message') and update.message:
                update.message.reply_text("❌ Not connected to exchange. Use /connect first.")
                return False
            elif hasattr(update, 'callback_query') and update.callback_query:
                update.callback_query.answer("Not connected to exchange")
                update.callback_query.edit_message_text("❌ Not connected to exchange. Use /connect first.")
                return False
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
        """Connect to the exchange with proper synchronization"""
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
            
            # Connect using API connector
            success = self.api_connector.connect_hyperliquid(wallet_address, secret_key, use_testnet)
            
            if success:
                # Update local state with thread safety
                with self.state_lock:
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
    
    def handle_text_message(self, update: Update, context: CallbackContext):
        """Handle text messages, especially from custom keyboard buttons"""
        if not self._check_auth(update, context):
            return
        
        text = update.message.text.strip()
        
        # Handle keyboard button text 
        if text == "💰 Balance":
            self.cmd_balance(update, context)
        elif text == "📊 Positions":
            self.cmd_positions(update, context)
        elif text == "📝 Orders":
            self.cmd_orders(update, context)
        elif text == "📈 Price":
            update.message.reply_text("Please use /price <symbol> to check prices")
        elif text == "❌ Close Position":
            self.cmd_close_position(update, context)
        elif text == "🔄 Status":
            self.cmd_status(update, context)
        elif text == "⚙️ Advanced":
            self.show_advanced_menu(update, context)
        elif text == "📏 Grid Menu":
            self.show_grid_menu(update, context)
        elif text == "⏱ TWAP Menu":
            self.show_twap_menu(update, context)
        elif text == "🛒 Trade Menu":
            self.show_trade_menu(update, context)
        elif text == "❔ Help":
            self.cmd_help(update, context)
        else:
            # If no specific handler is found, provide help
            update.message.reply_text(
                "Not sure what you're asking for. Use /help to see available commands."
            )
    
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
            [KeyboardButton("📝 Orders"), KeyboardButton("📈 Price")],
            [KeyboardButton("🛒 Trade Menu"), KeyboardButton("⚙️ Advanced")],
            [KeyboardButton("📏 Grid Menu"), KeyboardButton("⏱ TWAP Menu")],
            [KeyboardButton("🔄 Status"), KeyboardButton("❔ Help")]
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=False
        )
        
        with self.state_lock:
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
    
    def show_trade_menu(self, update: Update, context: CallbackContext):
        """Show basic trading options"""
        if not self._check_auth(update, context):
            return
        
        keyboard = [
            [
                InlineKeyboardButton("Spot Market Buy", callback_data="action_spot_market_buy"),
                InlineKeyboardButton("Spot Market Sell", callback_data="action_spot_market_sell")
            ],
            [
                InlineKeyboardButton("Spot Limit Buy", callback_data="action_spot_limit_buy"),
                InlineKeyboardButton("Spot Limit Sell", callback_data="action_spot_limit_sell")
            ],
            [
                InlineKeyboardButton("Perp Market Buy", callback_data="action_perp_market_buy"),
                InlineKeyboardButton("Perp Market Sell", callback_data="action_perp_market_sell")
            ],
            [
                InlineKeyboardButton("Perp Limit Buy", callback_data="action_perp_limit_buy"),
                InlineKeyboardButton("Perp Limit Sell", callback_data="action_perp_limit_sell")
            ],
            [
                InlineKeyboardButton("Close Position", callback_data="action_close_position")
            ],
            [
                InlineKeyboardButton("« Back to Main Menu", callback_data="action_main_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "*Trading Menu*\n\n"
            "Select a trading action:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    def show_advanced_menu(self, update: Update, context: CallbackContext):
        """Show advanced trading options"""
        if not self._check_auth(update, context):
            return
        
        keyboard = [
            [
                InlineKeyboardButton("Scaled Spot Buy", callback_data="action_scaled_buy"),
                InlineKeyboardButton("Scaled Spot Sell", callback_data="action_scaled_sell")
            ],
            [
                InlineKeyboardButton("Scaled Perp Buy", callback_data="action_perp_scaled_buy"),
                InlineKeyboardButton("Scaled Perp Sell", callback_data="action_perp_scaled_sell")
            ],
            [
                InlineKeyboardButton("Market Aware Buy", callback_data="action_market_scaled_buy"),
                InlineKeyboardButton("Market Aware Sell", callback_data="action_market_scaled_sell")
            ],
            [
                InlineKeyboardButton("Cancel All Orders", callback_data="action_cancel_all")
            ],
            [
                InlineKeyboardButton("« Back to Main Menu", callback_data="action_main_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "*Advanced Trading Options*\n\n"
            "These options provide more control over your trading activities.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    def cmd_grid_start(self, update: Update, context: CallbackContext):
        """
        Handle /grid_start command
        Usage: /grid_start <grid_id>
        """
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        try:
            # Check if grid_id is provided
            if not hasattr(context, 'args') or not context.args or len(context.args) < 1:
                self.handle_start_grid_menu(update.message, context)
                return
                
            grid_id = context.args[0]
            
            # Start the grid
            result = self.order_handler.start_grid(grid_id)
            
            if result["status"] == "ok":
                message = (
                    f"✅ Successfully started grid strategy {grid_id}\n"
                    f"Placed {result['buy_orders']} buy orders and {result['sell_orders']} sell orders\n"
                    f"Current market price: {result['current_price']}\n"
                )
                
                if result.get("warning"):
                    message += f"\n⚠️ Warning: {result['warning']}\n"
                    
                message += "\nUse /grid_status to check the status"
                
                # Add keyboard for follow-up actions
                keyboard = [
                    [InlineKeyboardButton("Check Status", callback_data=f"gridstatus_{grid_id}")],
                    [InlineKeyboardButton("Stop Grid", callback_data=f"gridstop_{grid_id}")],
                    [InlineKeyboardButton("« Back", callback_data="action_grid_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                update.message.reply_text(message, reply_markup=reply_markup)
            else:
                update.message.reply_text(f"❌ Failed to start grid strategy: {result.get('message', 'Unknown error')}")
        except Exception as e:
            self.logger.error(f"Error starting grid: {str(e)}")
            update.message.reply_text(f"❌ Error starting grid: {str(e)}")

    def cmd_grid_stop(self, update: Update, context: CallbackContext):
        """
        Handle /grid_stop command
        Usage: /grid_stop <grid_id>
        """
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        try:
            # Check if grid_id is provided
            if not hasattr(context, 'args') or not context.args or len(context.args) < 1:
                self.handle_stop_grid_menu(update.message, context)
                return
                
            grid_id = context.args[0]
            
            # Stop the grid
            result = self.order_handler.stop_grid(grid_id)
            
            if result["status"] == "ok":
                message = (
                    f"✅ Successfully stopped grid strategy {grid_id}\n"
                    f"Cancelled {result['cancelled_orders']}/{result['total_orders']} open orders\n"
                    f"Total profit/loss: {result['profit_loss']}\n"
                )
                
                # Add keyboard for follow-up actions
                keyboard = [
                    [InlineKeyboardButton("List Grids", callback_data="action_list_grids")],
                    [InlineKeyboardButton("Create New Grid", callback_data="action_create_grid")],
                    [InlineKeyboardButton("« Back", callback_data="action_grid_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                update.message.reply_text(message, reply_markup=reply_markup)
            else:
                update.message.reply_text(f"❌ Failed to stop grid strategy: {result.get('message', 'Unknown error')}")
        except Exception as e:
            self.logger.error(f"Error stopping grid: {str(e)}")
            update.message.reply_text(f"❌ Error stopping grid: {str(e)}")

    def show_grid_list(self, query, context):
        """Show list of grid trading strategies"""
        try:
            grid_list = self.order_handler.list_grids()
            
            message = "*Grid Trading Strategies*\n\n"
            
            # Display active grids
            message += "📊 *Active Grids:*\n"
            if grid_list["active"]:
                for grid in grid_list["active"]:
                    message += f"• ID: `{grid['id']}`\n"
                    message += f"  Symbol: {grid['symbol']}\n"
                    message += f"  Range: {grid['lower_price']} - {grid['upper_price']}\n"
                    message += f"  PnL: {grid.get('profit_loss', 0)}\n\n"
            else:
                message += "No active grid strategies\n\n"
            
            # Display completed grids
            message += "✅ *Completed Grids:*\n"
            if grid_list["completed"]:
                for grid in grid_list["completed"]:
                    message += f"• ID: `{grid['id']}`\n"
                    message += f"  Symbol: {grid['symbol']}\n"
                    message += f"  Final PnL: {grid.get('profit_loss', 0)}\n\n"
            else:
                message += "No completed grid strategies\n"
            
            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Grid Menu", callback_data="action_grid_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            self.logger.error(f"Error listing grids: {str(e)}")
            query.edit_message_text(f"❌ Error listing grids: {str(e)}")

    def cmd_grid_list(self, update: Update, context: CallbackContext):
        """Handle /grid_list command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        try:
            grid_list = self.order_handler.list_grids()
            
            message = "*Grid Trading Strategies*\n\n"
            
            # Display active grids
            message += "📊 *Active Grids:*\n"
            if grid_list["active"]:
                for grid in grid_list["active"]:
                    message += f"• ID: `{grid['id']}`\n"
                    message += f"  Symbol: {grid['symbol']}\n"
                    message += f"  Range: {grid['lower_price']} - {grid['upper_price']}\n"
                    message += f"  Status: {grid.get('status', 'created')}\n"
                    message += f"  PnL: {grid.get('profit_loss', 0)}\n\n"
            else:
                message += "No active grid strategies\n\n"
            
            # Display completed grids
            message += "✅ *Completed Grids:*\n"
            if grid_list["completed"]:
                for grid in grid_list["completed"]:
                    message += f"• ID: `{grid['id']}`\n"
                    message += f"  Symbol: {grid['symbol']}\n"
                    message += f"  Final PnL: {grid.get('profit_loss', 0)}\n\n"
            else:
                message += "No completed grid strategies\n"
            
            # Add keyboard with action buttons
            keyboard = []
            
            # Add buttons for active grids
            if grid_list["active"]:
                keyboard.append([InlineKeyboardButton("Start a Grid", callback_data="action_start_grid")])
                keyboard.append([InlineKeyboardButton("Stop a Grid", callback_data="action_stop_grid")])
            
            # Add back button
            keyboard.append([InlineKeyboardButton("« Back to Grid Menu", callback_data="action_grid_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error listing grids: {str(e)}")
            update.message.reply_text(f"❌ Error listing grids: {str(e)}")

    def handle_grid_status_menu(self, message_or_query, context):
        """Show menu for checking grid status"""
        try:
            grid_list = self.order_handler.list_grids()
            
            if not grid_list["active"] and not grid_list["completed"]:
                if hasattr(message_or_query, 'reply_text'):
                    message_or_query.reply_text("No grid trading strategies found")
                else:
                    message_or_query.edit_message_text("No grid trading strategies found")
                return
            
            keyboard = []
            
            # Add active grids
            for grid in grid_list["active"]:
                grid_id = grid['id']
                symbol = grid['symbol']
                keyboard.append([
                    InlineKeyboardButton(
                        f"Status: {symbol} ({grid_id.split('_')[-1]})", 
                        callback_data=f"gridstatus_{grid_id}"
                    )
                ])
            
            # Add completed grids
            for grid in grid_list["completed"]:
                grid_id = grid['id']
                symbol = grid['symbol']
                keyboard.append([
                    InlineKeyboardButton(
                        f"Completed: {symbol} ({grid_id.split('_')[-1]})", 
                        callback_data=f"gridstatus_{grid_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="action_grid_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "Select a grid to check its status:"
            
            if hasattr(message_or_query, 'reply_text'):
                message_or_query.reply_text(message, reply_markup=reply_markup)
            else:
                message_or_query.edit_message_text(message, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error getting grid list: {str(e)}")
            error_message = f"❌ Error getting grid list: {str(e)}"
            
            if hasattr(message_or_query, 'reply_text'):
                message_or_query.reply_text(error_message)
            else:
                message_or_query.edit_message_text(error_message)

    def handle_start_grid_menu(self, message_or_query, context):
        """Show menu for starting grid strategies"""
        try:
            grid_list = self.order_handler.list_grids()
            
            if not grid_list["active"]:
                if hasattr(message_or_query, 'reply_text'):
                    message_or_query.reply_text("No inactive grid strategies to start. Create a new grid first.")
                else:
                    message_or_query.edit_message_text("No inactive grid strategies to start. Create a new grid first.")
                return
            
            # Filter for inactive grids only
            inactive_grids = [g for g in grid_list["active"] if g.get("status") != "active"]
            
            if not inactive_grids:
                if hasattr(message_or_query, 'reply_text'):
                    message_or_query.reply_text("All grid strategies are already active.")
                else:
                    message_or_query.edit_message_text("All grid strategies are already active.")
                return
            
            keyboard = []
            for grid in inactive_grids:
                grid_id = grid['id']
                symbol = grid['symbol']
                keyboard.append([
                    InlineKeyboardButton(
                        f"Start: {symbol} ({grid_id.split('_')[-1]})", 
                        callback_data=f"gridstart_{grid_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="action_grid_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "Select a grid strategy to start:"
            
            if hasattr(message_or_query, 'reply_text'):
                message_or_query.reply_text(message, reply_markup=reply_markup)
            else:
                message_or_query.edit_message_text(message, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error getting grid list: {str(e)}")
            error_message = f"❌ Error getting grid list: {str(e)}"
            
            if hasattr(message_or_query, 'reply_text'):
                message_or_query.reply_text(error_message)
            else:
                message_or_query.edit_message_text(error_message)

    def handle_stop_grid_menu(self, message_or_query, context):
        """Show menu for stopping grid strategies"""
        try:
            grid_list = self.order_handler.list_grids()
            
            if not grid_list["active"]:
                if hasattr(message_or_query, 'reply_text'):
                    message_or_query.reply_text("No active grid strategies to stop.")
                else:
                    message_or_query.edit_message_text("No active grid strategies to stop.")
                return
            
            # Filter for active grids only
            active_grids = [g for g in grid_list["active"] if g.get("status") == "active"]
            
            if not active_grids:
                if hasattr(message_or_query, 'reply_text'):
                    message_or_query.reply_text("No active grid strategies to stop.")
                else:
                    message_or_query.edit_message_text("No active grid strategies to stop.")
                return
            
            keyboard = []
            for grid in active_grids:
                grid_id = grid['id']
                symbol = grid['symbol']
                keyboard.append([
                    InlineKeyboardButton(
                        f"Stop: {symbol} ({grid_id.split('_')[-1]})", 
                        callback_data=f"gridstop_{grid_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="action_grid_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "Select a grid strategy to stop:"
            
            if hasattr(message_or_query, 'reply_text'):
                message_or_query.reply_text(message, reply_markup=reply_markup)
            else:
                message_or_query.edit_message_text(message, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error getting grid list: {str(e)}")
            error_message = f"❌ Error getting grid list: {str(e)}"
            
            if hasattr(message_or_query, 'reply_text'):
                message_or_query.reply_text(error_message)
            else:
                message_or_query.edit_message_text(error_message)

    def handle_stop_all_grids(self, query, context):
        """Handle stopping all grid strategies"""
        try:
            confirm_keyboard = [
                [
                    InlineKeyboardButton("Yes, stop all", callback_data="gridstopall_confirm"),
                    InlineKeyboardButton("No, cancel", callback_data="action_grid_menu")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(confirm_keyboard)
            
            query.edit_message_text(
                "⚠️ Are you sure you want to stop ALL active grid strategies?",
                reply_markup=reply_markup
            )
        except Exception as e:
            self.logger.error(f"Error preparing stop all grids: {str(e)}")
            query.edit_message_text(f"❌ Error: {str(e)}")

    def handle_clean_grids(self, query, context):
        """Handle cleaning completed grid strategies"""
        try:
            confirm_keyboard = [
                [
                    InlineKeyboardButton("Yes, clean up", callback_data="gridclean_confirm"),
                    InlineKeyboardButton("No, cancel", callback_data="action_grid_menu")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(confirm_keyboard)
            
            query.edit_message_text(
                "Are you sure you want to clean up all completed grid strategies?",
                reply_markup=reply_markup
            )
        except Exception as e:
            self.logger.error(f"Error preparing clean grids: {str(e)}")
            query.edit_message_text(f"❌ Error: {str(e)}")

    def handle_modify_grid_menu(self, query, context):
        """Show menu for modifying grid strategies"""
        try:
            grid_list = self.order_handler.list_grids()
            
            if not grid_list["active"]:
                query.edit_message_text("No active grid strategies to modify.")
                return
            
            keyboard = []
            for grid in grid_list["active"]:
                grid_id = grid['id']
                symbol = grid['symbol']
                keyboard.append([
                    InlineKeyboardButton(
                        f"Modify: {symbol} ({grid_id.split('_')[-1]})", 
                        callback_data=f"gridmodify_{grid_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="action_grid_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                "Select a grid strategy to modify:",
                reply_markup=reply_markup
            )
        except Exception as e:
            self.logger.error(f"Error getting grid list: {str(e)}")
            query.edit_message_text(f"❌ Error getting grid list: {str(e)}")

    def cmd_balance(self, update: Update, context: CallbackContext):
        """Handle /balance command"""
        if not self._check_auth(update, context):
            return
        
        if not self._check_connection(update, context):
            return
        
        try:
            update.message.reply_text("🔄 Fetching balance information...")
            
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
        if not self._check_auth(update, context):
            return
        
        if not self._check_connection(update, context):
            return
        
        try:
            update.message.reply_text("🔄 Fetching position information...")
            
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
            
            # Add close buttons for positions
            keyboard = []
            for pos in positions:
                symbol = pos.get("symbol", "")
                keyboard.append([
                    InlineKeyboardButton(f"Close {symbol} Position", callback_data=f"close_{symbol}")
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            update.message.reply_text(f"❌ Error fetching positions: {str(e)}")

    def cmd_orders(self, update: Update, context: CallbackContext):
        """Handle /orders command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        try:
            update.message.reply_text("🔄 Fetching open orders...")
            
            orders = self.order_handler.get_open_orders()
            
            if not orders:
                update.message.reply_text("No open orders")
                return
            
            message = "*Open Orders:*\n\n"
            keyboard = []
            
            for order in orders:
                symbol = order.get("coin", "")
                side = "Buy" if order.get("side", "") == "B" else "Sell"
                size = float(order.get("sz", 0))
                price = float(order.get("limitPx", 0))
                order_id = order.get("oid", 0)
                
                message += (
                    f"*{symbol}:*\n"
                    f"• Side: {side}\n"
                    f"• Size: {size}\n"
                    f"• Price: {price}\n"
                    f"• Order ID: {order_id}\n\n"
                )
                
                # Add a cancel button for this order
                keyboard.append([InlineKeyboardButton(f"Cancel Order #{order_id}", callback_data=f"cancel_{symbol}_{order_id}")])
            
            # Add a cancel all button
            keyboard.append([InlineKeyboardButton("Cancel All Orders", callback_data="action_cancel_all")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"Error fetching orders: {str(e)}")
            update.message.reply_text(f"❌ Error fetching orders: {str(e)}")

    def cmd_close_position(self, update: Update, context: CallbackContext):
        """Handle /close command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        # Get arguments
        args = context.args if hasattr(context, 'args') else []
        
        # Get the list of positions
        try:
            positions = self.api_connector.get_positions()
            
            if not positions:
                update.message.reply_text("No open positions to close")
                return
            
            if args and len(args) > 0:
                # Direct close using command argument
                symbol = args[0].upper()
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

    def handle_close_position_menu(self, query, context):
        """Show menu for closing positions"""
        try:
            positions = self.api_connector.get_positions()
            
            if not positions:
                query.edit_message_text("No open positions to close")
                return
            
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
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="action_trade_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                "Select a position to close:",
                reply_markup=reply_markup
            )
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            query.edit_message_text(f"❌ Error getting positions: {str(e)}")

    def cmd_price(self, update: Update, context: CallbackContext):
        """Handle /price command"""
        if not self._check_auth(update, context) or not self._check_connection(update, context):
            return
        
        try:
            args = update.message.text.split()[1:] if len(update.message.text.split()) > 1 else []
            
            if not args:
                update.message.reply_text("Please specify a symbol. Usage: /price BTC")
                return
            
            symbol = args[0].upper()
            
            update.message.reply_text(f"🔄 Fetching price for {symbol}...")
            
            market_data = self.api_connector.get_market_data(symbol)
            
            if "error" in market_data:
                update.message.reply_text(f"❌ Error: {market_data['error']}")
                return
            
            message = f"*{symbol} Market Data:*\n\n"
            
            if "mid_price" in market_data:
                message += f"Mid Price: ${self._format_number(market_data['mid_price'], 6)}\n"
            
            if "best_bid" in market_data:
                message += f"Best Bid: ${self._format_number(market_data['best_bid'], 6)}\n"
            
            if "best_ask" in market_data:
                message += f"Best Ask: ${self._format_number(market_data['best_ask'], 6)}\n"
            
            if "best_bid" in market_data and "best_ask" in market_data:
                spread = market_data["best_ask"] - market_data["best_bid"]
                spread_percent = (spread / market_data["best_bid"]) * 100
                message += f"Spread: ${self._format_number(spread, 6)} ({self._format_number(spread_percent, 4)}%)\n"
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger.error(f"Error fetching price: {str(e)}")
            update.message.reply_text(f"❌ Error fetching price: {str(e)}")

    def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        with self.state_lock:
            connection_status = "Connected" if self.connected else "Not connected"
            network = "testnet" if self.is_testnet else "mainnet"
            network_emoji = "🧪" if self.is_testnet else "🌐"
        
        message = f"*Elysium Bot Status:*\n\n"
        message += f"Status: {connection_status}\n"
        
        if self.connected:
            message += f"Network: {network_emoji} {network.upper()}\n"
            message += f"Address: `{self.api_connector.wallet_address[:6]}...{self.api_connector.wallet_address[-4:]}`\n"
            
            # Add position summary if available
            try:
                positions = self.api_connector.get_positions()
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
            "/orders - Show open orders\n"
            "/price <symbol> - Check current price\n\n"
            
            "*Trading:*\n"
            "/spot - Create spot market/limit order\n"
            "/perp - Create perpetual market/limit order\n"
            "/close <symbol> - Close a position\n\n"
            
            "*Grid Trading:*\n"
            "/grid_list - List grid strategies\n"
            "/grid_status <id> - Check grid status\n"
            "/grid_start <id> - Start grid strategy\n"
            "/grid_stop <id> - Stop grid strategy\n\n"
            
            "*TWAP Trading:*\n"
            "/twap_list - List TWAP executions\n"
            "/twap_status <id> - Check TWAP status\n"
            "/twap_start <id> - Start TWAP execution\n"
            "/twap_stop <id> - Stop TWAP execution\n\n"
            
            "*Advanced:*\n"
            "/trade_menu - Show trading menu\n"
            "/grid_menu - Show grid trading menu\n"
            "/twap_menu - Show TWAP trading menu\n"
            "/advanced_menu - Show advanced options\n",
            parse_mode=ParseMode.MARKDOWN
        )

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

    def cancel_conversation(self, update: Update, context: CallbackContext):
        """Generic handler to cancel any conversation"""
        user_id = update.effective_user.id
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        # Remove keyboard if present
        update.message.reply_text(
            "Operation cancelled",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END