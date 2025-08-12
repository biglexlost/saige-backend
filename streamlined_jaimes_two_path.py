#!/usr/bin/streamlined_jaimes_two_path.py
"""
Streamlined JAIMES Two-Path Vehicle Collection System
===================================================

This module provides the streamlined two-path approach for vehicle information collection:
Path A: License plate + ZIP code (automatic lookup)
Path B: Manual collection (year, make, model, etc.)

Author: JAIMES Development Team
Date: December 7, 2025
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Set up logging
logger = logging.getLogger(__name__)


class VehicleCollectionPath(Enum):
    """Vehicle information collection paths"""

    LICENSE_PLATE = "license_plate"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass
class VehicleInfo:
    """Vehicle information container"""

    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    mileage: Optional[int] = None
    collection_path: VehicleCollectionPath = VehicleCollectionPath.UNKNOWN
    confidence_score: float = 0.0

    @property
    def description(self) -> str:
        """Get vehicle description"""
        if self.year and self.make and self.model:
            return f"{self.year} {self.make} {self.model}"
        return "Unknown Vehicle"

    @property
    def is_complete(self) -> bool:
        """Check if vehicle info is complete enough for processing"""
        return bool(self.year and self.make and self.model)


class StreamlinedJAIMESSystem:
    """
    Streamlined JAIMES system with two-path vehicle collection
    """

    def __init__(
        self,
        license_plate_client=None,
        vehicle_database_client=None,
        testing_mode: bool = False,
    ):
        """
        Initialize the streamlined JAIMES system
        """
        self.license_plate_client = license_plate_client
        self.vehicle_database_client = vehicle_database_client
        self.testing_mode = testing_mode
        self.logger = logging.getLogger(__name__)

        # Mock license plate data for testing
        self.mock_license_plates = {
            "ABC123": {
                "license_plate": "ABC123",
                "state": "NC",
                "vin": "1HGBH41JXMN109186",
                "year": 2019,
                "make": "Honda",
                "model": "Civic",
                "confidence": 0.95,
            },
            "XYZ789": {
                "license_plate": "XYZ789",
                "state": "NC",
                "vin": "4T1BF1FK5CU123456",
                "year": 2020,
                "make": "Toyota",
                "model": "Camry",
                "confidence": 0.92,
            },
        }

    async def collect_vehicle_info_path_a(
        self, license_plate: str, zip_code: str
    ) -> VehicleInfo:
        """Path A: Collect vehicle info via license plate lookup"""
        try:
            normalized_plate = self._normalize_license_plate(license_plate)
            if self.testing_mode:
                return await self._mock_license_plate_lookup(normalized_plate, zip_code)
            else:
                return await self._real_license_plate_lookup(normalized_plate, zip_code)
        except Exception as e:
            self.logger.error(f"Error in Path A vehicle collection: {e}")
            return VehicleInfo(
                license_plate=license_plate,
                zip_code=zip_code,
                collection_path=VehicleCollectionPath.LICENSE_PLATE,
                confidence_score=0.0,
            )

    async def collect_vehicle_info_path_b(
        self, conversation_data: Dict[str, Any]
    ) -> VehicleInfo:
        """Path B: Collect vehicle info via manual conversation"""
        try:
            vehicle_info = VehicleInfo(collection_path=VehicleCollectionPath.MANUAL)
            vehicle_info.year = self._validate_year(conversation_data.get("year"))
            vehicle_info.make = self._validate_make(conversation_data.get("make"))
            vehicle_info.model = self._validate_model(conversation_data.get("model"))
            vehicle_info.mileage = self._validate_mileage(
                conversation_data.get("mileage")
            )
            vehicle_info.zip_code = conversation_data.get("zip_code")
            vehicle_info.confidence_score = self._calculate_manual_confidence(
                vehicle_info
            )
            return vehicle_info
        except Exception as e:
            self.logger.error(f"Error in Path B vehicle collection: {e}")
            return VehicleInfo(
                collection_path=VehicleCollectionPath.MANUAL, confidence_score=0.0
            )

    async def determine_collection_path(self, user_input: str) -> VehicleCollectionPath:
        """Determine which collection path to use based on user input"""
        if self._looks_like_license_plate(user_input):
            return VehicleCollectionPath.LICENSE_PLATE
        if self._contains_vehicle_details(user_input):
            return VehicleCollectionPath.MANUAL
        return VehicleCollectionPath.UNKNOWN

    def generate_path_selection_prompt(self) -> str:
        """Generate prompt for path selection"""
        return (
            "I can look up your vehicle instantly with your license plate and ZIP code, "
            "or I can ask a few quick questions. Which would you prefer?"
        )

    def _normalize_license_plate(self, license_plate: str) -> str:
        """Normalize license plate format"""
        return re.sub(r"\s+", "", license_plate.upper())

    def _looks_like_license_plate(self, text: str) -> bool:
        """Check if text looks like a license plate"""
        cleaned = re.sub(r"\s+", "", text.upper())
        return bool(re.match(r"^[A-Z0-9]{3,8}$", cleaned))

    def _contains_vehicle_details(self, text: str) -> bool:
        """Check if text contains vehicle details"""
        text_lower = text.lower()
        has_year = bool(re.search(r"\b(19|20)\d{2}\b", text_lower))
        makes = ["honda", "toyota", "ford", "chevrolet", "nissan", "bmw", "mercedes"]
        has_make = any(make in text_lower for make in makes)
        return has_year or has_make

    def _validate_year(self, year_input: Any) -> Optional[int]:
        """Validate and convert year input"""
        try:
            year = int(year_input)
            current_year = datetime.now().year
            if 0 <= year <= 99:
                year += 2000 if year <= (current_year % 100) + 1 else 1900
            if 1950 <= year <= current_year + 1:
                return year
        except (ValueError, TypeError):
            pass
        return None

    def _validate_make(self, make_input: Any) -> Optional[str]:
        """Validate and normalize make input"""
        if isinstance(make_input, str) and len(make_input.strip()) >= 2:
            return make_input.strip().title()
        return None

    def _validate_model(self, model_input: Any) -> Optional[str]:
        """Validate and normalize model input"""
        if isinstance(model_input, str) and len(model_input.strip()) >= 1:
            return model_input.strip().title()
        return None

    def _validate_mileage(self, mileage_input: Any) -> Optional[int]:
        """Validate mileage input"""
        try:
            mileage = int(re.sub(r"[,\s]", "", str(mileage_input)))
            if 0 <= mileage <= 500000:
                return mileage
        except (ValueError, TypeError):
            pass
        return None

    def _calculate_manual_confidence(self, vehicle_info: VehicleInfo) -> float:
        """Calculate confidence score for manually collected data"""
        score = 0.0
        if vehicle_info.year:
            score += 0.3
        if vehicle_info.make:
            score += 0.3
        if vehicle_info.model:
            score += 0.3
        if vehicle_info.vin:
            score += 0.1
        return min(score, 1.0)

    async def _mock_license_plate_lookup(
        self, license_plate: str, zip_code: str
    ) -> VehicleInfo:
        """Mock license plate lookup for testing"""
        await asyncio.sleep(0.2)
        if license_plate in self.mock_license_plates:
            data = self.mock_license_plates[license_plate]
            return VehicleInfo(
                year=data["year"],
                make=data["make"],
                model=data["model"],
                vin=data["vin"],
                license_plate=license_plate,
                state=data["state"],
                zip_code=zip_code,
                collection_path=VehicleCollectionPath.LICENSE_PLATE,
                confidence_score=data["confidence"],
            )
        return VehicleInfo(
            license_plate=license_plate,
            zip_code=zip_code,
            collection_path=VehicleCollectionPath.LICENSE_PLATE,
            confidence_score=0.0,
        )

    async def _real_license_plate_lookup(
        self, license_plate: str, zip_code: str
    ) -> VehicleInfo:
        """Real license plate lookup using API client"""
        # This is where you would call your actual API client, e.g., the LicensePlateLookupManager
        if not self.license_plate_client:
            return VehicleInfo(
                license_plate=license_plate,
                collection_path=VehicleCollectionPath.LICENSE_PLATE,
                confidence_score=0.0,
            )

        response = await self.license_plate_client.lookup_vehicle_by_plate(
            license_plate, "NC", zip_code
        )
        if response.success:
            return response.vehicle_info
        return VehicleInfo(
            license_plate=license_plate,
            collection_path=VehicleCollectionPath.LICENSE_PLATE,
            confidence_score=0.0,
        )


# Example usage and testing
if __name__ == "__main__":

    async def test_streamlined_jaimes():
        """Test the streamlined JAIMES system"""
        system = StreamlinedJAIMESSystem(testing_mode=True)

        print("Testing Path A (License Plate)...")
        vehicle_info_a = await system.collect_vehicle_info_path_a("ABC123", "27701")
        print(f"Path A Result: {asdict(vehicle_info_a)}")

        print("\nTesting Path B (Manual)...")
        conversation_data = {"year": "2019", "make": "Honda", "model": "Civic"}
        vehicle_info_b = await system.collect_vehicle_info_path_b(conversation_data)
        print(f"Path B Result: {asdict(vehicle_info_b)}")

        print("\nTesting Path Determination...")
        path = await system.determine_collection_path("My license is ABC123")
        print(f"Input 'My license is ABC123' -> Path: {path.value}")

    asyncio.run(test_streamlined_jaimes())
