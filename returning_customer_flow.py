"""
Returning Customer Flow Manager for JAIMES AI Executive
======================================================

This module manages the conversation flow for returning customers,
providing proactive service based on their history and vehicle information.

Author: JAIMES Development Team
Date: July 20, 2025
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ReturningCustomerContext:
    """Context information for returning customers"""

    customer_id: str
    name: str
    phone_number: str
    vehicles: List[Dict[str, Any]]
    service_history: List[Dict[str, Any]]
    last_service_date: Optional[str] = None
    preferred_vehicle: Optional[Dict[str, Any]] = None
    upcoming_services: List[Dict[str, Any]] = field(default_factory=list)


class ReturningCustomerFlowManager:
    """
    Manages conversation flow for returning customers
    """

    def __init__(self, shopware_client=None, testing_mode: bool = False):
        """
        Initialize the returning customer flow manager

        Args:
            shopware_client: Shop-Ware API client for customer data
            testing_mode: If True, use mock data instead of real API calls
        """
        self.shopware_client = shopware_client
        self.testing_mode = testing_mode
        self.logger = logging.getLogger(__name__)

    async def get_customer_context(
        self, customer_id: str
    ) -> Optional[ReturningCustomerContext]:
        """Get complete context for a returning customer"""
        try:
            return await self._get_shopware_customer_context(customer_id)
        except Exception as e:
            self.logger.error(f"Error getting customer context: {e}")
            return None

    async def generate_proactive_greeting(
        self, context: ReturningCustomerContext
    ) -> str:
        """Generate a proactive greeting for returning customers"""
        try:
            primary_vehicle = self._get_primary_vehicle(context)
            vehicle_desc = (
                f"{primary_vehicle['year']} {primary_vehicle['make']} {primary_vehicle['model']}"
                if primary_vehicle
                else "your vehicle"
            )

            greeting_parts = [f"Welcome back, {context.name}!"]
            if primary_vehicle:
                greeting_parts.append(f"I see you have the {vehicle_desc}.")

            # Add proactive service suggestions from notes
            if context.service_history and "notes" in context.service_history[0]:
                notes = context.service_history[0]["notes"].lower()
                if "brake" in notes:
                    greeting_parts.append("How are those brakes feeling?")
                elif "oil change" in notes:
                    greeting_parts.append("Are you due for that oil change?")

            greeting_parts.append("What can I help you with today?")
            return " ".join(greeting_parts)
        except Exception as e:
            self.logger.error(f"Error generating proactive greeting: {e}")
            return f"Welcome back, {context.name}! What can I help you with today?"

    async def suggest_upcoming_services(
        self, context: ReturningCustomerContext
    ) -> List[str]:
        """Suggest upcoming services based on customer history"""
        suggestions = []
        try:
            primary_vehicle = self._get_primary_vehicle(context)
            if not primary_vehicle:
                return suggestions

            current_mileage = primary_vehicle.get("mileage", 0)
            if context.service_history:
                last_service = context.service_history[0]
                last_mileage = last_service.get("mileage", 0)
                if current_mileage - last_mileage >= 4500:
                    suggestions.append(
                        "You're due for an oil change based on your mileage."
                    )

            # Seasonal suggestions
            current_month = datetime.now().month
            if current_month in [10, 11, 12]:
                suggestions.append(
                    "With winter coming up, we could check your battery and heating system."
                )
            elif current_month in [3, 4, 5]:
                suggestions.append(
                    "Spring's a great time for a tune-up after the winter months."
                )
        except Exception as e:
            self.logger.error(f"Error suggesting upcoming services: {e}")
        return suggestions

    def _get_primary_vehicle(
        self, context: ReturningCustomerContext
    ) -> Optional[Dict[str, Any]]:
        """Get the customer's primary vehicle"""
        if not context.vehicles:
            return None
        for vehicle in context.vehicles:
            if vehicle.get("is_primary"):
                return vehicle
        return context.vehicles[0]

    def _days_since_last_service(
        self, context: ReturningCustomerContext
    ) -> Optional[int]:
        """Calculate days since last service"""
        if not context.last_service_date:
            return None
        try:
            last_service = datetime.strptime(context.last_service_date, "%Y-%m-%d")
            return (datetime.now() - last_service).days
        except Exception:
            return None

    async def _get_shopware_customer_context(
        self, customer_id: str
    ) -> Optional[ReturningCustomerContext]:
        """Get real customer context from Shop-Ware"""
        if not self.shopware_client:
            return None
        try:
            # Assumes shopware_client has these methods
            customer = await self.shopware_client.get_customer(customer_id)
            if not customer:
                return None

            vehicles = await self.shopware_client.get_customer_vehicles(customer_id)
            service_history = await self.shopware_client.get_customer_service_history(
                customer_id
            )

            return ReturningCustomerContext(
                customer_id=customer_id,
                name=f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                phone_number=customer.get("phone", ""),
                vehicles=vehicles or [],
                service_history=service_history or [],
                last_service_date=(
                    service_history[0].get("date") if service_history else None
                ),
            )
        except Exception as e:
            self.logger.error(f"Error getting Shop-Ware customer context: {e}")
            return None


# Example usage and testing
if __name__ == "__main__":

    async def test_returning_customer_flow():
        """Test the returning customer flow manager"""
        manager = ReturningCustomerFlowManager(testing_mode=True)

        print("Testing customer context...")
        context = await manager.get_customer_context("CUST_001")
        if context:
            print(f"Customer: {context.name}")

            print("\nTesting proactive greeting...")
            greeting = await manager.generate_proactive_greeting(context)
            print(f"Greeting: {greeting}")

            print("\nTesting service suggestions...")
            suggestions = await manager.suggest_upcoming_services(context)
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}")
        else:
            print("No customer context found")

    asyncio.run(test_returning_customer_flow())
