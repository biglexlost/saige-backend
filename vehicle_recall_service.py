#!/usr/bin/env python3
"""
Vehicle Recall Service
Provides VIN-based recall lookup capabilities for proactive customer service,
using Redis for scalable, persistent caching.
"""

import asyncio
import aiohttp
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

# It's recommended to install redis with: pip install redis
try:
    import redis
except ImportError:
    print("Redis library not found. Please install it with: pip install redis")
    redis = None

logger = logging.getLogger(__name__)


class RecallSeverity(Enum):
    """Recall severity levels"""

    CRITICAL = "critical"
    IMPORTANT = "important"
    MODERATE = "moderate"


@dataclass
class RecallInfo:
    """Vehicle recall information"""

    nhtsa_campaign_id: str
    component: str
    summary: str
    consequence: str
    remedy: str
    recall_date: str  # Stored as ISO format string
    severity: RecallSeverity


@dataclass
class VehicleRecallSummary:
    """Summary of all recalls for a vehicle"""

    vin: str
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    total_recalls: int
    open_recalls: int
    critical_recalls: int
    last_checked: str  # Stored as ISO format string
    recalls: List[RecallInfo]


class VehicleRecallService:
    """Service for VIN-based vehicle recall lookup"""

    def __init__(self, redis_url: str):
        """
        Initializes the recall service with a Redis connection.

        Args:
            redis_url: The connection URL for the Redis server.
        """
        if not redis:
            raise ImportError("Redis library is required but not installed.")

        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.session: Optional[aiohttp.ClientSession] = None
        self.nhtsa_base_url = "https://api.nhtsa.gov/recalls/recallsByVehicle"
        self.cache_validity_seconds = timedelta(days=7).total_seconds()
        logger.info("Vehicle Recall Service initialized with Redis cache.")

    async def __aenter__(self):
        """Async context manager to create the HTTP session."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager to close the HTTP session."""
        if self.session:
            await self.session.close()

    def _hash_vin(self, vin: str) -> str:
        """Create a hash of the VIN for privacy."""
        return hashlib.sha256(vin.encode()).hexdigest()

    def _validate_vin(self, vin: str) -> bool:
        """Validate VIN format."""
        if not vin or len(vin) != 17 or re.search(r"[IOQ]", vin.upper()):
            return False
        return True

    async def get_recalls_by_vin(
        self, vin: str, force_refresh: bool = False
    ) -> Optional[VehicleRecallSummary]:
        """Get recall information for a specific VIN, using Redis cache first."""
        if not self._validate_vin(vin):
            logger.warning(f"Invalid VIN format provided: {vin}")
            return None

        vin = vin.upper().strip()
        vin_hash = self._hash_vin(vin)
        cache_key = f"recall:{vin_hash}"

        if not force_refresh:
            cached_data = self._get_cached_recalls(cache_key)
            if cached_data:
                logger.info(
                    f"Returning cached recall data for VIN ending in {vin[-4:]}"
                )
                return cached_data

        recall_summary = await self._fetch_recalls_from_nhtsa(vin)
        if recall_summary:
            self._cache_recall_data(cache_key, recall_summary)
            logger.info(
                f"Retrieved {recall_summary.total_recalls} recalls for VIN ending in {vin[-4:]}"
            )
        return recall_summary

    def _get_cached_recalls(self, cache_key: str) -> Optional[VehicleRecallSummary]:
        """Get cached recall data from Redis if it's still valid."""
        try:
            cached_json = self.redis_client.get(cache_key)
            if cached_json:
                data = json.loads(cached_json)
                # Reconstruct dataclasses from dictionaries
                data["recalls"] = [RecallInfo(**r) for r in data["recalls"]]
                return VehicleRecallSummary(**data)
        except Exception as e:
            logger.error(f"Error getting cached recalls from Redis: {e}")
        return None

    async def _fetch_recalls_from_nhtsa(
        self, vin: str
    ) -> Optional[VehicleRecallSummary]:
        """Fetch recall data from the NHTSA API."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        url = f"{self.nhtsa_base_url}?vin={vin}&format=json"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_nhtsa_response(vin, data)
                else:
                    logger.error(
                        f"NHTSA API request failed with status {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Error fetching recalls from NHTSA: {str(e)}")
            return None

    def _parse_nhtsa_response(
        self, vin: str, data: Dict[str, Any]
    ) -> VehicleRecallSummary:
        """Parse the NHTSA API response into our structured format."""
        results = data.get("Results", [])
        recalls = []
        vehicle_info = {"year": 0, "make": "Unknown", "model": "Unknown"}

        if results:
            first_result = results[0]
            vehicle_info["year"] = int(first_result.get("ModelYear", 0))
            vehicle_info["make"] = first_result.get("Make", "Unknown")
            vehicle_info["model"] = first_result.get("Model", "Unknown")

        for result in results:
            consequence = result.get(
                "Conequence", ""
            ).lower()  # Typo in API is 'Conequence'
            severity = self._determine_recall_severity(consequence)
            recalls.append(
                RecallInfo(
                    nhtsa_campaign_id=result.get("NHTSACampaignNumber", ""),
                    component=result.get("Component", ""),
                    summary=result.get("Summary", ""),
                    consequence=result.get("Conequence", ""),
                    remedy=result.get("Remedy", ""),
                    recall_date=result.get("ReportReceivedDate", ""),
                    severity=severity,
                )
            )

        return VehicleRecallSummary(
            vin=vin,
            vehicle_year=vehicle_info["year"],
            vehicle_make=vehicle_info["make"],
            vehicle_model=vehicle_info["model"],
            total_recalls=len(recalls),
            open_recalls=len(recalls),  # NHTSA VIN search only returns open recalls
            critical_recalls=len(
                [r for r in recalls if r.severity == RecallSeverity.CRITICAL]
            ),
            last_checked=datetime.now().isoformat(),
            recalls=recalls,
        )

    def _determine_recall_severity(self, consequence: str) -> RecallSeverity:
        """Determine recall severity based on consequence description."""
        consequence_lower = consequence.lower()
        critical_keywords = [
            "death",
            "fire",
            "crash",
            "brake failure",
            "steering failure",
            "airbag",
        ]
        if any(keyword in consequence_lower for keyword in critical_keywords):
            return RecallSeverity.CRITICAL
        return RecallSeverity.IMPORTANT

    def _cache_recall_data(self, cache_key: str, recall_summary: VehicleRecallSummary):
        """Cache recall data to Redis."""
        try:
            # Use asdict to convert the nested dataclasses to dictionaries for JSON
            recall_data_json = json.dumps(asdict(recall_summary), default=str)
            self.redis_client.set(
                cache_key, recall_data_json, ex=int(self.cache_validity_seconds)
            )
        except Exception as e:
            logger.error(f"Error caching recall data to Redis: {e}")

    def format_recall_summary_for_conversation(
        self, recall_summary: VehicleRecallSummary
    ) -> str:
        """Format recall information for conversational presentation."""
        if recall_summary.total_recalls == 0:
            return f"Great news! I checked for recalls on your {recall_summary.vehicle_year} {recall_summary.vehicle_make} and found no open recalls."

        response = f"I found {recall_summary.total_recalls} recall{'s' if recall_summary.total_recalls != 1 else ''} for your vehicle.\n"

        critical_recalls = [
            r for r in recall_summary.recalls if r.severity == RecallSeverity.CRITICAL
        ]
        if critical_recalls:
            response += "🚨 **CRITICAL SAFETY RECALLS:**\n"
            for recall in critical_recalls[:2]:
                response += f"• **{recall.component}** - {recall.summary[:100]}...\n"

        response += "🔧 We can handle these recall repairs for you, and most are covered by the manufacturer at no cost. Would you like to schedule an appointment to address these?"
        return response


# Example usage and testing
async def test_recall_service():
    """Test the vehicle recall service"""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("🛑 Skipping test: Please set the REDIS_URL environment variable.")
        return

    async with VehicleRecallService(redis_url) as service:
        print("Testing Vehicle Recall Service:")
        print("=" * 50)
        test_vin = "5YJSA1E26F"  # Example VIN, replace if needed for a real test

        print(f"\nTesting VIN: {test_vin}")
        if service._validate_vin(test_vin):
            print("✅ VIN format is valid")
            summary = await service.get_recalls_by_vin(test_vin)
            if summary:
                print(f"Found {summary.total_recalls} recalls.")
                print(
                    f"Formatted for conversation:\n{service.format_recall_summary_for_conversation(summary)}"
                )
                # Test caching
                cached_summary = await service.get_recalls_by_vin(test_vin)
                if cached_summary:
                    print(
                        "\n✓ Successfully retrieved recall data from cache on second attempt."
                    )
        else:
            print("❌ Invalid VIN format")


if __name__ == "__main__":
    # For local testing, ensure you have a .env file with REDIS_URL
    # from dotenv import load_dotenv
    # load_dotenv()
    asyncio.run(test_recall_service())
