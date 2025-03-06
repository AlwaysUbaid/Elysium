"""
Configuration handling for the Elysium trading framework.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from elysium.utils.validators import validate_config


class Config:
    """
    Handles loading, validating, and accessing configuration.
    """

    def __init__(self,
                 config_path: str = "config.json",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize configuration handler.

        Args:
            config_path: Path to config file
            logger: Optional logger instance
        """
        self.config_path = config_path
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.config = {}

        # Load config if file exists
        if os.path.exists(config_path):
            self.load()

    def load(self) -> bool:
        """
        Load configuration from file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            # Validate config
            is_valid, errors = validate_config(self.config)
            if not is_valid:
                self.logger.error(f"Configuration validation failed: {errors}")
                return False

            self.logger.info(f"Loaded configuration from {self.config_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading configuration from {self.config_path}: {str(e)}")
            return False

    def save(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            self.logger.info(f"Saved configuration to {self.config_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving configuration to {self.config_path}: {str(e)}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (can use dot notation for nested fields)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Support dot notation for nested keys
        if '.' in key:
            parts = key.split('.')
            current = self.config

            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default

            return current

        # Simple key lookup
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key (can use dot notation for nested fields)
            value: Value to set
        """
        # Support dot notation for nested keys
        if '.' in key:
            parts = key.split('.')
            current = self.config

            # Navigate to the parent object
            for i, part in enumerate(parts[:-1]):
                # Create nested objects if they don't exist
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

            # Set the value
            current[parts[-1]] = value
        else:
            # Simple key assignment
            self.config[key] = value

    def get_exchange_config(self) -> Dict[str, Any]:
        """
        Get exchange configuration.

        Returns:
            Exchange configuration dictionary
        """
        return self.get('exchange', {})

    def get_strategy_config(self) -> Dict[str, Any]:
        """
        Get strategy configuration.

        Returns:
            Strategy configuration dictionary
        """
        return self.get('strategy', {})

    def get_strategy_name(self) -> str:
        """
        Get the configured strategy name.

        Returns:
            Strategy name or empty string if not configured
        """
        return self.get('strategy.name', '')

    def get_strategy_params(self) -> Dict[str, Any]:
        """
        Get strategy parameters.

        Returns:
            Strategy parameters dictionary
        """
        return self.get('strategy.params', {})

    def get_rebate_config(self) -> Dict[str, Any]:
        """
        Get rebate configuration.

        Returns:
            Rebate configuration dictionary
        """
        return self.get('rebates', {})

    def get_api_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get API credentials.

        Returns:
            Tuple of (account_address, private_key)
        """
        exchange_config = self.get_exchange_config()
        account_address = exchange_config.get('account_address')
        private_key = exchange_config.get('private_key')

        return account_address, private_key

    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration.

        Returns:
            Logging configuration dictionary
        """
        return self.get('logging', {
            'level': 'INFO',
            'log_to_console': True,
            'log_to_file': True,
            'log_dir': 'logs'
        })

    def generate_default_config(self) -> Dict[str, Any]:
        """
        Generate default configuration.

        Returns:
            Default configuration dictionary
        """
        default_config = {
            'exchange': {
                'base_url': 'https://api.hyperliquid.xyz',
                'account_address': '',
                'private_key': ''
            },
            'strategy': {
                'name': 'basic_market_making',
                'params': {
                    'symbol': 'ETH',
                    'order_size': 0.1,
                    'min_spread': 0.002,
                    'max_spread': 0.005,
                    'inventory_target': 0.0,
                    'inventory_range': 0.5,
                    'order_refresh_time': 30,
                    'max_orders_per_side': 1
                }
            },
            'rebates': {
                'enabled': True,
                'default_builder': '',
                'default_fee_rate': 1,
                'strategy': 'default'
            },
            'risk': {
                'max_position_size': {
                    'ETH': 1.0,
                    'BTC': 0.1
                },
                'max_drawdown_pct': 0.1
            },
            'logging': {
                'level': 'INFO',
                'log_to_console': True,
                'log_to_file': True,
                'log_dir': 'logs'
            }
        }

        return default_config

    def create_default_config(self) -> bool:
        """
        Create a default configuration file if none exists.

        Returns:
            True if successful, False otherwise
        """
        if os.path.exists(self.config_path):
            self.logger.info(f"Config file already exists: {self.config_path}")
            return False

        self.config = self.generate_default_config()
        return self.save()