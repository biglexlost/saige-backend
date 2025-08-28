#!/usr/bin/env python3
"""
🧪 Test Redis Connection Script
Tests the Redis connection using environment variables.
"""

import os
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_redis_connection():
    """Test Redis connection with environment variables."""
    print("🧪 Testing Redis Connection...")
    
    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL")
    
    if not redis_url:
        print("❌ REDIS_URL not found in environment")
        print("\n💡 Check your REDIS_URL format and token.")
        return False
    
    print(f"🔍 Testing Redis URL: {redis_url[:20]}...")
    
    try:
        # Test connection
        client = redis.from_url(redis_url)
        
        # Test ping
        response = client.ping()
        if response:
            print("✅ Redis connection successful!")
            print(f"🔗 Connected to: {redis_url}")
            
            # Test basic operations
            test_key = "test:connection"
            test_value = "Hello SAIGE!"
            
            client.set(test_key, test_value)
            retrieved = client.get(test_key)
            client.delete(test_key)
            
            if retrieved == test_value.encode():
                print("✅ Redis read/write operations successful!")
                return True
            else:
                print("⚠️  Redis operations failed")
                return False
                
        else:
            print("❌ Redis ping failed")
            return False
            
    except redis.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_redis_connection()
    if success:
        print("\n🎉 Redis is ready for SAIGE!")
    else:
        print("\n💡 Check your Redis configuration:")
        print("   - REDIS_URL environment variable")
        print("   - Redis server status")
        print("   - Network connectivity")
