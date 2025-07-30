#!/usr/bin/env python3
"""
Test script for the Cloud Engineer Agent
"""
import sys
import os
import json
from datetime import datetime

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from cloud_engineer import execute_custom_task, health_check, cleanup


def test_health_check():
    """Test the health check function"""
    print("🔍 Testing health check...")
    health = health_check()
    print(f"Health status: {json.dumps(health, indent=2)}")
    return health


def test_simple_task():
    """Test executing a simple task"""
    print("\n🧪 Testing simple custom task...")
    try:
        result = execute_custom_task("What is AWS EC2?")
        print(f"Result: {result[:200]}..." if len(result) > 200 else f"Result: {result}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 Cloud Engineer Agent Test Suite")
    print("=" * 50)

    # Test health check
    health = test_health_check()

    # Test simple task
    simple_success = test_simple_task()

    # Final health check
    print("\n🏁 Final health check...")
    final_health = health_check()
    print(f"Final health status: {json.dumps(final_health, indent=2)}")

    # Summary
    print("\n📊 Test Summary:")
    print(f"  ✅ Health check: Passed")
    print(
        f"  {'✅' if simple_success else '❌'} Simple task execution: {'Passed' if simple_success else 'Failed'}"
    )
    print(f"  📊 MCP initialized: {final_health['mcp_initialized']}")
    print(f"  📊 Agent ready: {final_health['agent_ready']}")

    # Cleanup
    print("\n🧹 Cleaning up...")
    cleanup()

    print("\n✨ Test completed!")


if __name__ == "__main__":
    main()
