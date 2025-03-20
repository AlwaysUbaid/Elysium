import requests
import json
from datetime import datetime
import time
import traceback
import sys

# API Configuration
BASE_URL = "http://localhost:8000"
TEST_WALLET = "0x4f7116a3B69b14480b0C0890d63bd4B3d0984EE6"
TEST_SECRET = "0x992df5cae22a4b8e3844f73e14756f11a2662b7f2e792ce78fd85abb63150d51"

def print_response(response, endpoint):
    """Print formatted response for an endpoint"""
    print(f"\n=== Testing {endpoint} ===")
    print(f"Status Code: {response.status_code}")
    try:
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print("Raw Response:")
        print(response.text)
    except Exception as e:
        print(f"Error printing response: {str(e)}")

def safe_request(method, url, **kwargs):
    """Make a request with error handling"""
    try:
        response = requests.request(method, url, **kwargs)
        return response
    except requests.exceptions.ConnectionError:
        print(f"Connection Error: Could not connect to {url}")
        print("Make sure the server is running on http://localhost:8000")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        return None

def test_health():
    """Test health check endpoint"""
    print("\nTesting server health...")
    response = safe_request("GET", f"{BASE_URL}/")
    if response:
        print_response(response, "Health Check")
        return response.status_code == 200
    return False

def test_connect():
    """Test connection endpoint"""
    print("\nTesting connection to exchange...")
    payload = {
        "network": "testnet",
        "credentials": {
            "wallet_address": TEST_WALLET,
            "secret_key": TEST_SECRET
        }
    }
    response = safe_request("POST", f"{BASE_URL}/connect", json=payload)
    if response:
        print_response(response, "Connect")
        return response.status_code == 200
    return False

def test_balances():
    """Test balances endpoint"""
    print("\nTesting balances endpoint...")
    response = safe_request("GET", f"{BASE_URL}/balances")
    if response:
        print_response(response, "Balances")
        return response.status_code == 200
    return False

def test_open_orders():
    """Test open orders endpoint"""
    print("\nTesting open orders endpoint...")
    response = safe_request("GET", f"{BASE_URL}/open-orders")
    if response:
        print_response(response, "Open Orders")
        return response.status_code == 200
    return False

def test_spot_market_buy():
    """Test spot market buy endpoint"""
    print("\nTesting spot market buy...")
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "slippage": 0.05
    }
    response = safe_request("POST", f"{BASE_URL}/api/v1/spot/market-buy", json=payload)
    if response:
        print_response(response, "Spot Market Buy")
        return response.status_code == 200
    return False

def test_spot_market_sell():
    """Test spot market sell endpoint"""
    print("\nTesting spot market sell...")
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "slippage": 0.05
    }
    response = safe_request("POST", f"{BASE_URL}/api/v1/spot/market-sell", json=payload)
    if response:
        print_response(response, "Spot Market Sell")
        return response.status_code == 200
    return False

def test_spot_limit_buy():
    """Test spot limit buy endpoint"""
    print("\nTesting spot limit buy...")
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "price": 50000.0
    }
    response = safe_request("POST", f"{BASE_URL}/api/v1/spot/limit-buy", json=payload)
    if response:
        print_response(response, "Spot Limit Buy")
        return response.status_code == 200
    return False

def test_spot_limit_sell():
    """Test spot limit sell endpoint"""
    print("\nTesting spot limit sell...")
    payload = {
        "symbol": "BTC/USDT",
        "size": 0.001,
        "price": 51000.0
    }
    response = safe_request("POST", f"{BASE_URL}/api/v1/spot/limit-sell", json=payload)
    if response:
        print_response(response, "Spot Limit Sell")
        return response.status_code == 200
    return False

def test_spot_cancel_order():
    """Test spot cancel order endpoint"""
    print("\nTesting spot cancel order...")
    # First get open orders to find an order ID
    response = safe_request("GET", f"{BASE_URL}/open-orders")
    if response and response.status_code == 200:
        try:
            orders = response.json().get("orders", [])
            if orders:
                order_id = orders[0]["order_id"]
                payload = {
                    "symbol": "BTC/USDT",
                    "order_id": order_id
                }
                response = safe_request("POST", f"{BASE_URL}/api/v1/spot/cancel-order", json=payload)
                if response:
                    print_response(response, "Spot Cancel Order")
                    return response.status_code == 200
        except Exception as e:
            print(f"Error processing orders: {str(e)}")
    return False

def test_spot_cancel_all_orders():
    """Test spot cancel all orders endpoint"""
    print("\nTesting spot cancel all orders...")
    response = safe_request("POST", f"{BASE_URL}/api/v1/spot/cancel-all-orders")
    if response:
        print_response(response, "Spot Cancel All Orders")
        return response.status_code == 200
    return False

def run_all_tests():
    """Run all tests in sequence"""
    print(f"\nStarting API Tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Make sure the server is running on http://localhost:8000")
    
    try:
        # Test health check
        if not test_health():
            print("\n❌ Health check failed. Please check if the server is running.")
            return
        
        # Test connection
        if not test_connect():
            print("\n❌ Connection failed. Please check your wallet credentials.")
            return
        
        # Wait a moment for connection to stabilize
        time.sleep(2)
        
        # Test read-only endpoints
        test_balances()
        test_open_orders()
        
        # Test trading endpoints
        test_spot_market_buy()
        time.sleep(2)  # Wait between trades
        test_spot_market_sell()
        time.sleep(2)
        test_spot_limit_buy()
        time.sleep(2)
        test_spot_limit_sell()
        time.sleep(2)
        
        # Test order management
        test_spot_cancel_order()
        time.sleep(2)
        test_spot_cancel_all_orders()
        
        print(f"\n✅ Completed API Tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during tests: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests() 