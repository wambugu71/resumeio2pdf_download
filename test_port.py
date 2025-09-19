#!/usr/bin/env python3
"""
Test script to verify PORT environment variable handling
"""

import os
import sys
from config import config

def test_port_handling():
    """Test if PORT environment variable is handled correctly"""
    
    print("=== Port Handling Test ===")
    print(f"Environment variables:")
    print(f"  PORT: {os.getenv('PORT', 'Not set')}")
    print(f"  API_PORT: {os.getenv('API_PORT', 'Not set')}")
    print(f"  API_HOST: {os.getenv('API_HOST', 'Not set')}")
    print()
    
    print(f"Config values:")
    print(f"  config.port: {config.port}")
    print(f"  config.host: {config.host}")
    print(f"  config.debug: {config.debug}")
    print()
    
    # Test different scenarios
    test_cases = [
        ("No PORT set", {}),
        ("PORT=3000", {"PORT": "3000"}),
        ("API_PORT=4000", {"API_PORT": "4000"}),
        ("Both set, PORT priority", {"PORT": "5000", "API_PORT": "6000"}),
    ]
    
    for test_name, env_vars in test_cases:
        print(f"Test: {test_name}")
        
        # Backup original env
        original_env = {}
        for key in ["PORT", "API_PORT"]:
            original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]
        
        # Set test env
        for key, value in env_vars.items():
            os.environ[key] = value
        
        # Create new config
        from config import APIConfig
        test_config = APIConfig.from_env()
        
        print(f"  Result: port={test_config.port}")
        
        # Restore original env
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
        
        print()

if __name__ == "__main__":
    test_port_handling()
    
    print("=== Starting Server Test ===")
    print(f"Would start server with:")
    print(f"  uvicorn app:app --host {config.host} --port {config.port}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--start":
        print("Starting actual server...")
        import uvicorn
        uvicorn.run("app:app", host=config.host, port=config.port, reload=config.debug)
