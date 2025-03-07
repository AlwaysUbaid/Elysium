# Cross Exchange module
"""
Cross-exchange arbitrage strategy for Elysium trading platform.

This module implements cross-exchange arbitrage between Hyperliquid and other exchanges.
"""

import logging
import time
import ccxt
from typing import Dict, Any, Optional, List, Tuple

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from strategies.arb import ArbitrageStrategy

logger = logging.getLogger(__name__)


class CrossExchangeArbitrage(ArbitrageStrategy):
    """Cross-exchange arbitrage strategy."""

    def __init__(
            self,
            hyperliquid_exchange: Exchange,
            hyperliquid_info: Info,
            other_exchange_id: str,
            other_exchange_config: Dict[str, Any],
            symbols: List[str],
            params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize cross-exchange arbitrage strategy.

        Args:
            hyperliquid_exchange: Hyperliquid Exchange instance
            hyperliquid_info: Hyperliquid Info instance
            other_exchange_id: CCXT exchange ID (e.g., 'binance', 'bybit')
            other_exchange_config: CCXT exchange configuration
            symbols: List of trading symbols (in Hyperliquid format)
            params: Strategy parameters
        """
        # Default parameters
        default_params = {
            "min_profit_threshold": 0.002,  # Minimum profit threshold (0.2%)
            "max_position_per_pair": 1000,  # Maximum position size per pair
            "execution_delay": 0.1,  # Delay between leg executions (seconds)
            "max_slippage": 0.0005,  # Maximum acceptable slippage (0.05%)
            "fee_hyperliquid": 0.0005,  # Hyperliquid trading fee rate (0.05%)
            "fee_other_exchange": 0.0006,  # Other exchange trading fee rate (0.06%)
            "symbol_mapping": {},  # Mapping from Hyperliquid to other exchange symbols
            "threshold_buffer": 1.5,  # Buffer multiplier for profit threshold to account for execution risk
            "max_trade_attempts": 3,  # Maximum number of attempts for trade execution
            "retry_delay": 1.0,  # Delay between retry attempts (seconds)
        }

        # Override defaults with provided params
        if params:
            default_params.update(params)

        # Initialize Arbitrage Strategy
        super().__init__(
            name=f"Cross Exchange Arbitrage (Hyperliquid-{other_exchange_id})",
            exchange=hyperliquid_exchange,
            info=hyperliquid_info,
            symbols=symbols,
            params=default_params,
            update_interval=1.0  # Check every second
        )

        # Initialize other exchange
        self.other_exchange_id = other_exchange_id
        exchange_class = getattr(ccxt, other_exchange_id)
        self.other_exchange = exchange_class(other_exchange_config)

        # Create symbol mapping if not provided
        if not self.params["symbol_mapping"]:
            self._create_symbol_mapping()

        logger.info(f"Initialized {self.name} for {len(symbols)} symbols")

    def _create_symbol_mapping(self):
        """Create mapping between Hyperliquid and other exchange symbols."""
        mapping = {}

        try:
            # Load markets from other exchange
            other_markets = self.other_exchange.load_markets()

            for hl_symbol in self.symbols:
                # Handle Hyperliquid spot symbols with @index notation
                if hl_symbol.startswith("@"):
                    # Map special cases
                    if hl_symbol == "@140":
                        base = "HWTR"
                        quote = "USDC"
                        mapped = f"{base}/{quote}"
                    else:
                        # For unknown index symbols, skip
                        continue
                # Handle regular symbols like ETH, BTC (perps)
                elif "/" not in hl_symbol:
                    base = hl_symbol
                    quote = "USDC"
                    mapped = f"{base}/{quote}:USDC"  # CCXT perpetual format
                # Handle regular spot symbols
                else:
                    mapped = hl_symbol

                # Check if the mapped symbol exists in the other exchange
                if mapped in other_markets:
                    mapping[hl_symbol] = mapped
                elif f"{base}/USDT:USDT" in other_markets:
                    mapping[hl_symbol] = f"{base}/USDT:USDT"
                elif f"{base}/USDT" in other_markets:
                    mapping[hl_symbol] = f"{base}/USDT"

            self.params["symbol_mapping"] = mapping
            logger.info(f"Created symbol mapping: {mapping}")

        except Exception as e:
            logger.error(f"Error creating symbol mapping: {str(e)}")

    def initialize(self):
        """Initialize strategy-specific state."""
        try:
            # Ensure markets are loaded
            self.other_exchange.load_markets()

            # Check which symbols are actually available on both exchanges
            valid_symbols = []

            for hl_symbol in self.symbols:
                if hl_symbol in self.params["symbol_mapping"]:
                    other_symbol = self.params["symbol_mapping"][hl_symbol]
                    valid_symbols.append(hl_symbol)
                    logger.info(f"Arbitrage pair available: {hl_symbol} (Hyperliquid) <-> {other_symbol} (Other)")
                else:
                    logger.warning(f"No mapping found for {hl_symbol}, excluding from arbitrage")

            self.symbols = valid_symbols

            if not valid_symbols:
                logger.warning("No valid arbitrage pairs found")

        except Exception as e:
            logger.error(f"Error initializing cross-exchange arbitrage: {str(e)}")

    def find_opportunities(self) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities between Hyperliquid and other exchange.

        Returns:
            List of arbitrage opportunities
        """
        opportunities = []

        try:
            # Get all midprices from Hyperliquid
            hyperliquid_mids = self.info.all_mids()

            for hl_symbol in self.symbols:
                if hl_symbol not in self.params["symbol_mapping"]:
                    continue

                other_symbol = self.params["symbol_mapping"][hl_symbol]

                # Get Hyperliquid orderbook
                hl_orderbook = self.info.l2_snapshot(hl_symbol)
                if not hl_orderbook or "levels" not in hl_orderbook or len(hl_orderbook["levels"]) < 2:
                    continue

                hl_bids = hl_orderbook["levels"][0]
                hl_asks = hl_orderbook["levels"][1]

                if not hl_bids or not hl_asks:
                    continue

                hl_best_bid = float(hl_bids[0]["px"])
                hl_best_ask = float(hl_asks[0]["px"])
                hl_bid_size = float(hl_bids[0]["sz"])
                hl_ask_size = float(hl_asks[0]["sz"])

                # Get other exchange orderbook
                try:
                    other_orderbook = self.other_exchange.fetch_order_book(other_symbol)
                    if not other_orderbook or not other_orderbook["bids"] or not other_orderbook["asks"]:
                        continue

                    other_best_bid = float(other_orderbook["bids"][0][0])
                    other_best_ask = float(other_orderbook["asks"][0][0])
                    other_bid_size = float(other_orderbook["bids"][0][1])
                    other_ask_size = float(other_orderbook["asks"][0][1])
                except Exception as e:
                    logger.error(f"Error fetching orderbook for {other_symbol}: {str(e)}")
                    continue

                # Calculate potential arbitrage opportunities

                # Opportunity 1: Buy on Hyperliquid, Sell on Other Exchange
                size_for_opp1 = min(hl_ask_size, other_bid_size, self.params["max_position_per_pair"])

                if size_for_opp1 > 0:
                    profit1, profit_pct1 = self.calculate_arbitrage_profit(
                        buy_price=hl_best_ask,
                        sell_price=other_best_bid,
                        trade_size=size_for_opp1,
                        fee_rate=self.params["fee_hyperliquid"] + self.params["fee_other_exchange"]
                    )

                    if profit_pct1 >= self.params["min_profit_threshold"] * self.params["threshold_buffer"]:
                        opportunities.append({
                            "type": "hl_to_other",
                            "hl_symbol": hl_symbol,
                            "other_symbol": other_symbol,
                            "hl_price": hl_best_ask,
                            "other_price": other_best_bid,
                            "size": size_for_opp1,
                            "expected_profit": profit1,
                            "expected_profit_pct": profit_pct1,
                            "timestamp": hl_orderbook["time"]
                        })

                # Opportunity 2: Buy on Other Exchange, Sell on Hyperliquid
                size_for_opp2 = min(other_ask_size, hl_bid_size, self.params["max_position_per_pair"])

                if size_for_opp2 > 0:
                    profit2, profit_pct2 = self.calculate_arbitrage_profit(
                        buy_price=other_best_ask,
                        sell_price=hl_best_bid,
                        trade_size=size_for_opp2,
                        fee_rate=self.params["fee_hyperliquid"] + self.params["fee_other_exchange"]
                    )

                    if profit_pct2 >= self.params["min_profit_threshold"] * self.params["threshold_buffer"]:
                        opportunities.append({
                            "type": "other_to_hl",
                            "hl_symbol": hl_symbol,
                            "other_symbol": other_symbol,
                            "hl_price": hl_best_bid,
                            "other_price": other_best_ask,
                            "size": size_for_opp2,
                            "expected_profit": profit2,
                            "expected_profit_pct": profit_pct2,
                            "timestamp": hl_orderbook["time"]
                        })

            # Sort by expected profit percentage
            opportunities.sort(key=lambda x: x["expected_profit_pct"], reverse=True)

        except Exception as e:
            logger.error(f"Error finding arbitrage opportunities: {str(e)}")

        return opportunities

    def execute_arbitrage(self, opportunity: Dict[str, Any]) -> bool:
        """
        Execute an arbitrage opportunity.

        Args:
            opportunity: Arbitrage opportunity details

        Returns:
            True if successfully executed, False otherwise
        """
        hl_symbol = opportunity["hl_symbol"]
        other_symbol = opportunity["other_symbol"]
        size = opportunity["size"]
        opportunity_type = opportunity["type"]

        logger.info(f"Executing {opportunity_type} arbitrage for {hl_symbol}/{other_symbol} with size {size}")

        try:
            # Execute Hyperliquid leg first for hl_to_other, otherwise execute other exchange leg first
            if opportunity_type == "hl_to_other":
                # Buy on Hyperliquid (taker order)
                hl_result = self.exchange.market_open(
                    hl_symbol,
                    True,  # is_buy
                    size,
                    opportunity["hl_price"],
                    slippage=self.params["max_slippage"]
                )

                if hl_result["status"] != "ok":
                    logger.error(f"Failed to execute Hyperliquid leg: {hl_result}")
                    return False

                # Delay to avoid race conditions
                time.sleep(self.params["execution_delay"])

                # Sell on other exchange
                other_result = self.other_exchange.create_market_sell_order(other_symbol, size)
                logger.info(f"Other exchange leg result: {other_result}")

                return True

            elif opportunity_type == "other_to_hl":
                # Buy on other exchange
                other_result = self.other_exchange.create_market_buy_order(other_symbol, size)
                logger.info(f"Other exchange leg result: {other_result}")

                # Delay to avoid race conditions
                time.sleep(self.params["execution_delay"])

                # Sell on Hyperliquid (taker order)
                hl_result = self.exchange.market_open(
                    hl_symbol,
                    False,  # is_buy
                    size,
                    opportunity["hl_price"],
                    slippage=self.params["max_slippage"]
                )

                if hl_result["status"] != "ok":
                    logger.error(f"Failed to execute Hyperliquid leg: {hl_result}")
                    # At this point we have a position on the other exchange that needs to be closed
                    logger.warning(f"Attempting to close position on {other_symbol} due to failed second leg")
                    self.other_exchange.create_market_sell_order(other_symbol, size)
                    return False

                return True

            return False

        except Exception as e:
            logger.error(f"Error executing arbitrage: {str(e)}")
            return False

    def stop(self) -> bool:
        """
        Stop the strategy.

        Returns:
            True if successfully stopped, False otherwise
        """
        result = super().stop()

        # Close the CCXT exchange connection
        try:
            if hasattr(self.other_exchange, 'close'):
                self.other_exchange.close()
        except Exception as e:
            logger.error(f"Error closing other exchange connection: {str(e)}")

        return result