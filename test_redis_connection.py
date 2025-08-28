#!/usr/bin/env python3
"""
Test Redis connection with current environment variables
"""
import os
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_redis_connection():
    """Test Redis connection with current config"""
    redis_url = os.getenv("REDIS_URL")
    
    if not redis_url:
        print("❌ REDIS_URL not found in environment")
        return False
    
    print(f"🔍 Testing Redis URL: {redis_url[:20]}...")
    
    try:
        # Test connection
        client = redis.from_url(redis_url)
        
        # Try to ping
        response = client.ping()
        print(f"✅ Redis connection successful! Ping response: {response}")
        
        # Test basic operations
        test_key = "saige:test:connection"
        client.set(test_key, "Hello SAIGE!")
        value = client.get(test_key)
        print(f"✅ Test write/read successful: {value}")
        
        # Clean up
        client.delete(test_key)
        print("✅ Test cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Redis Connection...")
    success = test_redis_connection()
    
    if success:
        print("\n🎉 Redis is working! The issue might be in the app configuration.")
    else:
        print("\n💡 Check your REDIS_URL format and token.")
