#!/usr/bin/env python3
"""
JAIMES AI Executive - Configuration Management
Handles all configuration settings using Pydantic for robust validation.
"""

import re
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, SecretStr


def validate_redis_url(redis_url: str) -> None:
    """Validates Redis URL format before initializing connection."""
    pattern = r"^(redis|rediss|unix)://"
    if not re.match(pattern, redis_url):
        raise ValueError(
            f"🚫 Invalid Redis URL: '{redis_url}'. "
            "Must start with redis://, rediss://, or unix://"
        )
    else:
        print(f"✅ Redis URL validated: {redis_url}")


class Config(BaseSettings):
    """
    Manages all application settings and secrets.
    Loads from environment variables and/or a .env file.
    """

    # --- Application Settings for GreetingsManager ---
    shop_name: str = "Your Med Spa"
    shop_location: str = "City"
    location_style: str = "standard"

    # --- Assistant Identity ---
    assistant_name: str = "SAIGE"
    assistant_title: str = "Spa AI Guest Executive"

    # --- Vertical / Domain ---
    vertical: str = "medspa"

    # --- Med-spa Service Catalog (JSON file; optional) ---
    service_catalog_path: Optional[str] = "medspa_services.json"

    # --- Booking Integration (pluggable adapter) ---
    booking_provider: str = "none"  # e.g., boulevard | mindbody | aesthetic_record | none
    booking_webhook_url: Optional[str] = None

    # --- Hours & Call Routing (defaults; per-client overrides later) ---
    business_hours: Dict[str, Dict[str, Optional[str]]] = {
        "mon_fri": {"open": "09:00", "close": "18:00", "tz": "America/New_York"},
        "sat": {"open": "10:00", "close": "16:00"},
        "sun": {"open": None, "close": None},
    }
    overflow_strategy: str = "answer_and_queue"  # or transfer | voicemail
    urgent_routing_number: Optional[str] = None

    # --- Compliance Defaults ---
    hipaa_mode: bool = True
    analytics_enabled: bool = False

    # The Environment Switch
    # It will use the OS environment variable 'ENVIRONMENT', or default to "DEV" if not set.
    environment: str = "DEV"

    # --- Secrets and External Service Keys ---
    vapi_api_key: SecretStr = Field(default="", description="VAPI API key for voice integration")
    vapi_assistant_id: Optional[str] = None
    groq_api_key: SecretStr = Field(default="", description="Groq API key for LLM integration")
    groq_model: str = Field(default="llama3-8b-8192", description="Groq model to use")
    
    # --- Security Settings ---
    max_requests_per_minute: int = 60
    max_conversation_length: int = 50
    request_timeout_seconds: int = 30

    # --- External URLs ---
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL with fallbacks for Upstash"
    )
    upstash_rest_token: Optional[str] = Field(
        default=None,
        description="Upstash Redis REST token for authentication"
    )
    discord_webhook_url: Optional[str] = (
        None  # Make this optional if you don't want local Discord alerts
    )

    # --- Application Settings ---
    debug: bool = False
    log_level: str = "INFO"
    shop_zip_code: str = Field(default="27701", pattern=r"^\d{5}$", description="Shop ZIP code")

    # Pydantic v2 model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # <--- THIS IS THE FIX. Ensures it finds 'ENVIRONMENT'.
        extra="ignore",  # <--- ADD THIS LINE to ignore unknown fields
    )

    # Pydantic v2 field validator
    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, v: Any) -> str:
        """Ensures the Redis URL has a valid scheme or is a valid Upstash REST URL."""
        if not v:
            # During deployment, allow empty redis_url to fall back to in-memory
            return "redis://localhost:6379"
        
        # Allow standard Redis URLs
        if v.startswith(("redis://", "rediss://")):
            return v
            
        # Allow Upstash REST URLs (https://...)
        if v.startswith("https://") and "upstash.io" in v:
            return v
            
        # Allow localhost fallback for development
        if v == "localhost" or v == "127.0.0.1":
            return "redis://localhost:6379"
            
        # If we get here, it's an invalid URL format
        raise ValueError(f"Invalid Redis URL: Must be redis://, rediss://, or valid Upstash REST URL. Got: {v}")


# Create a single, global instance of the configuration that the rest of the app can import
config = Config()

# Support Upstash env var names: if UPSTASH_REDIS_REST_URL is set, use it
import os as _os
upstash_rest_url = _os.getenv("UPSTASH_REDIS_REST_URL")
upstash_rest_token = _os.getenv("UPSTASH_REDIS_REST_TOKEN")

if upstash_rest_url and upstash_rest_token:
    # For Upstash REST, we need to construct a proper Redis-compatible URL
    # The actual Redis client will need to handle REST URLs differently
    try:
        # Store both URL and token for the Redis client to use
        object.__setattr__(config, "redis_url", upstash_rest_url)
        object.__setattr__(config, "upstash_rest_token", upstash_rest_token)
        print(f"Using Upstash REST URL: {upstash_rest_url}")
        print("Note: Upstash REST requires special Redis client handling")
    except Exception as e:
        print(f"Warning: Could not set Upstash REST config: {e}")
        pass
