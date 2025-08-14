#!/usr/bin/env python3
"""
JAIMES AI Executive - Configuration Management
Handles all configuration settings using Pydantic for robust validation.
"""

import re
from typing import Optional, List, Dict
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
    vapi_api_key: SecretStr
    vapi_assistant_id: Optional[str] = None
    shopware_api_key: Optional[SecretStr] = None
    groq_api_key: SecretStr
    groq_model: str
    vehicle_db_api_key: Optional[SecretStr] = None
    license_plate_api_key: Optional[SecretStr] = None
    
    # --- Security Settings ---
    max_requests_per_minute: int = 60
    max_conversation_length: int = 50
    request_timeout_seconds: int = 30

    # --- IN AND OUT OF SCOPE SERVICES LISTS ---
    IN_SCOPE_SERVICES: List[str] = [
        "oil change",
        "tire rotation",
        "brakes",
        "alignment",
        "engine diagnostic",
        "check engine light",
        "transmission",
        "squealing",
        "grinding",
        "leaking",
    ]
    OUT_OF_SCOPE_SERVICES: List[str] = [
        "body work",
        "paint",
        "dent repair",
        "collision",
        "detailing",
        "car wash",
        "upholstery",
        "window tinting",
    ]
    # --- External URLs ---
    redis_url: str
    discord_webhook_url: Optional[str] = (
        None  # Make this optional if you don't want local Discord alerts
    )
    shopware_store_url: Optional[str] = None  # Or =""
    license_plate_api_url: Optional[str] = None  # Or =""

    # --- Application Settings ---
    milex_location_id: str = "durham"
    debug: bool = False
    log_level: str = "INFO"
    shop_zip_code: str = Field("27701", pattern=r"^\d{5}$")

    # Pydantic v2 model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # <--- THIS IS THE FIX. Ensures it finds 'ENVIRONMENT'.
        extra="ignore",  # <--- ADD THIS LINE to ignore unknown fields
    )

    # Pydantic v2 field validator
    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Ensures the Redis URL has a valid scheme."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Invalid Redis URL: Must start with redis:// or rediss://")
        return v


# Create a single, global instance of the configuration that the rest of the app can import
config = Config()
