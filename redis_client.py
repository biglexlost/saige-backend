# file src/redis_client.py

import os
import redis
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the Redis client from the URL
redis_client = redis.from_url(os.getenv("UPSTASH_REDIS_REST_URL"))

# --- The Key Prefixing Strategy ---
SAIGE_PREFIX = "saige:"

# Helper function to automatically add the prefix
def prefix_key(key: str) -> str:
    return f"{SAIGE_PREFIX}{key}"

# --- How to use it in your app ---

def save_user_data(user_id: str, data: dict):
    key = prefix_key(f"user:{user_id}")  # Creates 'saige:user:123'
    print(f"SAVING to key: {key}")
    # Use the client to set the data. Store as a JSON string.
    redis_client.set(key, json.dumps(data))

def get_user_data(user_id: str) -> dict | None:
    key = prefix_key(f"user:{user_id}")  # Creates 'saige:user:123'
    print(f"GETTING from key: {key}")
    data = redis_client.get(key)
    return json.loads(data) if data else None

# Example Usage:
if __name__ == "__main__":
    save_user_data("456", {"name": "Casey", "status": "active"})
    user = get_user_data("456")
    print(f"Retrieved user: {user}")