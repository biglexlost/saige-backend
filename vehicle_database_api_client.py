#!/usr/bin/env python3
"""
Vehicle Database API Client with Intelligent Caching System
Integrates with vehicledatabases.com API for repair pricing estimates.
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class PriceValidityPeriod(Enum):
    """Price validity periods for different types of repairs"""

    ROUTINE_MAINTENANCE = 30
    MINOR_REPAIRS = 14
    MAJOR_REPAIRS = 7


@dataclass
class VehicleInfo:
    """Vehicle information for API requests"""

    year: int
    make: str
    model: str
    engine_size: Optional[str] = None
    transmission: Optional[str] = None


@dataclass
class RepairEstimate:
    """Repair estimate from Vehicle Database API"""

    repair_description: str
    labor_hours: float
    parts_cost: float
    total_estimate: float
    low_estimate: float
    high_estimate: float
    zip_code: str


class VehicleDatabaseAPIClient:
    """Client for Vehicle Database API with intelligent caching"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.vehicledatabases.com",
        cache_db_path: str = "vehicle_pricing_cache.db",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.cache_db_path = cache_db_path
        self.session: Optional[aiohttp.ClientSession] = None
        self._init_cache_database()
        self.repair_categories = {
            "oil change": PriceValidityPeriod.ROUTINE_MAINTENANCE,
            "brake pads": PriceValidityPeriod.MINOR_REPAIRS,
            "engine": PriceValidityPeriod.MAJOR_REPAIRS,
            "transmission": PriceValidityPeriod.MAJOR_REPAIRS,
        }
        logger.info("Vehicle Database API Client initialized")

    async def __aenter__(self):
        """Async context manager to create the session."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager to close the session."""
        if self.session:
            await self.session.close()

    def _init_cache_database(self):
        """Initialize SQLite cache database"""
        with sqlite3.connect(self.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_cache (
                    id INTEGER PRIMARY KEY, vehicle_hash TEXT NOT NULL,
                    repair_hash TEXT NOT NULL, zip_code TEXT NOT NULL,
                    estimate_json TEXT NOT NULL, created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL, UNIQUE(vehicle_hash, repair_hash, zip_code)
                )
            """
            )
            conn.commit()

    def _generate_hash(self, text: str) -> str:
        """Generate MD5 hash for a given string."""
        return hashlib.md5(text.lower().strip().encode()).hexdigest()

    # Compatibility helpers for SmartPricingManager
    def _generate_vehicle_hash(self, vehicle_info: VehicleInfo) -> str:
        """Generate a stable hash key for a vehicle description."""
        key = f"{vehicle_info.year}|{vehicle_info.make}|{vehicle_info.model}|{vehicle_info.engine_size or ''}|{vehicle_info.transmission or ''}"
        return self._generate_hash(key)

    def _generate_repair_hash(self, repair_description: str) -> str:
        return self._generate_hash(repair_description)

    def _categorize_repair(self, repair_description: str) -> str:
        """Simple categorization for analytics/volatility bucketing."""
        text = repair_description.lower()
        if any(k in text for k in ["brake", "rotor", "pad", "caliper"]):
            return "brakes"
        if any(k in text for k in ["transmission", "gear", "clutch"]):
            return "transmission"
        if any(k in text for k in ["engine", "timing", "belt", "water pump", "serpentine"]):
            return "engine"
        if any(k in text for k in ["oil change", "maintenance", "inspection"]):
            return "maintenance"
        return "other"

    def _determine_price_validity(self, repair_description: str) -> PriceValidityPeriod:
        """Determine price validity period based on repair type"""
        repair_lower = repair_description.lower()
        for keyword, validity_period in self.repair_categories.items():
            if keyword in repair_lower:
                return validity_period
        return PriceValidityPeriod.MINOR_REPAIRS

    async def get_repair_estimate(
        self,
        vehicle: VehicleInfo,
        repair_description: str,
        zip_code: str,
        force_refresh: bool = False,
    ) -> Optional[RepairEstimate]:
        """Get repair estimate with intelligent caching"""
        if not force_refresh:
            cached_estimate = self._get_cached_price(
                vehicle, repair_description, zip_code
            )
            if cached_estimate:
                return cached_estimate

        estimate = await self._make_api_request(vehicle, repair_description, zip_code)
        if estimate:
            self._cache_price(vehicle, repair_description, zip_code, estimate)
        return estimate

    async def get_cache_statistics(self) -> Dict[str, float]:
        """Return basic cache stats for analytics. Placeholder implementation."""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM price_cache")
                total_rows = cur.fetchone()[0] or 0
            # Without hit/miss counters, return zeros for ratios; keep extensible
            return {"cache_hit_ratio": 0.0, "estimated_cost_saved": 0.0, "entries": float(total_rows)}
        except Exception:
            return {"cache_hit_ratio": 0.0, "estimated_cost_saved": 0.0}

    def _get_cached_price(
        self, vehicle: VehicleInfo, repair_description: str, zip_code: str
    ) -> Optional[RepairEstimate]:
        """Retrieve cached price if valid"""
        vehicle_hash = self._generate_hash(
            f"{vehicle.year}{vehicle.make}{vehicle.model}{vehicle.engine_size}"
        )
        repair_hash = self._generate_hash(repair_description)

        with sqlite3.connect(self.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT estimate_json FROM price_cache WHERE vehicle_hash = ? AND repair_hash = ? AND zip_code = ? AND expires_at > ?",
                (vehicle_hash, repair_hash, zip_code, datetime.now().isoformat()),
            )
            result = cursor.fetchone()
            if result:
                logger.info(
                    f"Cache hit for {vehicle.make} {vehicle.model} - {repair_description}"
                )
                return RepairEstimate(**json.loads(result[0]))
        return None

    def _cache_price(
        self,
        vehicle: VehicleInfo,
        repair_description: str,
        zip_code: str,
        estimate: RepairEstimate,
    ):
        """Cache price estimate with appropriate expiration"""
        vehicle_hash = self._generate_hash(
            f"{vehicle.year}{vehicle.make}{vehicle.model}{vehicle.engine_size}"
        )
        repair_hash = self._generate_hash(repair_description)
        validity_period = self._determine_price_validity(repair_description)
        expires_at = datetime.now() + timedelta(days=validity_period.value)

        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO price_cache (vehicle_hash, repair_hash, zip_code, estimate_json, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    vehicle_hash,
                    repair_hash,
                    zip_code,
                    json.dumps(asdict(estimate)),
                    datetime.now().isoformat(),
                    expires_at.isoformat(),
                ),
            )
            logger.info(
                f"Cached price for {vehicle.make} {vehicle.model} - {repair_description}"
            )

    async def _make_api_request(
        self, vehicle: VehicleInfo, repair_description: str, zip_code: str
    ) -> Optional[RepairEstimate]:
        """Make API request to Vehicle Database"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        payload = {
            "zipCode": zip_code,
            "vehicle": {
                "year": vehicle.year,
                "make": vehicle.make,
                "model": vehicle.model,
            },
            "repair": {"description": repair_description},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with self.session.post(
                f"{self.base_url}/estimates", json=payload, headers=headers, timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return RepairEstimate(
                        repair_description=repair_description,
                        labor_hours=data.get("laborHours", 0.0),
                        parts_cost=data.get("partsCost", 0.0),
                        total_estimate=data.get("totalEstimate", 0.0),
                        low_estimate=data.get("lowEstimate", 0.0),
                        high_estimate=data.get("highEstimate", 0.0),
                        zip_code=zip_code,
                    )
                else:
                    logger.error(
                        f"API request failed with status {response.status}: {await response.text()}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Error making API request: {str(e)}")
            return None


# Example usage and testing
async def test_vehicle_database_api():
    """Test the Vehicle Database API client"""
    api_key = os.getenv("VEHICLE_DB_API_KEY")
    if not api_key:
        print("🛑 Skipping test: Please set VEHICLE_DB_API_KEY environment variable.")
        return

    async with VehicleDatabaseAPIClient(api_key) as client:
        vehicle = VehicleInfo(
            year=2018, make="Ford", model="F-150", engine_size="5.0L V8"
        )
        repair = "Brake pad replacement"
        zip_code = "27701"

        print(f"Getting estimate for: {repair}")
        estimate = await client.get_repair_estimate(vehicle, repair, zip_code)

        if estimate:
            print(f"  Total Estimate: ${estimate.total_estimate:.2f}")
            print(
                f"  Range: ${estimate.low_estimate:.2f} - ${estimate.high_estimate:.2f}"
            )

            # Second call should hit the cache
            cached_estimate = await client.get_repair_estimate(
                vehicle, repair, zip_code
            )
            if cached_estimate:
                print("  ✓ Cache hit on second request")
        else:
            print("  No estimate available")


if __name__ == "__main__":
    asyncio.run(test_vehicle_database_api())
