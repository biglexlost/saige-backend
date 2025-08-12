#!/usr/bin/env python3
"""
License Plate Lookup Integration Design for JAIMES
==================================================

This module provides the design and implementation for integrating license plate
lookup capabilities into the JAIMES AI Executive system, capturing rich vehicle
data to enhance diagnostic and quoting accuracy.
"""

import asyncio
import aiohttp
import json
import sqlite3
import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Data Models ---


@dataclass
class LicensePlateRequest:
    """License plate lookup request data"""

    plate_number: str
    state: str
    zip_code: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def cache_key(self) -> str:
        """Generate a unique cache key for this request."""
        return hashlib.md5(f"{self.plate_number}_{self.state}".encode()).hexdigest()


@dataclass
class VehicleInfo:
    """
    Rich vehicle information structure, populated from the PlateToVIN API.
    """

    # Core Vehicle Info
    vin: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    body_type: Optional[str] = None

    # Engine & Drivetrain Details
    engine_displacement: Optional[float] = None
    drivetrain: Optional[str] = None
    transmission: Optional[str] = None
    fuel_type: Optional[str] = None
    horsepower: Optional[int] = None
    mpg_city: Optional[int] = None
    mpg_highway: Optional[int] = None

    # JAIMES-specific fields
    zip_code: Optional[str] = None
    api_provider: Optional[str] = None
    api_cost: Optional[float] = None
    lookup_timestamp: datetime = field(default_factory=datetime.now)
    cache_expiry: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(days=30)
    )

    def display_name(self) -> str:
        """Generate a human-readable vehicle name."""
        parts = [
            str(self.year) if self.year else None,
            self.make,
            self.model,
            self.trim,
        ]
        return " ".join(filter(None, parts))


@dataclass
class LicensePlateResponse:
    """Response from a license plate lookup operation."""

    success: bool
    vehicle_info: Optional[VehicleInfo] = None
    error_message: Optional[str] = None
    cached: bool = False
    fallback_required: bool = False


# --- Caching Layer ---


class LicensePlateLookupCache:
    """SQLite-based cache for license plate lookup results."""

    def __init__(self, db_path: str = "license_plate_cache.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the cache database and table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS license_plate_cache (
                    cache_key TEXT PRIMARY KEY, plate_number TEXT NOT NULL,
                    state TEXT NOT NULL, vehicle_data TEXT NOT NULL,
                    api_provider TEXT, lookup_timestamp TEXT NOT NULL,
                    cache_expiry TEXT NOT NULL
                )
            """
            )

    def get_cached_result(self, request: LicensePlateRequest) -> Optional[VehicleInfo]:
        """Retrieve cached vehicle info if it's available and not expired."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT vehicle_data FROM license_plate_cache WHERE cache_key = ? AND cache_expiry > ?",
                (request.cache_key(), datetime.now().isoformat()),
            )
            result = cursor.fetchone()
            if result:
                logger.info(f"Cache hit for plate {request.plate_number}")
                return VehicleInfo(**json.loads(result[0]))
        return None

    def cache_result(self, request: LicensePlateRequest, vehicle_info: VehicleInfo):
        """Cache a successful vehicle lookup result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO license_plate_cache
                   (cache_key, plate_number, state, vehicle_data, api_provider, lookup_timestamp, cache_expiry)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.cache_key(),
                    request.plate_number,
                    request.state,
                    json.dumps(asdict(vehicle_info)),
                    vehicle_info.api_provider,
                    vehicle_info.lookup_timestamp.isoformat(),
                    vehicle_info.cache_expiry.isoformat(),
                ),
            )
        logger.info(f"Cached result for plate {request.plate_number}")


# --- API Client ---


class PlateToVINClient:
    """Client for the PlateToVIN API integration."""

    def __init__(self, api_key: str, base_url: str = "https://api.platetovin.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.cost_per_request = 0.05

    async def lookup_vehicle(
        self, request: LicensePlateRequest
    ) -> LicensePlateResponse:
        """Looks up vehicle information by license plate, parsing the rich data."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {"plate": request.plate_number, "state": request.state}
            timeout = aiohttp.ClientTimeout(total=10)  # 10-second timeout

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/v1/lookup", json=payload, headers=headers
                ) as response:
                    if response.status == 200:
                        data = (await response.json()).get("data", {})
                        engine_data = data.get("engine_drivetrain", {})
                        economy_data = data.get("economy", {})

                        vehicle_info = VehicleInfo(
                            vin=data.get("vin"),
                            year=int(data.get("year")) if data.get("year") else None,
                            make=data.get("make"),
                            model=data.get("model"),
                            trim=data.get("trim"),
                            body_type=data.get("body_type"),
                            engine_displacement=engine_data.get("engine_displacement"),
                            drivetrain=engine_data.get("drivetrain"),
                            transmission=engine_data.get("transmission"),
                            fuel_type=engine_data.get("fuel_type"),
                            horsepower=data.get("performance", {}).get("horsepower"),
                            mpg_city=economy_data.get("mpg_city"),
                            mpg_highway=economy_data.get("mpg_highway"),
                            zip_code=request.zip_code,
                            api_provider="platetovin",
                            api_cost=self.cost_per_request,
                        )
                        return LicensePlateResponse(
                            success=True, vehicle_info=vehicle_info
                        )
                    else:
                        error_data = await response.json()
                        return LicensePlateResponse(
                            success=False,
                            error_message=error_data.get(
                                "message", f"API error: {response.status}"
                            ),
                            fallback_required=True,
                        )
        except Exception as e:
            logger.error(f"PlateToVIN API error: {str(e)}")
            return LicensePlateResponse(
                success=False,
                error_message=f"API connection error: {str(e)}",
                fallback_required=True,
            )


# --- Main Manager ---


class LicensePlateLookupManager:
    """Main manager for license plate lookup operations."""

    def __init__(self, platetovin_api_key: str):
        self.cache = LicensePlateLookupCache()
        self.platetovin_client = PlateToVINClient(platetovin_api_key)

    async def lookup_vehicle_by_plate(
        self, plate_number: str, state: str, zip_code: Optional[str] = None
    ) -> LicensePlateResponse:
        """Main method to look up vehicle information, using the cache first."""
        plate_number = plate_number.strip().upper()
        state = state.strip().upper()
        if not plate_number or not state:
            return LicensePlateResponse(
                success=False,
                error_message="License plate and state are required",
                fallback_required=True,
            )

        request = LicensePlateRequest(
            plate_number=plate_number, state=state, zip_code=zip_code
        )

        cached_vehicle = self.cache.get_cached_result(request)
        if cached_vehicle:
            if zip_code:
                cached_vehicle.zip_code = zip_code
            return LicensePlateResponse(
                success=True, vehicle_info=cached_vehicle, cached=True
            )

        response = await self.platetovin_client.lookup_vehicle(request)

        if response.success and response.vehicle_info:
            self.cache.cache_result(request, response.vehicle_info)

        return response


# --- Example Usage ---


async def test_license_plate_integration():
    """Test the license plate integration system."""
    api_key = os.getenv("PLATETOVIN_API_KEY")
    if not api_key:
        print(
            "🛑 Skipping test: Please set the PLATETOVIN_API_KEY environment variable."
        )
        return

    lookup_manager = LicensePlateLookupManager(api_key)

    print("Testing license plate lookup for 'ABC123' in 'NC'...")
    response = await lookup_manager.lookup_vehicle_by_plate("ABC123", "NC", "27701")

    if response.success and response.vehicle_info:
        vehicle = response.vehicle_info
        print(f"✅ Success! Found: {vehicle.display_name()}")
        print(f"   VIN: {vehicle.vin}")
        print(f"   Engine Displacement: {vehicle.engine_displacement}L")
        print(f"   Drivetrain: {vehicle.drivetrain}")
        print(f"   Cached: {response.cached}")
    else:
        print(f"❌ Lookup failed: {response.error_message}")


if __name__ == "__main__":
    asyncio.run(test_license_plate_integration())
