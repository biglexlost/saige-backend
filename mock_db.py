# /src/mock_db.py

import re
from typing import Dict, Optional
from datetime import date
from models import CustomerProfile, VehicleInfo, ServiceHistoryEntry


def normalize_phone_number_for_db(phone: str) -> str:
    """
    Strips all non-digit characters and returns a consistent 10-digit number.
    This is the single source of truth for phone number format.
    """
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) == 11 and digits_only.startswith("1"):
        return digits_only[1:]  # Strip the leading '1' for US numbers
    return digits_only


class MockCustomerEngine:
    """A mock customer database engine..."""

    def __init__(self):
        self._customers: Dict[str, CustomerProfile] = {
            "lex-456": CustomerProfile(
                customer_id="lex-456",
                name="Lex Jimenez",
                phone="+18087790738",
                vehicles=[
                    VehicleInfo(year=2015, make="Subaru", model="Outback", vin=None),
                    VehicleInfo(year=2019, make="Toyota", model="Tacoma", vin=None),
                ],
                # --- ADDED SERVICE HISTORY FOR LEX ---
                service_history=[
                    ServiceHistoryEntry(
                        service_date=date(2025, 6, 12),
                        vehicle_description="2019 Toyota Tacoma",
                        service_description="a sixty-thousand-mile service",
                    )
                ],
            ),
            "rob-123": CustomerProfile(
                customer_id="rob-123",
                name="Rob Black",
                phone="+17194399345",
                vehicles=[
                    VehicleInfo(year=2017, make="Toyota", model="Corolla", vin=None),
                    VehicleInfo(year=2015, make="Subaru", model="Outback", vin=None),
                ],
                # --- ADDED SERVICE HISTORY FOR ROB ---
                service_history=[
                    ServiceHistoryEntry(
                        service_date=date(2025, 7, 2),
                        vehicle_description="2017 Toyota Corolla",
                        service_description="an alignment check",
                    )
                ],
            ),
            "daughtry-789": CustomerProfile(
                customer_id="daughtry-789",
                name="David Daughtry",
                phone="+19195556789",
                vehicles=[
                    VehicleInfo(year=2017, make="Toyota", model="Corolla", vin=None)
                ],
                # --- ADDED SERVICE HISTORY FOR DAVID ---
                service_history=[
                    ServiceHistoryEntry(
                        service_date=date(2025, 5, 20),
                        vehicle_description="2017 Toyota Corolla",
                        service_description="an alignment check",
                    )
                ],
            ),
        }
        print("MockCustomerEngine initialized with mock data.")

    async def find_customer_by_phone(
        self, phone_number: str
    ) -> Optional[CustomerProfile]:
        """Finds a customer by comparing fully normalized phone numbers."""
        # This function now expects an already-normalized 10-digit number.
        print(f"Mock DB: Searching for normalized phone number: {phone_number}")
        for profile in self._customers.values():
            stored_normalized_phone = normalize_phone_number_for_db(profile.phone)
            if stored_normalized_phone == phone_number:
                print(f"Mock DB: Found match for {phone_number}: {profile.name}")
                return profile
        print(f"Mock DB: No match found for {phone_number}")
        return None
