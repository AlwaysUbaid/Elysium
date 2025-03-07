# Persistence module
"""
Data persistence utilities for saving and loading trading data.
"""

import os
import json
import logging
import pickle
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import pandas as pd


class DataPersistence:
    """
    Handles persistence of trading data for strategy state,
    filled orders, and other data that needs to be stored.
    """

    def __init__(self,
                 data_dir: str = "data",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize data persistence handler.

        Args:
            data_dir: Directory for data storage
            logger: Optional logger instance
        """
        self.data_dir = data_dir
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            self.logger.info(f"Created data directory: {data_dir}")

    def save_json(self, data: Dict[str, Any], filename: str) -> bool:
        """
        Save data as JSON.

        Args:
            data: Data to save
            filename: Output filename (without extension)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure filename has .json extension
            if not filename.endswith('.json'):
                filename += '.json'

            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            self.logger.debug(f"Saved data to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving JSON data to {filename}: {str(e)}")
            return False

    def load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Load JSON data.

        Args:
            filename: Input filename (without extension)

        Returns:
            Loaded data or None if file doesn't exist or error occurs
        """
        try:
            # Ensure filename has .json extension
            if not filename.endswith('.json'):
                filename += '.json'

            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            if not os.path.exists(filepath):
                self.logger.warning(f"File does not exist: {filepath}")
                return None

            with open(filepath, 'r') as f:
                data = json.load(f)

            self.logger.debug(f"Loaded data from {filepath}")
            return data

        except Exception as e:
            self.logger.error(f"Error loading JSON data from {filename}: {str(e)}")
            return None

    def save_pickle(self, data: Any, filename: str) -> bool:
        """
        Save data using pickle.

        Args:
            data: Data to save (can be any picklable object)
            filename: Output filename (without extension)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure filename has .pkl extension
            if not filename.endswith('.pkl'):
                filename += '.pkl'

            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            with open(filepath, 'wb') as f:
                pickle.dump(data, f)

            self.logger.debug(f"Saved data to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving pickle data to {filename}: {str(e)}")
            return False

    def load_pickle(self, filename: str) -> Optional[Any]:
        """
        Load pickle data.

        Args:
            filename: Input filename (without extension)

        Returns:
            Loaded data or None if file doesn't exist or error occurs
        """
        try:
            # Ensure filename has .pkl extension
            if not filename.endswith('.pkl'):
                filename += '.pkl'

            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            if not os.path.exists(filepath):
                self.logger.warning(f"File does not exist: {filepath}")
                return None

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            self.logger.debug(f"Loaded data from {filepath}")
            return data

        except Exception as e:
            self.logger.error(f"Error loading pickle data from {filename}: {str(e)}")
            return None

    def save_dataframe(self, df: pd.DataFrame, filename: str, format: str = 'csv') -> bool:
        """
        Save DataFrame to disk.

        Args:
            df: DataFrame to save
            filename: Output filename (without extension)
            format: Output format ('csv' or 'parquet')

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure filename has correct extension
            if format.lower() == 'csv' and not filename.endswith('.csv'):
                filename += '.csv'
            elif format.lower() == 'parquet' and not filename.endswith('.parquet'):
                filename += '.parquet'

            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            # Save based on format
            if format.lower() == 'csv':
                df.to_csv(filepath, index=False)
            elif format.lower() == 'parquet':
                df.to_parquet(filepath, index=False)
            else:
                self.logger.error(f"Unsupported format: {format}")
                return False

            self.logger.debug(f"Saved DataFrame to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving DataFrame to {filename}: {str(e)}")
            return False

    def load_dataframe(self, filename: str, format: str = None) -> Optional[pd.DataFrame]:
        """
        Load DataFrame from disk.

        Args:
            filename: Input filename
            format: Input format ('csv' or 'parquet'), if None will be determined from extension

        Returns:
            DataFrame or None if file doesn't exist or error occurs
        """
        try:
            # Determine format from extension if not specified
            if format is None:
                if filename.endswith('.csv'):
                    format = 'csv'
                elif filename.endswith('.parquet'):
                    format = 'parquet'
                else:
                    self.logger.error(f"Cannot determine format from filename: {filename}")
                    return None

            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            if not os.path.exists(filepath):
                self.logger.warning(f"File does not exist: {filepath}")
                return None

            # Load based on format
            if format.lower() == 'csv':
                df = pd.read_csv(filepath)
            elif format.lower() == 'parquet':
                df = pd.read_parquet(filepath)
            else:
                self.logger.error(f"Unsupported format: {format}")
                return None

            self.logger.debug(f"Loaded DataFrame from {filepath}")
            return df

        except Exception as e:
            self.logger.error(f"Error loading DataFrame from {filename}: {str(e)}")
            return None

    def append_to_file(self, data: str, filename: str) -> bool:
        """
        Append data to a text file.

        Args:
            data: String data to append
            filename: Output filename

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            # Append data to file
            with open(filepath, 'a') as f:
                f.write(data + '\n')

            return True

        except Exception as e:
            self.logger.error(f"Error appending to file {filename}: {str(e)}")
            return False

    def save_fills(self, fills: List[Dict[str, Any]], filename: str = "fills.json") -> bool:
        """
        Save trade fills to file, appending if file exists.

        Args:
            fills: List of fill data
            filename: Output filename

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create full path
            filepath = os.path.join(self.data_dir, filename)

            # Load existing fills if file exists
            existing_fills = []
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    try:
                        existing_fills = json.load(f)
                    except json.JSONDecodeError:
                        # If file is corrupted, start fresh
                        existing_fills = []

            # Append new fills
            all_fills = existing_fills + fills

            # Save back to file
            with open(filepath, 'w') as f:
                json.dump(all_fills, f, indent=2, default=str)

            self.logger.info(f"Saved {len(fills)} fills to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving fills to {filename}: {str(e)}")
            return False