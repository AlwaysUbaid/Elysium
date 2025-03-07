# elysium/strategies/__init__.py
from typing import List, Type, Dict, Any

def get_available_strategies() -> List[str]:
    """
    Get a list of available strategy names.
    
    Returns:
        List of strategy names
    """
    return [
        "basic_market_making",
        "market_order_making"
    ]

def get_strategy_class(strategy_name: str):
    """
    Get the class for a strategy by name.
    
    Args:
        strategy_name: Name of the strategy
        
    Returns:
        Strategy class
    """
    if strategy_name == "basic_market_making":
        from elysium.strategies.market_making.basic_mm import BasicMarketMaking
        return BasicMarketMaking
    elif strategy_name == "market_order_making":
        from elysium.strategies.market_making.market_mm import MarketOrderMaking
        return MarketOrderMaking
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
def get_strategy_default_parameters(strategy_name: str, token_pair: Dict[str, str]) -> Dict[str, Any]:
    """
    Get default parameters for a strategy.
    
    Args:
        strategy_name: Name of the strategy
        token_pair: Token pair information
        
    Returns:
        Dictionary of default parameters
    """
    strategy_class = get_strategy_class(strategy_name)
    if hasattr(strategy_class, 'get_default_parameters'):
        defaults = strategy_class.get_default_parameters()
        # Override with token pair info
        defaults['symbol'] = token_pair['api_symbol']
        defaults['display_name'] = token_pair['display_name']
        return defaults
    
    # Fallback default parameters
    if strategy_name == "basic_market_making":
        return {
            "symbol": token_pair["api_symbol"],
            "display_name": token_pair["display_name"],
            "max_order_size": 1000.0 if "KOGU" in token_pair["symbol"] else 0.1,
            "min_order_size": 100.0 if "KOGU" in token_pair["symbol"] else 0.01,
            "position_use_pct": 0.90,
            "initial_offset": 0.0005,
            "min_offset": 0.0003,
            "offset_reduction": 0.00005,
            "order_refresh_time": 15
        }
    elif strategy_name == "market_order_making":
        return {
            "symbol": token_pair["api_symbol"],
            "display_name": token_pair["display_name"],
            "max_order_size": 1000.0 if "KOGU" in token_pair["symbol"] else 0.1,
            "min_order_size": 100.0 if "KOGU" in token_pair["symbol"] else 0.01,
            "target_position": 5000.0 if "KOGU" in token_pair["symbol"] else 1.0,
            "rebalance_threshold": 0.1,
            "order_interval": 30.0,
            "max_slippage": 0.005,
            "order_size_pct": 0.2
        }
    
    return {}