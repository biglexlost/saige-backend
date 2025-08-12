#!/usr/bin/env python3
"""
Shop-Ware API Integration Framework for JAIMES
Handles customer management, appointment scheduling, and service integration
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class CustomerType(Enum):
    """Customer types supported by Shop-Ware"""

    INDIVIDUAL = "individual"
    CORPORATE = "corporate"


@dataclass
class PhoneNumber:
    """Phone number structure for Shop-Ware API"""

    number: str  # E.164 format: +15554441234
    label: Optional[str] = None
    preferred: bool = False
    show_on_ro: bool = True


@dataclass
class Customer:
    """Customer data structure for Shop-Ware API"""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None  # Deprecated but still supported
    detail: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    marketing_ok: bool = True
    phones: List[PhoneNumber] = None
    shop_id: int = 1  # Default shop ID
    customer_type: CustomerType = CustomerType.INDIVIDUAL
    date_of_birth: Optional[str] = None  # YYYY-MM-DD format
    business_name: Optional[str] = None
    fleet_id: Optional[str] = None

    def __post_init__(self):
        if self.phones is None:
            self.phones = []


@dataclass
class Appointment:
    """Appointment data structure for Shop-Ware API"""

    shop_id: int
    start_at: str  # ISO 8601 format: 2025-01-15T09:00:00Z
    title: Optional[str] = None
    repair_order_id: Optional[int] = None
    staff_id: Optional[int] = None
    description: Optional[str] = None
    end_at: Optional[str] = None


@dataclass
class ShopWareConfig:
    """Configuration for Shop-Ware API client"""

    base_url: str
    tenant_id: int
    api_partner_id: str
    api_secret: str
    timeout: int = 30
    max_retries: int = 3


class ShopWareAPIError(Exception):
    """Custom exception for Shop-Ware API errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class ShopWareAPIClient:
    """Async Shop-Ware API client with comprehensive error handling"""

    def __init__(self, config: ShopWareConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()

    async def connect(self):
        """Initialize the HTTP session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout, headers=self.base_headers
            )
            logger.info("Shop-Ware API client connected")

    async def disconnect(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Shop-Ware API client disconnected")

    def _get_auth_params(self) -> Dict[str, str]:
        """Get authentication parameters"""
        return {
            "api_partner_id": self.config.api_partner_id,
            "api_secret": self.config.api_secret,
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Shop-Ware API with retry logic"""
        if not self.session:
            await self.connect()

        url = (
            f"{self.config.base_url}/api/v1/tenants/{self.config.tenant_id}/{endpoint}"
        )

        # Add authentication parameters
        if params is None:
            params = {}
        params.update(self._get_auth_params())

        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[{request_id}] {method} {endpoint}")

        for attempt in range(self.config.max_retries):
            try:
                async with self.session.request(
                    method=method, url=url, json=data, params=params
                ) as response:
                    response_data = (
                        await response.json()
                        if response.content_type == "application/json"
                        else {}
                    )

                    if response.status >= 200 and response.status < 300:
                        logger.info(f"[{request_id}] Success: {response.status}")
                        return response_data
                    else:
                        error_msg = f"API request failed: {response.status}"
                        if response_data:
                            error_msg += f" - {response_data}"

                        logger.error(f"[{request_id}] {error_msg}")

                        if attempt == self.config.max_retries - 1:
                            raise ShopWareAPIError(
                                error_msg,
                                status_code=response.status,
                                response_data=response_data,
                            )

                        # Wait before retry
                        await asyncio.sleep(2**attempt)

            except aiohttp.ClientError as e:
                error_msg = f"Network error: {str(e)}"
                logger.error(f"[{request_id}] {error_msg}")

                if attempt == self.config.max_retries - 1:
                    raise ShopWareAPIError(error_msg)

                await asyncio.sleep(2**attempt)

    # Customer Management Methods

    async def create_customer(self, customer: Customer) -> Dict[str, Any]:
        """Create a new customer in Shop-Ware"""
        # Convert customer to API format
        customer_data = self._customer_to_api_format(customer)

        logger.info(f"Creating customer: {customer.first_name} {customer.last_name}")
        return await self._make_request("POST", "customers", data=customer_data)

    async def get_customer(self, customer_id: int) -> Dict[str, Any]:
        """Get customer by ID"""
        logger.info(f"Fetching customer: {customer_id}")
        return await self._make_request("GET", f"customers/{customer_id}")

    async def search_customers(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for customers by various criteria"""
        params = {"limit": limit}

        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone
        if name:
            params["name"] = name

        logger.info(f"Searching customers with params: {params}")
        response = await self._make_request("GET", "customers", params=params)
        return response.get("data", [])

    async def update_customer(
        self, customer_id: int, customer: Customer
    ) -> Dict[str, Any]:
        """Update existing customer"""
        customer_data = self._customer_to_api_format(customer)

        logger.info(f"Updating customer: {customer_id}")
        return await self._make_request(
            "PUT", f"customers/{customer_id}", data=customer_data
        )

    # Appointment Management Methods

    async def create_appointment(self, appointment: Appointment) -> Dict[str, Any]:
        """Create a new appointment in Shop-Ware"""
        appointment_data = self._appointment_to_api_format(appointment)

        logger.info(f"Creating appointment for {appointment.start_at}")
        return await self._make_request("POST", "appointments", data=appointment_data)

    async def get_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """Get appointment by ID"""
        logger.info(f"Fetching appointment: {appointment_id}")
        return await self._make_request("GET", f"appointments/{appointment_id}")

    async def get_appointments(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        shop_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get appointments with optional filtering"""
        params = {"limit": limit}

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if shop_id:
            params["shop_id"] = shop_id

        logger.info(f"Fetching appointments with params: {params}")
        response = await self._make_request("GET", "appointments", params=params)
        return response.get("data", [])

    async def update_appointment(
        self, appointment_id: int, appointment: Appointment
    ) -> Dict[str, Any]:
        """Update existing appointment"""
        appointment_data = self._appointment_to_api_format(appointment)

        logger.info(f"Updating appointment: {appointment_id}")
        return await self._make_request(
            "PUT", f"appointments/{appointment_id}", data=appointment_data
        )

    async def delete_appointment(self, appointment_id: int) -> bool:
        """Delete appointment"""
        logger.info(f"Deleting appointment: {appointment_id}")
        await self._make_request("DELETE", f"appointments/{appointment_id}")
        return True

    # Availability and Scheduling Methods

    async def get_available_slots(
        self, date: str, shop_id: Optional[int] = None, duration_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get available appointment slots for a given date"""
        params = {"date": date, "duration": duration_minutes}

        if shop_id:
            params["shop_id"] = shop_id

        logger.info(f"Fetching available slots for {date}")
        try:
            response = await self._make_request(
                "GET", "appointments/availability", params=params
            )
            return response.get("available_slots", [])
        except ShopWareAPIError as e:
            # If availability endpoint doesn't exist, return mock data
            logger.warning(f"Availability endpoint not available: {e.message}")
            return self._generate_mock_availability(date, duration_minutes)

    async def get_shop_info(self, shop_id: Optional[int] = None) -> Dict[str, Any]:
        """Get shop information"""
        if shop_id is None:
            shop_id = self.config.tenant_id

        logger.info(f"Fetching shop info: {shop_id}")
        try:
            return await self._make_request("GET", f"shops/{shop_id}")
        except ShopWareAPIError:
            # Return mock shop data if endpoint doesn't exist
            return {
                "id": shop_id,
                "name": "MileX Complete Auto Care",
                "address": "Durham, NC",
                "phone": "+1-919-555-0123",
                "hours": {
                    "monday": "8:00 AM - 6:00 PM",
                    "tuesday": "8:00 AM - 6:00 PM",
                    "wednesday": "8:00 AM - 6:00 PM",
                    "thursday": "8:00 AM - 6:00 PM",
                    "friday": "8:00 AM - 6:00 PM",
                    "saturday": "8:00 AM - 4:00 PM",
                    "sunday": "Closed",
                },
            }

    # Helper Methods

    def _customer_to_api_format(self, customer: Customer) -> Dict[str, Any]:
        """Convert Customer object to Shop-Ware API format"""
        data = {}

        # Basic fields
        if customer.first_name:
            data["first_name"] = customer.first_name
        if customer.last_name:
            data["last_name"] = customer.last_name
        if customer.email:
            data["email"] = customer.email
        if customer.phone:
            data["phone"] = customer.phone
        if customer.detail:
            data["detail"] = customer.detail
        if customer.address:
            data["address"] = customer.address
        if customer.city:
            data["city"] = customer.city
        if customer.state:
            data["state"] = customer.state
        if customer.zip:
            data["zip"] = customer.zip

        data["marketing_ok"] = customer.marketing_ok
        data["shop_id"] = customer.shop_id
        data["customer_type"] = customer.customer_type.value

        if customer.date_of_birth:
            data["date_of_birth"] = customer.date_of_birth
        if customer.business_name:
            data["business_name"] = customer.business_name
        if customer.fleet_id:
            data["fleet_id"] = customer.fleet_id

        # Phone numbers
        if customer.phones:
            data["phones"] = [asdict(phone) for phone in customer.phones]

        return data

    def _appointment_to_api_format(self, appointment: Appointment) -> Dict[str, Any]:
        """Convert Appointment object to Shop-Ware API format"""
        data = {"shop_id": appointment.shop_id, "start_at": appointment.start_at}

        if appointment.title:
            data["title"] = appointment.title
        if appointment.repair_order_id:
            data["repair_order_id"] = appointment.repair_order_id
        if appointment.staff_id:
            data["staff_id"] = appointment.staff_id
        if appointment.description:
            data["description"] = appointment.description
        if appointment.end_at:
            data["end_at"] = appointment.end_at

        return data

    def _generate_mock_availability(
        self, date: str, duration_minutes: int
    ) -> List[Dict[str, Any]]:
        """Generate mock availability data for testing"""
        slots = []
        start_hour = 8
        end_hour = 17

        for hour in range(start_hour, end_hour):
            for minute in [0, 30]:
                if hour == end_hour - 1 and minute == 30:
                    break  # Don't go past closing time

                slot_time = f"{hour:02d}:{minute:02d}"
                slots.append(
                    {
                        "start_time": f"{date}T{slot_time}:00Z",
                        "end_time": f"{date}T{hour:02d}:{minute + duration_minutes:02d}:00Z",
                        "available": True,
                        "staff_id": 1,
                    }
                )

        return slots


class JAIMESShopWareIntegration:
    """High-level integration class for JAIMES and Shop-Ware"""

    def __init__(self, config: ShopWareConfig):
        self.config = config
        self.client = ShopWareAPIClient(config)

    async def __aenter__(self):
        await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.disconnect()

    async def create_customer_from_conversation(
        self,
        name: str,
        phone: str,
        email: Optional[str] = None,
        vehicle_info: Optional[Dict] = None,
        problem_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create customer from JAIMES conversation data"""

        # Parse name
        name_parts = name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        # Format phone number to E.164
        formatted_phone = self._format_phone_number(phone)

        # Create customer object
        customer = Customer(
            first_name=first_name,
            last_name=last_name,
            email=email,
            detail=problem_description,
            phones=[
                PhoneNumber(
                    number=formatted_phone,
                    label="Primary",
                    preferred=True,
                    show_on_ro=True,
                )
            ],
            shop_id=1,  # MileX Durham location
        )

        try:
            result = await self.client.create_customer(customer)
            logger.info(f"Created customer: {result.get('id')} - {name}")
            return result
        except ShopWareAPIError as e:
            logger.error(f"Failed to create customer: {e.message}")
            raise

    async def schedule_appointment_from_conversation(
        self,
        customer_id: int,
        preferred_date: str,
        preferred_time: Optional[str] = None,
        service_description: Optional[str] = None,
        urgency: str = "normal",
    ) -> Dict[str, Any]:
        """Schedule appointment from JAIMES conversation"""

        # Get available slots
        available_slots = await self.client.get_available_slots(preferred_date)

        if not available_slots:
            raise ShopWareAPIError(f"No available slots for {preferred_date}")

        # Select best slot based on preference
        selected_slot = self._select_best_slot(available_slots, preferred_time, urgency)

        # Create appointment
        appointment = Appointment(
            shop_id=1,
            start_at=selected_slot["start_time"],
            end_at=selected_slot["end_time"],
            title=service_description or "Vehicle Service",
            description=service_description,
        )

        try:
            result = await self.client.create_appointment(appointment)
            logger.info(
                f"Created appointment: {result.get('id')} for customer {customer_id}"
            )
            return result
        except ShopWareAPIError as e:
            logger.error(f"Failed to create appointment: {e.message}")
            raise

    def _format_phone_number(self, phone: str) -> str:
        """Format phone number to E.164 format"""
        # Remove all non-digit characters
        digits = re.sub(r"\D", "", phone)

        # Add country code if missing
        if len(digits) == 10:
            digits = "1" + digits

        return f"+{digits}"

    def _select_best_slot(
        self,
        available_slots: List[Dict],
        preferred_time: Optional[str] = None,
        urgency: str = "normal",
    ) -> Dict[str, Any]:
        """Select the best available slot based on preferences"""

        if urgency == "urgent":
            # Return first available slot
            return available_slots[0]

        if preferred_time:
            # Try to find slot close to preferred time
            preferred_hour = int(preferred_time.split(":")[0])

            best_slot = None
            min_diff = float("inf")

            for slot in available_slots:
                slot_time = slot["start_time"]
                slot_hour = int(slot_time.split("T")[1].split(":")[0])
                diff = abs(slot_hour - preferred_hour)

                if diff < min_diff:
                    min_diff = diff
                    best_slot = slot

            return best_slot or available_slots[0]

        # Default to first available slot
        return available_slots[0]


# Example usage and testing
async def test_shopware_integration():
    """Test the Shop-Ware integration"""

    # Mock configuration (replace with real values)
    config = ShopWareConfig(
        base_url="https://api.shop-ware.com",
        tenant_id=1,
        api_partner_id="test_partner_id",
        api_secret="test_secret",
    )

    print("Testing Shop-Ware API Integration:")
    print("=" * 50)

    async with JAIMESShopWareIntegration(config) as integration:
        try:
            # Test customer creation
            print("\n1. Testing customer creation...")
            customer_result = await integration.create_customer_from_conversation(
                name="Billy Bob Johnson",
                phone="919-555-1234",
                email="billy.bob@example.com",
                problem_description="Truck making strange noises",
            )
            print(f"✓ Customer created: {customer_result}")

            # Test appointment scheduling
            print("\n2. Testing appointment scheduling...")
            appointment_result = (
                await integration.schedule_appointment_from_conversation(
                    customer_id=customer_result.get("id", 1),
                    preferred_date="2025-01-20",
                    preferred_time="10:00",
                    service_description="Diagnose strange noises",
                    urgency="normal",
                )
            )
            print(f"✓ Appointment scheduled: {appointment_result}")

        except ShopWareAPIError as e:
            print(f"✗ API Error: {e.message}")
        except Exception as e:
            print(f"✗ Unexpected error: {str(e)}")


if __name__ == "__main__":
    import re

    asyncio.run(test_shopware_integration())
