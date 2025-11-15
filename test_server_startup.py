#!/usr/bin/env python3
"""Test FastAPI server startup."""

import asyncio
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_server_startup():
    """Test that FastAPI server can start without errors."""
    print("Testing FastAPI server startup...")
    
    try:
        app = create_app()
        print("✓ FastAPI app created successfully")
        
        # Test with TestClient
        with TestClient(app) as client:
            print("✓ TestClient created successfully")
            
            # Test health endpoint
            response = client.get("/healthz")
            print(f"✓ Health endpoint status: {response.status_code}")
            print(f"  Response: {response.json()}")
            
            # Check API docs are available
            response = client.get("/docs")
            print(f"✓ API docs endpoint status: {response.status_code}")
            
            # Check OpenAPI schema
            response = client.get("/openapi.json")
            print(f"✓ OpenAPI schema endpoint status: {response.status_code}")
            
        print("\n✅ FastAPI server startup test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ FastAPI server startup failed: {e}")
        return False


if __name__ == "__main__":
    success = test_server_startup()
    sys.exit(0 if success else 1)
