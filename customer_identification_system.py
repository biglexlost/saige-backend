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
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)

# Mock customer data for development/testing
MOCK_CUSTOMERS = {
    "1234567890": {
        "customer_id": "1",
        "name": "Alex Johnson",
        "phone": "1234567890",
        "email": "alex@example.com",
        "vehicles": [],
        "service_history": ["facial", "massage"],
        "last_visit": "2024-01-15",
        "preferences": ["anti-aging", "relaxation"]
    },
    "5551234567": {
        "customer_id": "2", 
        "name": "Sarah Smith",
        "phone": "5551234567",
        "email": "sarah@example.com",
        "vehicles": [],
        "service_history": ["botox", "filler"],
        "last_visit": "2024-02-20",
        "preferences": ["wrinkle reduction", "volume restoration"]
    },
    "9998887777": {
        "customer_id": "3",
        "name": "Mike Davis",
        "phone": "9998887777", 
        "email": "mike@example.com",
        "vehicles": [],
        "service_history": ["laser hair removal"],
        "last_visit": "2024-03-10",
        "preferences": ["permanent hair reduction"]
    }
}

class CustomerProfile(BaseModel):
    """Customer profile for med-spa services"""
    customer_id: str
    name: str
    phone: str
    email: Optional[str] = None
    vehicles: List[str] = []  # Keep for compatibility but not used
    service_history: List[str] = []
    last_visit: Optional[str] = None
    preferences: List[str] = []

class IdentificationResult(BaseModel):
    """Result of customer identification attempt"""
    customer_profile: Optional[CustomerProfile] = None
    identification_method: str
    confidence_score: float
    additional_data: Dict[str, Any] = {}

class MockCustomerEngine:
    """Mock customer identification engine for development/testing"""
    
    def __init__(self):
        logger.info("MockCustomerEngine initialized with mock data")
        self.customers = MOCK_CUSTOMERS.copy()
    
    async def find_customer_by_phone(self, phone_number: str) -> Optional[CustomerProfile]:
        """Find customer by phone number"""
        normalized_phone = self._normalize_phone(phone_number)
        if normalized_phone in self.customers:
            customer_data = self.customers[normalized_phone]
            return CustomerProfile(**customer_data)
        return None
    
    async def find_customer_by_name(self, name: str) -> Optional[CustomerProfile]:
        """Find customer by name"""
        normalized_name = self._normalize_name(name)
        for customer_data in self.customers.values():
            if self._normalize_name(customer_data["name"]) == normalized_name:
                return CustomerProfile(**customer_data)
        return None
    
    async def search_customers_by_phone(self, phone_number: str) -> List[CustomerProfile]:
        """Search for customers by phone number (partial match)"""
        normalized_phone = self._normalize_phone(phone_number)
        results = []
        for phone, customer_data in self.customers.items():
            if normalized_phone in phone or phone in normalized_phone:
                results.append(CustomerProfile(**customer_data))
        return results
    
    async def search_customers_by_name(self, name: str) -> List[CustomerProfile]:
        """Search for customers by name (partial match)"""
        normalized_name = self._normalize_name(name)
        results = []
        for customer_data in self.customers.values():
            if normalized_name in self._normalize_name(customer_data["name"]):
                results.append(CustomerProfile(**customer_data))
        return results
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        return re.sub(r'\D', '', phone)
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        return re.sub(r'[^\w\s]', '', name.lower()).strip()
