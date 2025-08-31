# file src/redis_client.py

import os
import redis
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- The Key Prefixing Strategy ---
SAIGE_PREFIX = "saige:"

# Create Redis client lazily to avoid connection errors during import
def get_redis_client():
    """Get Redis client, creating connection only when needed."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("⚠️  REDIS_URL not found, Redis operations will fail")
        return None
    
    try:
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        print(f"❌ Failed to create Redis client: {e}")
        return None

# Helper function to automatically add the prefix
def prefix_key(key: str) -> str:
    return f"{SAIGE_PREFIX}{key}"

# --- How to use it in your app ---

def save_user_data(user_id: str, data: dict):
    key = prefix_key(f"user:{user_id}")  # Creates 'saige:user:123'
    print(f"SAVING to key: {key}")
    
    client = get_redis_client()
    if not client:
        print("❌ Cannot save data - Redis client not available")
        return False
    
    try:
        # Use the client to set the data. Store as a JSON string.
        client.set(key, json.dumps(data))
        return True
    except Exception as e:
        print(f"❌ Failed to save data: {e}")
        return False

def get_user_data(user_id: str) -> dict | None:
    key = prefix_key(f"user:{user_id}")  # Creates 'saige:user:123'
    print(f"GETTING from key: {key}")
    
    client = get_redis_client()
    if not client:
        print("❌ Cannot get data - Redis client not available")
        return None
    
    try:
        data = client.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        print(f"❌ Failed to get data: {e}")
        return None

# Example Usage:
if __name__ == "__main__":
    save_user_data("456", {"name": "Casey", "status": "active"})
    user = get_user_data("456")
    print(f"Retrieved user: {user}")