"""
Logging functionality for the Elysium trading framework.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional


class Logger:
    """
    Provides logging functionality with configuration options.
    """

    def __init__(self,
                 name: str,
                 log_level: int = logging.INFO,
                 log_to_console: bool = True,
                 log_to_file: bool = True,
                 log_dir: str = "logs",
                 log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"):
        """
        Initialize logger with configuration options.

        Args:
            name: Logger name
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_console: Whether to log to console
            log_to_file: Whether to log to file
            log_dir: Directory for log files
            log_format: Format string for log messages
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.log_format = log_format
        
        # Clear any existing handlers
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(log_format)

        # Set up console logging if enabled
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # Set up file logging if enabled
        if log_to_file:
            # Create log directory if it doesn't exist
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Create log file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_file = os.path.join(log_dir, f"{name}-{timestamp}.log")

            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        return self.logger


def create_logger(name: str,
                  module: Optional[str] = None,
                  log_level: int = logging.INFO,
                  log_to_console: bool = True,
                  log_to_file: bool = True) -> logging.Logger:
    """
    Create and configure a logger instance.

    Args:
        name: Base name for the logger
        module: Optional module name to append
        log_level: Logging level
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file

    Returns:
        Configured logger instance
    """
    logger_name = f"{name}.{module}" if module else name
    logger = Logger(
        name=logger_name,
        log_level=log_level,
        log_to_console=log_to_console,
        log_to_file=log_to_file
    )
    return logger.get_logger()