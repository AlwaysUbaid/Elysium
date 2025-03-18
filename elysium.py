#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import json
import telegram
import threading
import importlib.util
from pathlib import Path

# Import other modules
from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager
from terminal_ui import ElysiumTerminalUI
from grid_trading import GridTrading

# Try to import the Telegram bot module
try:
    from elysium_telegram_bot import ElysiumTelegramBot, notify_telegram_bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

def setup_logging(log_level=logging.INFO, log_file=None):
    """Configure logging"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger("elysium")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Elysium Trading Platform')
    parser.add_argument('-c', '--config', type=str, default='elysium_config.json',
                        help='Path to configuration file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-t', '--testnet', action='store_true',
                        help='Use testnet instead of mainnet')
    parser.add_argument('--log-file', type=str, 
                        help='Path to log file')
    parser.add_argument('--no-telegram', action='store_true',
                        help='Disable Telegram bot')
    parser.add_argument('--telegram-only', action='store_true',
                        help='Run only the Telegram bot (no terminal UI)')
    
    return parser.parse_args()


def is_telegram_dependencies_installed():
    """Check if the required Telegram dependencies are installed"""
    try:
        import telegram
        import telegram.ext
        return True
    except ImportError:
        return False


def create_telegram_bot_module(logger):
    """Create the Telegram bot module if not exist"""
    # First, check if the file already exists
    if os.path.exists("elysium_telegram_bot.py"):
        logger.info("Telegram bot module already exists")
        return
    
    # If file doesn't exist, check if we can import it
    if not is_telegram_dependencies_installed():
        logger.warning("python-telegram-bot is not installed. Run 'pip install python-telegram-bot==13.7 urllib3==1.26.15 httpx==0.23.0'")
        return
    
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find the path to the updated-telegram-bot file
    bot_file_path = os.path.join(current_dir, "updated-telegram-bot.py")
    
    if os.path.exists(bot_file_path):
        # If the file exists, copy it
        with open(bot_file_path, 'r') as source_file:
            content = source_file.read()
        
        with open("elysium_telegram_bot.py", 'w') as target_file:
            target_file.write(content)
        
        logger.info("Created elysium_telegram_bot.py from updated-telegram-bot.py")
    else:
        logger.warning("Could not find updated-telegram-bot.py to create elysium_telegram_bot.py")


def main():
    """Main entry point for the application"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(log_level, args.log_file)
    
    logger.info("Starting Elysium Trading Platform")
    
    # Create Telegram bot module if needed
    if not args.no_telegram:
        create_telegram_bot_module(logger)
    
    # Initialize components
    config_manager = ConfigManager(args.config)
    api_connector = ApiConnector()
    order_handler = OrderHandler(None, None)  # Will be initialized when connected
    telegram_bot = None
    
    try:
        # Set up cross-references between components
        order_handler.api_connector = api_connector  # This is critical for grid trading to work
        
        # Initialize Telegram bot if not disabled
        if not args.no_telegram and TELEGRAM_AVAILABLE:
            try:
                # Try importing the module directly
                from elysium_telegram_bot import ElysiumTelegramBot, notify_telegram_bot
                
                telegram_bot = ElysiumTelegramBot(api_connector, order_handler, config_manager, logger)
                # Start the Telegram bot in a separate thread
                telegram_thread = threading.Thread(target=telegram_bot.start)
                telegram_thread.daemon = True
                telegram_thread.start()
                logger.info("Telegram bot started in background")
            except Exception as e:
                logger.error(f"Failed to start Telegram bot: {str(e)}")
                logger.info("You may need to install dependencies: pip install python-telegram-bot==13.7 urllib3==1.26.15 httpx==0.23.0")
                telegram_bot = None
        else:
            logger.info("Telegram bot disabled or not available")
        
        if args.telegram_only:
            logger.info("Running in Telegram-only mode (no terminal UI)")
            # Just keep the main thread alive
            import time
            try:
                while True:
                    time.sleep(10)
            except KeyboardInterrupt:
                logger.info("Shutting down due to keyboard interrupt")
                if telegram_bot:
                    telegram_bot.stop()
                return
        
        # Create and start the CLI
        terminal = ElysiumTerminalUI(api_connector, order_handler, config_manager)
        
        # Auto-connect if credentials are available
        if args.testnet:
            logger.info("Auto-connecting to testnet")
            terminal.do_connect("testnet")
            if telegram_bot:
                telegram_bot.update_connection_status(True, True)
                notify_telegram_bot(telegram_bot, "🔄 *Elysium Platform Started*\nAutomatically connected to testnet")
        elif config_manager.get("auto_connect", False):
            logger.info("Auto-connecting to mainnet")
            terminal.do_connect("")
            if telegram_bot:
                telegram_bot.update_connection_status(True, False)
                notify_telegram_bot(telegram_bot, "🔄 *Elysium Platform Started*\nAutomatically connected to mainnet")
        else:
            # Just notify that the platform has started
            if telegram_bot:
                notify_telegram_bot(telegram_bot, "🔄 *Elysium Platform Started*\nUse /connect to connect to an exchange")
        
        # Start the CLI (this will block until exit)
        terminal.cmdloop()
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    finally:
        # Stop the Telegram bot if it was started
        if telegram_bot:
            try:
                telegram_bot.stop()
                logger.info("Telegram bot stopped")
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {str(e)}")
    
    logger.info("Elysium Trading Platform shutdown complete")


if __name__ == "__main__":
    main()