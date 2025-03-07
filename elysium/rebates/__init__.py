# Initialize the module
"""
Rebates module for Elysium trading platform.

This module provides functionality for tracking and optimizing
exchange rebates and fees on Hyperliquid.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

import pandas as pd

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

logger = logging.getLogger(__name__)


class RebateTracker:
    """Track and analyze exchange fee rebates."""

    def __init__(
            self,
            exchange: Exchange,
            info: Info,
            data_dir: str = "data/rebates",
            fee_tiers: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize rebate tracker.

        Args:
            exchange: Exchange instance
            info: Info instance
            data_dir: Directory to store rebate data
            fee_tiers: Fee tier information
        """
        self.exchange = exchange
        self.info = info
        self.data_dir = data_dir

        # Create data directory
        os.makedirs(data_dir, exist_ok=True)

        # Initialize fee tiers
        self.fee_tiers = fee_tiers or {
            "maker": {
                "default": -0.0003,  # -0.03%
                "tiers": [
                    {"volume": 0, "fee": -0.0003},  # -0.03%
                    {"volume": 1000000, "fee": -0.0004},  # -0.04%
                    {"volume": 5000000, "fee": -0.0005},  # -0.05%
                    {"volume": 10000000, "fee": -0.00055},  # -0.055%
                    {"volume": 20000000, "fee": -0.0006},  # -0.06%
                    {"volume": 50000000, "fee": -0.00065},  # -0.065%
                ]
            },
            "taker": {
                "default": 0.0005,  # 0.05%
                "tiers": [
                    {"volume": 0, "fee": 0.0005},  # 0.05%
                    {"volume": 1000000, "fee": 0.00045},  # 0.045%
                    {"volume": 5000000, "fee": 0.0004},  # 0.04%
                    {"volume": 10000000, "fee": 0.00035},  # 0.035%
                    {"volume": 20000000, "fee": 0.0003},  # 0.03%
                    {"volume": 50000000, "fee": 0.00025},  # 0.025%
                ]
            },
            "referral": {
                "default": 0.0,
                "rebate": 0.1  # 10% of fees refunded through referral
            }
        }

        # Initialize rebate data
        self.trade_history: Dict[str, pd.DataFrame] = {}
        self.fee_history: Dict[str, pd.DataFrame] = {}
        self.daily_volume: Dict[str, float] = {}
        self.monthly_volume: Dict[str, float] = {}
        self.current_tier: Dict[str, Any] = {
            "maker": self.fee_tiers["maker"]["default"],
            "taker": self.fee_tiers["taker"]["default"]
        }

        logger.info(f"Initialized rebate tracker with data directory: {data_dir}")

    def load_trade_history(self, address: Optional[str] = None, days: int = 30) -> None:
        """
        Load trade history for fee analysis.

        Args:
            address: Wallet address (or None to use exchange wallet address)
            days: Number of days of history to load
        """
        if address is None:
            address = self.exchange.wallet.address

        try:
            # Fetch trade history from exchange
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

            # Try to get user fills from fills file first
            fills = []
            try:
                with open("fills", "r") as f:
                    for line in f:
                        fills.extend(json.loads(line.strip()))

                # Filter by date
                fills = [fill for fill in fills if fill.get("time", 0) >= start_time]
            except (FileNotFoundError, json.JSONDecodeError):
                # If file doesn't exist or is invalid, fetch from API
                fills = self.info.user_fills_by_time(address, start_time)

            if not fills:
                logger.warning(f"No trade history found for {address}")
                return

            # Convert to DataFrame
            df = pd.DataFrame(fills)

            if df.empty:
                logger.warning(f"No trade history found for {address}")
                return

            # Format DataFrame
            df["datetime"] = pd.to_datetime(df["time"], unit="ms")
            df["date"] = df["datetime"].dt.date
            df["size"] = pd.to_numeric(df["sz"])
            df["price"] = pd.to_numeric(df["px"])
            df["value"] = df["size"] * df["price"]

            if "fee" in df.columns:
                df["fee"] = pd.to_numeric(df["fee"])
            else:
                # Estimate fee if not available
                df["is_maker"] = ~df["crossed"]
                df["fee"] = df.apply(lambda row: self._estimate_fee(row["value"], row["is_maker"]), axis=1)

            # Group by date and calculate daily volume
            daily = df.groupby("date").agg({
                "value": "sum",
                "fee": "sum",
                "size": "sum"
            }).reset_index()

            self.trade_history[address] = df
            self.fee_history[address] = daily

            # Calculate total volume for tier determination
            self.daily_volume[address] = daily["value"].sum()

            # Determine current fee tier
            self._update_fee_tier(address)

            logger.info(f"Loaded {len(df)} trades for {address} covering {len(daily)} days")
            logger.info(f"Total trading volume: ${self.daily_volume[address]:,.2f}")
            logger.info(
                f"Current fee tier: Maker {self.current_tier['maker'] * 100:.4f}%, Taker {self.current_tier['taker'] * 100:.4f}%")

        except Exception as e:
            logger.error(f"Error loading trade history: {str(e)}")

    def _estimate_fee(self, trade_value: float, is_maker: bool) -> float:
        """
        Estimate fee for a trade.

        Args:
            trade_value: Trade value
            is_maker: Whether the trade was a maker order

        Returns:
            Estimated fee amount
        """
        if is_maker:
            fee_rate = self.fee_tiers["maker"]["default"]
        else:
            fee_rate = self.fee_tiers["taker"]["default"]

        return trade_value * fee_rate

    def _update_fee_tier(self, address: str) -> None:
        """
        Update fee tier based on trading volume.

        Args:
            address: Wallet address
        """
        if address not in self.daily_volume:
            return

        volume = self.daily_volume[address]

        # Determine maker tier
        maker_tier = self.fee_tiers["maker"]["default"]
        for tier in reversed(self.fee_tiers["maker"]["tiers"]):
            if volume >= tier["volume"]:
                maker_tier = tier["fee"]
                break

        # Determine taker tier
        taker_tier = self.fee_tiers["taker"]["default"]
        for tier in reversed(self.fee_tiers["taker"]["tiers"]):
            if volume >= tier["volume"]:
                taker_tier = tier["fee"]
                break

        self.current_tier = {
            "maker": maker_tier,
            "taker": taker_tier,
            "volume": volume
        }

    def get_fee_summary(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get fee summary for an address.

        Args:
            address: Wallet address (or None to use exchange wallet address)

        Returns:
            Fee summary dictionary
        """
        if address is None:
            address = self.exchange.wallet.address

        if address not in self.fee_history:
            self.load_trade_history(address)

        if address not in self.fee_history or self.fee_history[address].empty:
            logger.warning(f"No fee history available for {address}")
            return {
                "address": address,
                "total_fees": 0,
                "maker_fees": 0,
                "taker_fees": 0,
                "total_volume": 0,
                "current_tier": self.current_tier
            }

        df = self.trade_history[address]

        # Calculate fee breakdown
        maker_fees = df[df["is_maker"]]["fee"].sum() if "is_maker" in df.columns else 0
        taker_fees = df[~df["is_maker"]]["fee"].sum() if "is_maker" in df.columns else df["fee"].sum()
        total_volume = df["value"].sum()

        return {
            "address": address,
            "total_fees": maker_fees + taker_fees,
            "maker_fees": maker_fees,
            "taker_fees": taker_fees,
            "total_volume": total_volume,
            "fee_to_volume_ratio": (maker_fees + taker_fees) / total_volume if total_volume > 0 else 0,
            "current_tier": self.current_tier,
            "last_updated": datetime.now()
        }

    def save_fee_history(self, address: Optional[str] = None) -> bool:
        """
        Save fee history to file.

        Args:
            address: Wallet address (or None to use exchange wallet address)

        Returns:
            True if successful, False otherwise
        """
        if address is None:
            address = self.exchange.wallet.address

        if address not in self.fee_history or self.fee_history[address].empty:
            logger.warning(f"No fee history available for {address}")
            return False

        try:
            # Save fee history to CSV
            filename = os.path.join(self.data_dir, f"fee_history_{address[-8:]}.csv")
            self.fee_history[address].to_csv(filename, index=False)

            # Save fee summary to JSON
            summary = self.get_fee_summary(address)
            summary_filename = os.path.join(self.data_dir, f"fee_summary_{address[-8:]}.json")

            with open(summary_filename, "w") as f:
                json.dump(summary, f, indent=2, default=str)

            logger.info(f"Saved fee history for {address} to {filename} and {summary_filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving fee history: {str(e)}")
            return False

    def get_optimal_order_type(self, order_size: float, symbol: str) -> str:
        """
        Get optimal order type (limit or market) based on fee tiers.

        Args:
            order_size: Order size in base currency
            symbol: Trading symbol

        Returns:
            Recommended order type ("limit" or "market")
        """
        try:
            # Get current price
            price = 0
            try:
                all_mids = self.info.all_mids()
                if symbol in all_mids:
                    price = float(all_mids[symbol])
            except Exception:
                pass

            if price <= 0:
                # Try getting from order book
                try:
                    book = self.info.l2_snapshot(symbol)
                    if book and "levels" in book and len(book["levels"]) >= 2:
                        if len(book["levels"][0]) > 0 and len(book["levels"][1]) > 0:
                            bid = float(book["levels"][0][0]["px"])
                            ask = float(book["levels"][1][0]["px"])
                            price = (bid + ask) / 2
                except Exception:
                    pass

            if price <= 0:
                # Default recommendation if we can't get price
                return "limit"

            # Calculate trade value
            trade_value = order_size * price

            # Calculate fees for maker vs taker
            maker_fee = trade_value * self.current_tier["maker"]
            taker_fee = trade_value * self.current_tier["taker"]

            # Calculate price improvement needed to offset fee difference
            fee_difference = taker_fee - maker_fee
            price_improvement_needed = fee_difference / order_size

            # Get current spread
            spread = 0
            try:
                book = self.info.l2_snapshot(symbol)
                if book and "levels" in book and len(book["levels"]) >= 2:
                    if len(book["levels"][0]) > 0 and len(book["levels"][1]) > 0:
                        bid = float(book["levels"][0][0]["px"])
                        ask = float(book["levels"][1][0]["px"])
                        spread = ask - bid
            except Exception:
                pass

            # Make recommendation
            # If price improvement needed is greater than half the spread,
            # then limit order is better
            if spread > 0 and price_improvement_needed > spread / 2:
                return "limit"
            else:
                return "market"

        except Exception as e:
            logger.error(f"Error determining optimal order type: {str(e)}")
            return "limit"  # Default to limit

    def calculate_rebate_optimization(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate potential rebate optimizations.

        Args:
            address: Wallet address (or None to use exchange wallet address)

        Returns:
            Rebate optimization recommendations
        """
        if address is None:
            address = self.exchange.wallet.address

        if address not in self.trade_history:
            self.load_trade_history(address)

        if address not in self.trade_history or self.trade_history[address].empty:
            logger.warning(f"No trade history available for {address}")
            return {
                "address": address,
                "recommendations": [],
                "potential_savings": 0
            }

        try:
            df = self.trade_history[address]

            # Calculate current fees
            current_fees = df["fee"].sum()

            # Estimate optimal fees assuming all orders were makers
            optimal_maker_rate = self.current_tier["maker"]
            df["optimal_fee"] = df["value"] * optimal_maker_rate
            optimal_fees = df["optimal_fee"].sum()

            # Calculate potential savings
            potential_savings = current_fees - optimal_fees

            # Market breakdown
            market_stats = df.groupby("coin").agg({
                "value": "sum",
                "fee": "sum",
                "optimal_fee": "sum"
            }).reset_index()

            market_stats["potential_savings"] = market_stats["fee"] - market_stats["optimal_fee"]
            market_stats["savings_percentage"] = (market_stats["potential_savings"] / market_stats["fee"]) * 100

            # Create recommendations
            recommendations = []

            for _, row in market_stats.iterrows():
                if row["potential_savings"] > 0:
                    recommendations.append({
                        "symbol": row["coin"],
                        "trading_volume": row["value"],
                        "current_fees": row["fee"],
                        "potential_fees": row["optimal_fee"],
                        "potential_savings": row["potential_savings"],
                        "savings_percentage": row["savings_percentage"],
                        "recommendation": "Use limit orders to maximize maker rebates"
                    })

            # Sort by potential savings
            recommendations.sort(key=lambda x: x["potential_savings"], reverse=True)

            return {
                "address": address,
                "total_volume": df["value"].sum(),
                "current_fees": current_fees,
                "optimal_fees": optimal_fees,
                "potential_savings": potential_savings,
                "savings_percentage": (potential_savings / current_fees) * 100 if current_fees != 0 else 0,
                "recommendations": recommendations,
                "current_tier": self.current_tier,
                "next_tier": self._get_next_tier_info(df["value"].sum())
            }

        except Exception as e:
            logger.error(f"Error calculating rebate optimization: {str(e)}")
            return {
                "address": address,
                "recommendations": [],
                "potential_savings": 0,
                "error": str(e)
            }

    def _get_next_tier_info(self, current_volume: float) -> Dict[str, Any]:
        """
        Get information about the next fee tier.

        Args:
            current_volume: Current trading volume

        Returns:
            Next tier information
        """
        # Find next maker tier
        next_maker_tier = None
        for tier in self.fee_tiers["maker"]["tiers"]:
            if tier["volume"] > current_volume:
                next_maker_tier = tier
                break

        # Find next taker tier
        next_taker_tier = None
        for tier in self.fee_tiers["taker"]["tiers"]:
            if tier["volume"] > current_volume:
                next_taker_tier = tier
                break

        if next_maker_tier is None and next_taker_tier is None:
            return {
                "exists": False,
                "message": "Already at highest tier"
            }

        # Use the tier with the smaller volume requirement
        if next_maker_tier is None:
            next_tier = next_taker_tier
            tier_type = "taker"
        elif next_taker_tier is None:
            next_tier = next_maker_tier
            tier_type = "maker"
        else:
            if next_maker_tier["volume"] < next_taker_tier["volume"]:
                next_tier = next_maker_tier
                tier_type = "maker"
            else:
                next_tier = next_taker_tier
                tier_type = "taker"

        volume_needed = next_tier["volume"] - current_volume

        return {
            "exists": True,
            "type": tier_type,
            "volume": next_tier["volume"],
            "fee": next_tier["fee"],
            "volume_needed": volume_needed,
            "percentage_to_next_tier": (current_volume / next_tier["volume"]) * 100
        }