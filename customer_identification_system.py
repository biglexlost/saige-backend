"""
Customer Identification System for JAIMES AI Executive
=====================================================

This module handles customer identification and verification for returning customers.
It integrates with Shop-Ware to recognize customers by phone number and provides
fallback identification methods.

Author: JAIMES Development Team
Date: December 7, 2025
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging
import httpx

# Set up logging
logger = logging.getLogger(__name__)


class CustomerType(Enum):
    """Types of customers in the system"""

    NEW = "new"
    RETURNING = "returning"
    UNKNOWN = "unknown"


class VerificationStatus(Enum):
    """Status of customer verification"""

    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


@dataclass
class IdentificationResult:
    """Result of customer identification attempt"""

    customer_type: CustomerType
    verification_status: VerificationStatus
    customer_id: Optional[str] = None
    phone_number: Optional[str] = None
    name: Optional[str] = None
    confidence_score: float = 0.0
    identification_method: Optional[str] = None
    error_message: Optional[str] = None
    customer_data: Optional[Dict[str, Any]] = None  # Added for full customer data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "customer_type": self.customer_type.value,
            "verification_status": self.verification_status.value,
            "customer_id": self.customer_id,
            "phone_number": self.phone_number,
            "name": self.name,
            "confidence_score": self.confidence_score,
            "identification_method": self.identification_method,
            "error_message": self.error_message,
            "customer_data": self.customer_data,
        }


class ShopWareClient:
    """
    Shop-Ware API client for customer operations
    """

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def search_customers_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """Search customers by phone number"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/customers",
                    headers=self.headers,
                    params={"phone": phone},
                )
                response.raise_for_status()
                return response.json().get("data", [])
            except Exception as e:
                logger.error(f"Shop-Ware API error: {e}")
                return []

    async def search_customers_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Search customers by name"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/customers",
                    headers=self.headers,
                    params={"name": name},
                )
                response.raise_for_status()
                return response.json().get("data", [])
            except Exception as e:
                logger.error(f"Shop-Ware API error: {e}")
                return []

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by ID"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/customers/{customer_id}", headers=self.headers
                )
                response.raise_for_status()
                return response.json().get("data")
            except Exception as e:
                logger.error(f"Shop-Ware API error: {e}")
                return None


class CustomerIdentificationEngine:
    """
    Main engine for customer identification and verification
    """

    def __init__(
        self,
        shopware_client: Optional[ShopWareClient] = None,
        testing_mode: bool = False,
    ):
        """
        Initialize the customer identification engine

        Args:
            shopware_client: Shop-Ware API client for customer lookup
            testing_mode: If True, use mock data instead of real API calls
        """
        self.shopware_client = shopware_client
        self.testing_mode = testing_mode
        self.logger = logging.getLogger(__name__)

        # Mock customer data for testing
        self.mock_customers = {
            "(919) 555-0123": {
                "customer_id": "CUST_001",
                "name": "John Smith",
                "phone": "(919) 555-0123",
                "vehicles": [
                    {
                        "year": 2019,
                        "make": "Honda",
                        "model": "Civic",
                        "vin": "1HGBH41JXMN109186",
                        "mileage": 45000,
                    }
                ],
                "last_service": "2024-09-15",
                "service_history": [
                    {
                        "date": "2024-09-15",
                        "service": "Oil Change",
                        "mileage": 45000,
                        "cost": 89.99,
                    }
                ],
                "preferred_contact": "phone",
                "notes": "Prefers morning appointments",
            },
            "(919) 555-0456": {
                "customer_id": "CUST_002",
                "name": "Sarah Johnson",
                "phone": "(919) 555-0456",
                "vehicles": [
                    {
                        "year": 2020,
                        "make": "Toyota",
                        "model": "Camry",
                        "vin": "4T1BF1FK5CU123456",
                        "mileage": 32000,
                    }
                ],
                "last_service": "2024-10-20",
                "service_history": [
                    {
                        "date": "2024-10-20",
                        "service": "Brake Inspection",
                        "mileage": 32000,
                        "cost": 125.00,
                    }
                ],
                "preferred_contact": "text",
                "notes": "Has warranty until 2025",
            },
        }

    def get_customer_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get customer data by phone number (sync method for quick access)

        Args:
            phone_number: The customer's phone number

        Returns:
            Customer data dict or None if not found
        """
        normalized_phone = self._normalize_phone_number(phone_number)

        if self.testing_mode:
            return self.mock_customers.get(normalized_phone)

        # For production, this would need to be async or use a cache
        return None

    async def identify_customer_by_phone(
        self, phone_number: str
    ) -> IdentificationResult:
        """
        Identify customer by phone number

        Args:
            phone_number: Customer's phone number

        Returns:
            IdentificationResult with customer information
        """
        try:
            # Normalize phone number
            normalized_phone = self._normalize_phone_number(phone_number)

            if self.testing_mode:
                return await self._mock_phone_lookup(normalized_phone)
            else:
                return await self._shopware_phone_lookup(normalized_phone)

        except Exception as e:
            self.logger.error(f"Error identifying customer by phone: {e}")
            return IdentificationResult(
                customer_type=CustomerType.UNKNOWN,
                verification_status=VerificationStatus.FAILED,
                error_message=str(e),
            )

    async def identify_customer_by_name(
        self, name: str, phone_hint: Optional[str] = None
    ) -> IdentificationResult:
        """
        Identify customer by name (fallback method)

        Args:
            name: Customer's name
            phone_hint: Optional phone number to help disambiguate

        Returns:
            IdentificationResult with customer information
        """
        try:
            if self.testing_mode:
                return await self._mock_name_lookup(name, phone_hint)
            else:
                return await self._shopware_name_lookup(name)

        except Exception as e:
            self.logger.error(f"Error identifying customer by name: {e}")
            return IdentificationResult(
                customer_type=CustomerType.UNKNOWN,
                verification_status=VerificationStatus.FAILED,
                error_message=str(e),
            )

    async def verify_customer_identity(
        self, customer_id: str, verification_data: Dict[str, str]
    ) -> bool:
        """
        Verify customer identity with additional data points

        Args:
            customer_id: Customer ID to verify
            verification_data: Dict with verification fields (e.g., last_four_phone, zip_code, vehicle_year)

        Returns:
            True if verification passes, False otherwise
        """
        try:
            if self.testing_mode:
                # Mock verification logic
                for customer in self.mock_customers.values():
                    if customer["customer_id"] == customer_id:
                        # Check various verification points
                        if "last_four_phone" in verification_data:
                            phone_digits = re.sub(r"\D", "", customer["phone"])
                            if (
                                phone_digits[-4:]
                                != verification_data["last_four_phone"]
                            ):
                                return False

                        if "vehicle_year" in verification_data:
                            vehicle_years = [
                                str(v["year"]) for v in customer.get("vehicles", [])
                            ]
                            if verification_data["vehicle_year"] not in vehicle_years:
                                return False

                        return True
                return False
            else:
                # Real Shop-Ware verification
                if self.shopware_client:
                    customer = await self.shopware_client.get_customer(customer_id)
                    if customer:
                        # Implement verification logic based on Shop-Ware data structure
                        return True
                return False

        except Exception as e:
            self.logger.error(f"Error verifying customer identity: {e}")
            return False

    def _normalize_phone_number(self, phone: str) -> str:
        """
        Normalize phone number to consistent format

        Args:
            phone: Raw phone number string

        Returns:
            Normalized phone number
        """
        # Remove all non-digit characters
        digits = re.sub(r"\D", "", phone)

        # Handle different formats
        if len(digits) == 10:
            # Format as (XXX) XXX-XXXX
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == "1":
            # Remove leading 1 and format
            digits = digits[1:]
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        else:
            # Return as-is if can't normalize
            return phone

    async def _mock_phone_lookup(self, phone_number: str) -> IdentificationResult:
        """Mock phone lookup for testing"""
        await asyncio.sleep(0.1)  # Simulate API delay

        if phone_number in self.mock_customers:
            customer = self.mock_customers[phone_number]
            return IdentificationResult(
                customer_type=CustomerType.RETURNING,
                verification_status=VerificationStatus.VERIFIED,
                customer_id=customer["customer_id"],
                phone_number=phone_number,
                name=customer["name"],
                confidence_score=0.95,
                identification_method="phone_lookup",
                customer_data=customer,
            )
        else:
            return IdentificationResult(
                customer_type=CustomerType.NEW,
                verification_status=VerificationStatus.NOT_ATTEMPTED,
                phone_number=phone_number,
                confidence_score=0.0,
                identification_method="phone_lookup",
            )

    async def _mock_name_lookup(
        self, name: str, phone_hint: Optional[str] = None
    ) -> IdentificationResult:
        """Mock name lookup for testing"""
        await asyncio.sleep(0.2)  # Simulate API delay

        name_lower = name.lower()
        matches = []

        for phone, customer in self.mock_customers.items():
            if customer["name"].lower() == name_lower:
                matches.append((phone, customer))

        if len(matches) == 1:
            # Single match - high confidence
            phone, customer = matches[0]
            return IdentificationResult(
                customer_type=CustomerType.RETURNING,
                verification_status=VerificationStatus.VERIFIED,
                customer_id=customer["customer_id"],
                phone_number=phone,
                name=customer["name"],
                confidence_score=0.85,
                identification_method="name_lookup",
                customer_data=customer,
            )
        elif len(matches) > 1 and phone_hint:
            # Multiple matches - try to disambiguate with phone hint
            normalized_hint = self._normalize_phone_number(phone_hint)
            for phone, customer in matches:
                if phone == normalized_hint:
                    return IdentificationResult(
                        customer_type=CustomerType.RETURNING,
                        verification_status=VerificationStatus.VERIFIED,
                        customer_id=customer["customer_id"],
                        phone_number=phone,
                        name=customer["name"],
                        confidence_score=0.90,
                        identification_method="name_plus_phone_lookup",
                        customer_data=customer,
                    )

        # No match or ambiguous
        return IdentificationResult(
            customer_type=CustomerType.NEW,
            verification_status=VerificationStatus.NOT_ATTEMPTED,
            name=name,
            confidence_score=0.0,
            identification_method="name_lookup",
        )

    async def _shopware_phone_lookup(self, phone_number: str) -> IdentificationResult:
        """Real Shop-Ware phone lookup"""
        if not self.shopware_client:
            return IdentificationResult(
                customer_type=CustomerType.UNKNOWN,
                verification_status=VerificationStatus.FAILED,
                error_message="Shop-Ware client not configured",
            )

        try:
            # Search for customer by phone number
            customers = await self.shopware_client.search_customers_by_phone(
                phone_number
            )

            if customers:
                customer = customers[0]  # Take first match
                return IdentificationResult(
                    customer_type=CustomerType.RETURNING,
                    verification_status=VerificationStatus.VERIFIED,
                    customer_id=customer.get("id"),
                    phone_number=phone_number,
                    name=f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                    confidence_score=0.95,
                    identification_method="shopware_phone_lookup",
                    customer_data=customer,
                )
            else:
                return IdentificationResult(
                    customer_type=CustomerType.NEW,
                    verification_status=VerificationStatus.NOT_ATTEMPTED,
                    phone_number=phone_number,
                    confidence_score=0.0,
                    identification_method="shopware_phone_lookup",
                )

        except Exception as e:
            self.logger.error(f"Shop-Ware phone lookup error: {e}")
            return IdentificationResult(
                customer_type=CustomerType.UNKNOWN,
                verification_status=VerificationStatus.FAILED,
                error_message=str(e),
            )

    async def _shopware_name_lookup(self, name: str) -> IdentificationResult:
        """Real Shop-Ware name lookup"""
        if not self.shopware_client:
            return IdentificationResult(
                customer_type=CustomerType.UNKNOWN,
                verification_status=VerificationStatus.FAILED,
                error_message="Shop-Ware client not configured",
            )

        try:
            # Search for customer by name
            customers = await self.shopware_client.search_customers_by_name(name)

            if customers:
                if len(customers) == 1:
                    # Single match
                    customer = customers[0]
                    return IdentificationResult(
                        customer_type=CustomerType.RETURNING,
                        verification_status=VerificationStatus.VERIFIED,
                        customer_id=customer.get("id"),
                        phone_number=customer.get("phone"),
                        name=f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                        confidence_score=0.85,
                        identification_method="shopware_name_lookup",
                        customer_data=customer,
                    )
                else:
                    # Multiple matches - need disambiguation
                    return IdentificationResult(
                        customer_type=CustomerType.RETURNING,
                        verification_status=VerificationStatus.PENDING,
                        name=name,
                        confidence_score=0.5,
                        identification_method="shopware_name_lookup",
                        error_message=f"Found {len(customers)} customers with that name",
                    )
            else:
                return IdentificationResult(
                    customer_type=CustomerType.NEW,
                    verification_status=VerificationStatus.NOT_ATTEMPTED,
                    name=name,
                    confidence_score=0.0,
                    identification_method="shopware_name_lookup",
                )

        except Exception as e:
            self.logger.error(f"Shop-Ware name lookup error: {e}")
            return IdentificationResult(
                customer_type=CustomerType.UNKNOWN,
                verification_status=VerificationStatus.FAILED,
                error_message=str(e),
            )


# Integration helper for groq_handler.py
class CustomerContextManager:
    """
    Manages customer context for JAIMES conversations
    """

    def __init__(self, identification_engine: CustomerIdentificationEngine):
        self.engine = identification_engine
        self.active_sessions = {}  # phone_number -> customer_data

    async def get_customer_context(self, phone_number: str) -> Dict[str, Any]:
        """
        Get customer context for a phone number

        Returns dict with:
        - is_returning: bool
        - customer_name: str or None
        - vehicles: list of vehicle dicts
        - last_service: str or None
        - preferences: dict
        """
        # Check cache first
        if phone_number in self.active_sessions:
            return self.active_sessions[phone_number]

        # Look up customer
        result = await self.engine.identify_customer_by_phone(phone_number)

        context = {
            "is_returning": result.customer_type == CustomerType.RETURNING,
            "customer_name": result.name,
            "customer_id": result.customer_id,
            "vehicles": [],
            "last_service": None,
            "preferences": {},
        }

        if result.customer_data:
            context["vehicles"] = result.customer_data.get("vehicles", [])
            context["last_service"] = result.customer_data.get("last_service")
            context["preferences"] = {
                "contact_method": result.customer_data.get(
                    "preferred_contact", "phone"
                ),
                "notes": result.customer_data.get("notes", ""),
            }

        # Cache for session
        self.active_sessions[phone_number] = context
        return context


# Example usage and testing
if __name__ == "__main__":

    async def test_customer_identification():
        """Test the customer identification system"""
        engine = CustomerIdentificationEngine(testing_mode=True)

        # Test phone lookup - returning customer
        print("Testing phone lookup for returning customer...")
        result = await engine.identify_customer_by_phone("(919) 555-0123")
        print(f"Result: {json.dumps(result.to_dict(), indent=2)}")

        # Test phone lookup - new customer
        print("\nTesting phone lookup for new customer...")
        result = await engine.identify_customer_by_phone("(919) 555-9999")
        print(f"Result: {json.dumps(result.to_dict(), indent=2)}")

        # Test name lookup
        print("\nTesting name lookup...")
        result = await engine.identify_customer_by_name("Sarah Johnson")
        print(f"Result: {json.dumps(result.to_dict(), indent=2)}")

        # Test verification
        print("\nTesting customer verification...")
        verified = await engine.verify_customer_identity(
            "CUST_001", {"last_four_phone": "0123", "vehicle_year": "2019"}
        )
        print(f"Verification result: {verified}")

        # Test context manager
        print("\nTesting context manager...")
        context_mgr = CustomerContextManager(engine)
        context = await context_mgr.get_customer_context("(919) 555-0456")
        print(f"Customer context: {json.dumps(context, indent=2)}")

    # Run test
    asyncio.run(test_customer_identification())
