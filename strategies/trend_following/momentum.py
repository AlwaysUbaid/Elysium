# Momentum module
"""
Momentum-based trend following strategy for Elysium trading platform.

This module implements a momentum strategy using RSI, MACD, and moving averages.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from strategies.trend_following import TrendFollowingStrategy

logger = logging.getLogger(__name__)


class MomentumStrategy(TrendFollowingStrategy):
    """
    Momentum strategy implementation.

    This strategy uses a combination of RSI, MACD, and moving averages
    to identify trending markets and generate trading signals.
    """

    def __init__(
            self,
            exchange: Exchange,
            info: Info,
            symbols: List[str],
            params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize momentum strategy.

        Args:
            exchange: Exchange instance
            info: Info instance
            symbols: List of trading symbols
            params: Strategy parameters
        """
        # Default parameters
        default_params = {
            "candle_interval": "1h",
            "lookback_periods": 100,
            "short_ma_period": 9,
            "long_ma_period": 21,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast_period": 12,
            "macd_slow_period": 26,
            "macd_signal_period": 9,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "position_sizing_method": "risk",
            "risk_per_trade": 0.01,
            "max_position_size": 1000,
            "stop_loss_atr_multiplier": 2.0,
            "take_profit_atr_multiplier": 4.0,
            "min_volume": 0,  # Minimum trading volume
            "trend_confirmation_periods": 3,  # Number of periods to confirm trend
            "max_open_positions": 5,
            "max_positions_per_direction": 3,  # Maximum long or short positions
        }

        # Override defaults with provided params
        if params:
            default_params.update(params)

        super().__init__(
            name="Momentum Strategy",
            exchange=exchange,
            info=info,
            symbols=symbols,
            params=default_params,
            update_interval=60.0  # Check every minute
        )

        logger.info(f"Initialized Momentum Strategy with parameters: {default_params}")

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate momentum indicators for a DataFrame.

        Args:
            df: DataFrame with candle data

        Returns:
            Dictionary of indicator values
        """
        if df.empty:
            return {}

        indicators = {}

        try:
            # Create a copy to avoid modifying the original
            df_copy = df.copy()

            # Calculate moving averages
            short_ma_period = self.params["short_ma_period"]
            long_ma_period = self.params["long_ma_period"]

            df_copy['short_ma'] = df_copy['close'].rolling(window=short_ma_period).mean()
            df_copy['long_ma'] = df_copy['close'].rolling(window=long_ma_period).mean()

            # Calculate RSI
            rsi_period = self.params["rsi_period"]
            delta = df_copy['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=rsi_period).mean()

            rs = gain / loss
            df_copy['rsi'] = 100 - (100 / (1 + rs))

            # Calculate MACD
            macd_fast = self.params["macd_fast_period"]
            macd_slow = self.params["macd_slow_period"]
            macd_signal = self.params["macd_signal_period"]

            df_copy['ema_fast'] = df_copy['close'].ewm(span=macd_fast, adjust=False).mean()
            df_copy['ema_slow'] = df_copy['close'].ewm(span=macd_slow, adjust=False).mean()
            df_copy['macd'] = df_copy['ema_fast'] - df_copy['ema_slow']
            df_copy['macd_signal'] = df_copy['macd'].ewm(span=macd_signal, adjust=False).mean()
            df_copy['macd_histogram'] = df_copy['macd'] - df_copy['macd_signal']

            # Calculate ATR
            atr_period = self.params["atr_period"]
            df_copy['tr'] = np.maximum(
                df_copy['high'] - df_copy['low'],
                np.maximum(
                    abs(df_copy['high'] - df_copy['close'].shift()),
                    abs(df_copy['low'] - df_copy['close'].shift())
                )
            )
            df_copy['atr'] = df_copy['tr'].rolling(window=atr_period).mean()

            # Calculate trend indicators
            df_copy['ma_trend'] = (df_copy['short_ma'] > df_copy['long_ma']).astype(
                int) * 2 - 1  # 1 for uptrend, -1 for downtrend
            df_copy['rsi_trend'] = ((df_copy['rsi'] > 50).astype(int) * 2 - 1)  # 1 for uptrend, -1 for downtrend
            df_copy['macd_trend'] = ((df_copy['macd'] > df_copy['macd_signal']).astype(
                int) * 2 - 1)  # 1 for uptrend, -1 for downtrend

            # Calculate trend confirmation
            df_copy['trend_strength'] = (df_copy['ma_trend'] + df_copy['rsi_trend'] + df_copy['macd_trend']) / 3

            # Store the calculated indicators
            indicators = {
                'short_ma': df_copy['short_ma'].iloc[-1],
                'long_ma': df_copy['long_ma'].iloc[-1],
                'rsi': df_copy['rsi'].iloc[-1],
                'macd': df_copy['macd'].iloc[-1],
                'macd_signal': df_copy['macd_signal'].iloc[-1],
                'macd_histogram': df_copy['macd_histogram'].iloc[-1],
                'atr': df_copy['atr'].iloc[-1],
                'trend_strength': df_copy['trend_strength'].iloc[-1],
                'ma_trend': df_copy['ma_trend'].iloc[-1],
                'rsi_trend': df_copy['rsi_trend'].iloc[-1],
                'macd_trend': df_copy['macd_trend'].iloc[-1],
                'df': df_copy  # Store the entire dataframe with indicators
            }

            # Calculate trend confirmation
            indicators['trend_confirmed'] = False
            confirmation_periods = self.params["trend_confirmation_periods"]

            if len(df_copy) >= confirmation_periods:
                if all(df_copy['trend_strength'].iloc[-confirmation_periods:] > 0.5):
                    indicators['trend_confirmed'] = True
                    indicators['confirmed_trend'] = 'uptrend'
                elif all(df_copy['trend_strength'].iloc[-confirmation_periods:] < -0.5):
                    indicators['trend_confirmed'] = True
                    indicators['confirmed_trend'] = 'downtrend'

        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")

        return indicators

    def _generate_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Signal dictionary or None
        """
        if symbol not in self.indicators:
            return None

        try:
            indicators = self.indicators[symbol]
            if not indicators:
                return None

            # Get current position
            current_position = self.position_sizes.get(symbol, 0)

            # Get current price
            df = self.candle_data.get(symbol)
            if df.empty:
                return None

            current_price = float(df.iloc[-1]['close'])

            # Check how many positions we have in each direction
            long_positions = 0
            short_positions = 0

            for sym, pos in self.position_sizes.items():
                if pos > 0:
                    long_positions += 1
                elif pos < 0:
                    short_positions += 1

            # Get indicators
            rsi = indicators.get('rsi')
            rsi_overbought = self.params.get('rsi_overbought')
            rsi_oversold = self.params.get('rsi_oversold')
            macd = indicators.get('macd')
            macd_signal = indicators.get('macd_signal')
            short_ma = indicators.get('short_ma')
            long_ma = indicators.get('long_ma')
            atr = indicators.get('atr', 0)
            trend_strength = indicators.get('trend_strength')
            trend_confirmed = indicators.get('trend_confirmed')
            confirmed_trend = indicators.get('confirmed_trend')

            # Signal logic
            signal = None

            # Neutral/Exit signal conditions
            if (current_position > 0 and (
                    rsi > rsi_overbought or
                    macd < macd_signal or
                    short_ma < long_ma)):
                signal = "neutral"

            elif (current_position < 0 and (
                    rsi < rsi_oversold or
                    macd > macd_signal or
                    short_ma > long_ma)):
                signal = "neutral"

            # Long signal conditions
            elif (current_position <= 0 and
                  rsi > 50 and rsi < rsi_overbought and
                  macd > macd_signal and
                  short_ma > long_ma and
                  trend_strength > 0.5 and
                  trend_confirmed and confirmed_trend == 'uptrend' and
                  long_positions < self.params.get('max_positions_per_direction')):
                signal = "long"

            # Short signal conditions
            elif (current_position >= 0 and
                  rsi < 50 and rsi > rsi_oversold and
                  macd < macd_signal and
                  short_ma < long_ma and
                  trend_strength < -0.5 and
                  trend_confirmed and confirmed_trend == 'downtrend' and
                  short_positions < self.params.get('max_positions_per_direction')):
                signal = "short"

            if signal:
                # Calculate stop loss and take profit prices
                stop_loss_price = 0
                take_profit_price = 0

                if signal == "long":
                    stop_loss_price = current_price - (atr * self.params.get('stop_loss_atr_multiplier'))
                    take_profit_price = current_price + (atr * self.params.get('take_profit_atr_multiplier'))
                elif signal == "short":
                    stop_loss_price = current_price + (atr * self.params.get('stop_loss_atr_multiplier'))
                    take_profit_price = current_price - (atr * self.params.get('take_profit_atr_multiplier'))
                elif signal == "neutral":
                    # For exit signals, we don't need stop loss or take profit
                    pass

                # Calculate position size
                if signal in ["long", "short"]:
                    # Create temporary signal dict for position sizing
                    temp_signal = {
                        "signal": signal,
                        "price": current_price,
                        "stop_loss": stop_loss_price,
                        "take_profit": take_profit_price
                    }

                    position_size = self._calculate_position_size(symbol, temp_signal)
                else:
                    position_size = 0

                # Create and return signal dict
                return {
                    "signal": signal,
                    "timestamp": df.iloc[-1]['datetime'],
                    "price": current_price,
                    "stop_loss": stop_loss_price,
                    "take_profit": take_profit_price,
                    "position_size": position_size,
                    "indicators": {
                        "rsi": rsi,
                        "macd": macd,
                        "macd_signal": macd_signal,
                        "short_ma": short_ma,
                        "long_ma": long_ma,
                        "atr": atr,
                        "trend_strength": trend_strength
                    }
                }

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {str(e)}")

        return None