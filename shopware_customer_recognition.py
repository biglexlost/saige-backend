"""
Shop-Ware Customer Recognition Engine for JAIMES AI Executive
============================================================

This module provides customer recognition and data retrieval from Shop-Ware,
including customer profiles, vehicle information, and service history.

Author: JAIMES Development Team
Date: December 7, 2025
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class CustomerProfile:
    """Customer profile information from Shop-Ware"""

    customer_id: str
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    created_date: Optional[str] = None
    last_visit: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get customer's full name"""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class VehicleProfile:
    """Vehicle profile information"""

    vehicle_id: str
    customer_id: str
    year: int
    make: str
    model: str
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    mileage: Optional[int] = None
    is_primary: bool = False

    @property
    def description(self) -> str:
        """Get vehicle description"""
        return f"{self.year} {self.make} {self.model}"


@dataclass
class ServiceHistory:
    """Service history record"""

    service_id: str
    customer_id: str
    vehicle_id: str
    date: str
    service_type: str
    description: str
    mileage: Optional[int] = None
    cost: Optional[float] = None
    technician: Optional[str] = None
    notes: Optional[str] = None


class CustomerRecognitionEngine:
    """
    Engine for recognizing customers and retrieving their information from Shop-Ware
    """

    def __init__(self, shopware_client=None, testing_mode: bool = False):
        """
        Initialize the customer recognition engine

        Args:
            shopware_client: Shop-Ware API client
            testing_mode: If True, use mock data instead of real API calls
        """
        self.shopware_client = shopware_client
        self.testing_mode = testing_mode
        self.logger = logging.getLogger(__name__)

        # Mock data for testing
        self.mock_customers = {
            "CUST_001": CustomerProfile(
                customer_id="CUST_001",
                first_name="John",
                last_name="Smith",
                phone="(919) 555-0123",
                email="john.smith@email.com",
                created_date="2023-05-15",
                last_visit="2024-09-15",
            ),
            "CUST_002": CustomerProfile(
                customer_id="CUST_002",
                first_name="Sarah",
                last_name="Johnson",
                phone="(919) 555-0456",
                email="sarah.johnson@email.com",
                created_date="2023-08-20",
                last_visit="2024-10-20",
            ),
        }

        self.mock_vehicles = {
            "CUST_001": [
                VehicleProfile(
                    vehicle_id="VEH_001",
                    customer_id="CUST_001",
                    year=2019,
                    make="Honda",
                    model="Civic",
                    vin="1HGBH41JXMN109186",
                    license_plate="ABC123",
                    mileage=45000,
                    is_primary=True,
                )
            ],
            "CUST_002": [
                VehicleProfile(
                    vehicle_id="VEH_002",
                    customer_id="CUST_002",
                    year=2020,
                    make="Toyota",
                    model="Camry",
                    vin="4T1BF1FK5CU123456",
                    license_plate="XYZ789",
                    mileage=32000,
                    is_primary=True,
                )
            ],
        }

        self.mock_service_history = {
            "CUST_001": [
                ServiceHistory(
                    service_id="SVC_001",
                    customer_id="CUST_001",
                    vehicle_id="VEH_001",
                    date="2024-09-15",
                    service_type="Oil Change",
                    description="Full synthetic oil change",
                    mileage=45000,
                    cost=89.99,
                    technician="Mike",
                    notes="Brake pads at 40% - recommend inspection in 3 months",
                ),
                ServiceHistory(
                    service_id="SVC_002",
                    customer_id="CUST_001",
                    vehicle_id="VEH_001",
                    date="2024-06-10",
                    service_type="Brake Inspection",
                    description="Brake system inspection",
                    mileage=42000,
                    cost=125.00,
                    technician="Dave",
                    notes="Brake pads at 60% - good condition",
                ),
            ],
            "CUST_002": [
                ServiceHistory(
                    service_id="SVC_003",
                    customer_id="CUST_002",
                    vehicle_id="VEH_002",
                    date="2024-10-20",
                    service_type="Brake Inspection",
                    description="Comprehensive brake inspection",
                    mileage=32000,
                    cost=125.00,
                    technician="Mike",
                    notes="All systems good - next oil change due at 35,000 miles",
                )
            ],
        }

    async def recognize_customer_by_phone(
        self, phone_number: str
    ) -> Optional[CustomerProfile]:
        """
        Recognize customer by phone number

        Args:
            phone_number: Customer's phone number

        Returns:
            CustomerProfile if found, None otherwise
        """
        try:
            if self.testing_mode:
                return await self._mock_phone_recognition(phone_number)
            else:
                return await self._shopware_phone_recognition(phone_number)

        except Exception as e:
            self.logger.error(f"Error recognizing customer by phone: {e}")
            return None

    async def get_customer_vehicles(self, customer_id: str) -> List[VehicleProfile]:
        """
        Get all vehicles for a customer

        Args:
            customer_id: Customer ID

        Returns:
            List of VehicleProfile objects
        """
        try:
            if self.testing_mode:
                return await self._mock_get_vehicles(customer_id)
            else:
                return await self._shopware_get_vehicles(customer_id)

        except Exception as e:
            self.logger.error(f"Error getting customer vehicles: {e}")
            return []

    async def get_customer_service_history(
        self, customer_id: str, limit: int = 10
    ) -> List[ServiceHistory]:
        """
        Get service history for a customer

        Args:
            customer_id: Customer ID
            limit: Maximum number of records to return

        Returns:
            List of ServiceHistory objects
        """
        try:
            if self.testing_mode:
                return await self._mock_get_service_history(customer_id, limit)
            else:
                return await self._shopware_get_service_history(customer_id, limit)

        except Exception as e:
            self.logger.error(f"Error getting service history: {e}")
            return []

    async def get_primary_vehicle(self, customer_id: str) -> Optional[VehicleProfile]:
        """
        Get customer's primary vehicle

        Args:
            customer_id: Customer ID

        Returns:
            Primary VehicleProfile or None
        """
        vehicles = await self.get_customer_vehicles(customer_id)

        # Look for vehicle marked as primary
        for vehicle in vehicles:
            if vehicle.is_primary:
                return vehicle

        # If no primary marked, return first vehicle
        return vehicles[0] if vehicles else None

    async def get_last_service(self, customer_id: str) -> Optional[ServiceHistory]:
        """
        Get customer's most recent service

        Args:
            customer_id: Customer ID

        Returns:
            Most recent ServiceHistory or None
        """
        history = await self.get_customer_service_history(customer_id, limit=1)
        return history[0] if history else None

    async def search_customers_by_name(self, name: str) -> List[CustomerProfile]:
        """
        Search for customers by name

        Args:
            name: Customer name to search for

        Returns:
            List of matching CustomerProfile objects
        """
        try:
            if self.testing_mode:
                return await self._mock_name_search(name)
            else:
                return await self._shopware_name_search(name)

        except Exception as e:
            self.logger.error(f"Error searching customers by name: {e}")
            return []

    # Mock methods for testing
    async def _mock_phone_recognition(
        self, phone_number: str
    ) -> Optional[CustomerProfile]:
        """Mock phone recognition for testing"""
        await asyncio.sleep(0.1)  # Simulate API delay

        for customer in self.mock_customers.values():
            if customer.phone == phone_number:
                return customer
        return None

    async def _mock_get_vehicles(self, customer_id: str) -> List[VehicleProfile]:
        """Mock vehicle retrieval for testing"""
        await asyncio.sleep(0.1)  # Simulate API delay
        return self.mock_vehicles.get(customer_id, [])

    async def _mock_get_service_history(
        self, customer_id: str, limit: int
    ) -> List[ServiceHistory]:
        """Mock service history retrieval for testing"""
        await asyncio.sleep(0.1)  # Simulate API delay
        history = self.mock_service_history.get(customer_id, [])
        return history[:limit]

    async def _mock_name_search(self, name: str) -> List[CustomerProfile]:
        """Mock name search for testing"""
        await asyncio.sleep(0.2)  # Simulate API delay

        results = []
        name_lower = name.lower()

        for customer in self.mock_customers.values():
            if (
                name_lower in customer.first_name.lower()
                or name_lower in customer.last_name.lower()
                or name_lower in customer.full_name.lower()
            ):
                results.append(customer)

        return results

    # Real Shop-Ware methods
    async def _shopware_phone_recognition(
        self, phone_number: str
    ) -> Optional[CustomerProfile]:
        """Real Shop-Ware phone recognition"""
        if not self.shopware_client:
            return None

        try:
            customers = await self.shopware_client.search_customers_by_phone(
                phone_number
            )
            if customers:
                customer_data = customers[0]
                return CustomerProfile(
                    customer_id=customer_data.get("id"),
                    first_name=customer_data.get("firstName", ""),
                    last_name=customer_data.get("lastName", ""),
                    phone=customer_data.get("phone", ""),
                    email=customer_data.get("email"),
                    created_date=customer_data.get("createdAt"),
                    last_visit=customer_data.get("lastVisit"),
                )
            return None

        except Exception as e:
            self.logger.error(f"Shop-Ware phone recognition error: {e}")
            return None

    async def _shopware_get_vehicles(self, customer_id: str) -> List[VehicleProfile]:
        """Real Shop-Ware vehicle retrieval"""
        if not self.shopware_client:
            return []

        try:
            vehicles_data = await self.shopware_client.get_customer_vehicles(
                customer_id
            )
            vehicles = []

            for vehicle_data in vehicles_data:
                vehicle = VehicleProfile(
                    vehicle_id=vehicle_data.get("id"),
                    customer_id=customer_id,
                    year=vehicle_data.get("year"),
                    make=vehicle_data.get("make"),
                    model=vehicle_data.get("model"),
                    vin=vehicle_data.get("vin"),
                    license_plate=vehicle_data.get("licensePlate"),
                    mileage=vehicle_data.get("mileage"),
                    is_primary=vehicle_data.get("isPrimary", False),
                )
                vehicles.append(vehicle)

            return vehicles

        except Exception as e:
            self.logger.error(f"Shop-Ware vehicle retrieval error: {e}")
            return []

    async def _shopware_get_service_history(
        self, customer_id: str, limit: int
    ) -> List[ServiceHistory]:
        """Real Shop-Ware service history retrieval"""
        if not self.shopware_client:
            return []

        try:
            history_data = await self.shopware_client.get_customer_service_history(
                customer_id, limit
            )
            history = []

            for service_data in history_data:
                service = ServiceHistory(
                    service_id=service_data.get("id"),
                    customer_id=customer_id,
                    vehicle_id=service_data.get("vehicleId"),
                    date=service_data.get("date"),
                    service_type=service_data.get("serviceType"),
                    description=service_data.get("description"),
                    mileage=service_data.get("mileage"),
                    cost=service_data.get("cost"),
                    technician=service_data.get("technician"),
                    notes=service_data.get("notes"),
                )
                history.append(service)

            return history

        except Exception as e:
            self.logger.error(f"Shop-Ware service history error: {e}")
            return []

    async def _shopware_name_search(self, name: str) -> List[CustomerProfile]:
        """Real Shop-Ware name search"""
        if not self.shopware_client:
            return []

        try:
            customers_data = await self.shopware_client.search_customers_by_name(name)
            customers = []

            for customer_data in customers_data:
                customer = CustomerProfile(
                    customer_id=customer_data.get("id"),
                    first_name=customer_data.get("firstName", ""),
                    last_name=customer_data.get("lastName", ""),
                    phone=customer_data.get("phone", ""),
                    email=customer_data.get("email"),
                    created_date=customer_data.get("createdAt"),
                    last_visit=customer_data.get("lastVisit"),
                )
                customers.append(customer)

            return customers

        except Exception as e:
            self.logger.error(f"Shop-Ware name search error: {e}")
            return []


# Example usage and testing
if __name__ == "__main__":

    async def test_customer_recognition():
        """Test the customer recognition engine"""
        engine = CustomerRecognitionEngine(testing_mode=True)

        # Test phone recognition
        print("Testing phone recognition...")
        customer = await engine.recognize_customer_by_phone("(919) 555-0123")
        if customer:
            print(f"Found customer: {customer.full_name}")

            # Test vehicle retrieval
            print("\nTesting vehicle retrieval...")
            vehicles = await engine.get_customer_vehicles(customer.customer_id)
            for vehicle in vehicles:
                print(f"Vehicle: {vehicle.description}")

            # Test service history
            print("\nTesting service history...")
            history = await engine.get_customer_service_history(customer.customer_id)
            for service in history:
                print(f"Service: {service.date} - {service.service_type}")
        else:
            print("No customer found")

    # Run test
    asyncio.run(test_customer_recognition())
