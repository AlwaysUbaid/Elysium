# elysium/config.py
import os
import json
import logging
from typing import Dict, Any, Tuple, Optional

# Default configuration
DEFAULT_CONFIG = {
    "exchange": {
        "base_url": "https://api.hyperliquid-testnet.xyz",
        "use_testnet": True
    },
    "api": {
        "wallet_address": "0xb92e5A1363Da1030B10f02378ea9FBcA7bEC1973",
         "private_key": "0xf5e6970eedc56f66975beaf3c81d1fa97d01c747550137ddeeb096dce8d810ac"
    },
    "strategy": {
        "default": "basic_market_making"
    }
}

class Config:
    """Configuration manager for Elysium trading bot."""
    
    def __init__(self, config_file="elysium_config.json", logger=None):
        """Initialize config with file path."""
        self.config_file = config_file
        self.config = {}
        self.logger = logger or logging.getLogger(__name__)
    
    def create_default_config(self):
        """Create a default configuration file if one doesn't exist."""
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            self.logger.info(f"Saved configuration to {self.config_file}")
            return True
        return False
    
    def load(self):
        """Load configuration from file."""
        try:
            # Create default config if it doesn't exist
            self.create_default_config()
            
            # Load the configuration
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            self.logger.info(f"Loaded configuration from {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            return False
    
    def save(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            self.logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def get(self, key_path, default=None):
        """Get a configuration value using dot notation."""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path, value):
        """Set a configuration value using dot notation."""
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to the innermost dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        return True
    
    def get_api_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get API credentials from config."""
        wallet_address = self.get('api.wallet_address')
        private_key = self.get('api.private_key')
        
        return wallet_address, private_key
    
    def set_api_credentials(self, wallet_address: str, private_key: str) -> bool:
        """Set API credentials in config."""
        self.set('api.wallet_address', wallet_address)
        self.set('api.private_key', private_key)
        return self.save()

# Helper function to get config instance
def get_config(config_file="elysium_config.json"):
    """Get a config instance."""
    return Config(config_file)
# =============================Old Config.py==================================
# """
# Configuration handling for Elysium Trading Bot.
# """
# import os
# import json
# import logging
# from typing import Dict, Any, Optional, List, Tuple

# # Default configuration
# DEFAULT_CONFIG = {
#     "exchange": {
#         "use_testnet": True,
#         "base_url": None,  # Will be set based on use_testnet
#         "wallet_address": "0xb92e5A1363Da1030B10f02378ea9FBcA7bEC1973",
#         "private_key": "0xf5e6970eedc56f66975beaf3c81d1fa97d01c747550137ddeeb096dce8d810ac",
#     },
#     "logging": {
#         "level": "INFO",
#         "log_to_console": True,
#         "log_to_file": True,
#         "log_dir": "logs"
#     },
#     "risk": {
#         "max_drawdown_pct": 0.1,  # 10% max drawdown
#         "max_position_sizes": {
#             "ETH": 1.0,
#             "BTC": 0.05,
#             "HWTR/USDC": 10000.0
#         },
#         "risk_per_trade": 0.01  # 1% account risk per trade
#     },
#     "strategy": {
#         "name": "basic_market_making",
#         "params": {
#             "symbol": "@140",  # HWTR/USDC pair
#             "display_name": "HWTR/USDC",
#             "max_order_size": 6000.0,
#             "min_order_size": 1000.0,
#             "position_use_pct": 0.90,
#             "initial_offset": 0.0001,  # 0.01%
#             "min_offset": 0.00009,     # 0.009%
#             "offset_reduction": 0.00001,
#             "order_refresh_time": 10,  # seconds
#             "max_active_orders": 4
#         }
#     },
#     "rebates": {
#         "enabled": True,
#         "default_builder": "",
#         "default_fee_rate": 1,
#         "strategy": "default"
#     }
# }

# CONFIG_FILE = "elysium_config.json"


# class Config:
#     """
#     Handles loading, validating, and accessing configuration.
#     """

#     def __init__(self,
#                  config_path: str = CONFIG_FILE,
#                  logger: Optional[logging.Logger] = None):
#         """
#         Initialize configuration handler.

#         Args:
#             config_path: Path to config file
#             logger: Optional logger instance
#         """
#         self.config_path = config_path
#         self.logger = logger or logging.getLogger(self.__class__.__name__)
#         self.config = DEFAULT_CONFIG.copy()

#         # Load config if file exists
#         if os.path.exists(config_path):
#             self.load()
#         else:
#             # Save default config
#             self.save()

#     def load(self) -> bool:
#         """
#         Load configuration from file.

#         Returns:
#             True if successful, False otherwise
#         """
#         try:
#             with open(self.config_path, 'r') as f:
#                 loaded_config = json.load(f)
                
#             # Merge with default config to ensure all required fields exist
#             self._merge_configs(self.config, loaded_config)

#             self.logger.info(f"Loaded configuration from {self.config_path}")
#             return True

#         except Exception as e:
#             self.logger.error(f"Error loading configuration from {self.config_path}: {str(e)}")
#             return False

#     def save(self) -> bool:
#         """
#         Save configuration to file.

#         Returns:
#             True if successful, False otherwise
#         """
#         try:
#             with open(self.config_path, 'w') as f:
#                 json.dump(self.config, f, indent=2)

#             self.logger.info(f"Saved configuration to {self.config_path}")
#             return True

#         except Exception as e:
#             self.logger.error(f"Error saving configuration to {self.config_path}: {str(e)}")
#             return False

#     def _merge_configs(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
#         """
#         Recursively merge source config into target config.
        
#         Args:
#             target: Target configuration dictionary
#             source: Source configuration dictionary
#         """
#         for key, value in source.items():
#             if key in target and isinstance(target[key], dict) and isinstance(value, dict):
#                 self._merge_configs(target[key], value)
#             else:
#                 target[key] = value

#     def get(self, key: str, default: Any = None) -> Any:
#         """
#         Get a configuration value using a dot-separated path.

#         Args:
#             key: Dot-separated path to the config value (e.g. "exchange.use_testnet")
#             default: Default value if key not found

#         Returns:
#             Configuration value or default
#         """
#         # Support dot notation for nested keys
#         if '.' in key:
#             parts = key.split('.')
#             current = self.config

#             for part in parts:
#                 if isinstance(current, dict) and part in current:
#                     current = current[part]
#                 else:
#                     return default

#             return current

#         # Simple key lookup
#         return self.config.get(key, default)

#     def set(self, key: str, value: Any) -> None:
#         """
#         Set a configuration value using a dot-separated path.

#         Args:
#             key: Dot-separated path to the config value (e.g. "exchange.use_testnet")
#             value: New value
#         """
#         # Support dot notation for nested keys
#         if '.' in key:
#             parts = key.split('.')
#             current = self.config

#             # Navigate to the parent object
#             for i, part in enumerate(parts[:-1]):
#                 # Create nested objects if they don't exist
#                 if part not in current or not isinstance(current[part], dict):
#                     current[part] = {}
#                 current = current[part]

#             # Set the value
#             current[parts[-1]] = value
#         else:
#             # Simple key assignment
#             self.config[key] = value

#     def get_exchange_config(self) -> Dict[str, Any]:
#         """
#         Get exchange configuration.

#         Returns:
#             Exchange configuration dictionary
#         """
#         return self.get('exchange', {})

#     def get_strategy_config(self) -> Dict[str, Any]:
#         """
#         Get strategy configuration.

#         Returns:
#             Strategy configuration dictionary
#         """
#         return self.get('strategy', {})

#     def get_strategy_name(self) -> str:
#         """
#         Get the configured strategy name.

#         Returns:
#             Strategy name or empty string if not configured
#         """
#         return self.get('strategy.name', '')

#     def get_strategy_params(self) -> Dict[str, Any]:
#         """
#         Get strategy parameters.

#         Returns:
#             Strategy parameters dictionary
#         """
#         return self.get('strategy.params', {})

#     def get_rebate_config(self) -> Dict[str, Any]:
#         """
#         Get rebate configuration.

#         Returns:
#             Rebate configuration dictionary
#         """
#         return self.get('rebates', {})

#     def get_api_credentials(self) -> Tuple[Optional[str], Optional[str]]:
#         """
#         Get API credentials.

#         Returns:
#             Tuple of (account_address, private_key)
#         """
#         exchange_config = self.get_exchange_config()
#         account_address = exchange_config.get('account_address')
#         private_key = exchange_config.get('private_key')

#         return account_address, private_key

#     def get_logging_config(self) -> Dict[str, Any]:
#         """
#         Get logging configuration.

#         Returns:
#             Logging configuration dictionary
#         """
#         return self.get('logging', {
#             'level': 'INFO',
#             'log_to_console': True,
#             'log_to_file': True,
#             'log_dir': 'logs'
#         })


# # Global config instance for convenience
# _config = None

# def get_config() -> Config:
#     """
#     Get the global config instance.
    
#     Returns:
#         Config instance
#     """
#     global _config
#     if _config is None:
#         _config = Config()
#     return _config

# def load_config() -> Dict[str, Any]:
#     """
#     Load configuration from file, or create default if not exists.
#     For compatibility with function-based access.
    
#     Returns:
#         Configuration dictionary
#     """
#     return get_config().config

# def save_config(config: Dict[str, Any]) -> bool:
#     """
#     Save configuration to file.
#     For compatibility with function-based access.
    
#     Args:
#         config: Configuration to save
    
#     Returns:
#         Success status
#     """
#     global _config
#     if _config is None:
#         _config = Config()
#     _config.config = config
#     return _config.save()

# def get_config_value(key_path: str, default: Any = None) -> Any:
#     """
#     Get a configuration value using a dot-separated path.
#     For compatibility with function-based access.
    
#     Args:
#         key_path: Dot-separated path to the config value (e.g. "exchange.use_testnet")
#         default: Default value if key not found
    
#     Returns:
#         Configuration value or default
#     """
#     return get_config().get(key_path, default)

# def update_config_value(key_path: str, value: Any) -> bool:
#     """
#     Update a configuration value using a dot-separated path.
#     For compatibility with function-based access.
    
#     Args:
#         key_path: Dot-separated path to the config value (e.g. "exchange.use_testnet")
#         value: New value
    
#     Returns:
#         Success status
#     """
#     config = get_config()
#     config.set(key_path, value)
#     return config.save()