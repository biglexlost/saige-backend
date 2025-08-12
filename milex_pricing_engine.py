#!/usr/bin/env python3
"""
MileX Custom Pricing Engine
Handles shop-specific pricing for maintenance services and oil changes,
integrating with rich vehicle data for maximum accuracy.
"""

import json
import logging
import sqlite3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


# This assumes your models will eventually be in a central file
# from models.schemas import VehicleInfo
# For now, we'll define a minimal version here for compatibility
@dataclass
class VehicleInfo:
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    engine: Optional[str] = None


logger = logging.getLogger(__name__)


class OilType(Enum):
    """Oil types with different pricing"""

    CONVENTIONAL = "conventional"
    HIGH_MILEAGE = "high_mileage"
    SYNTHETIC_BLEND = "synthetic_blend"
    FULL_SYNTHETIC = "full_synthetic"


@dataclass
class OilChangeSpecs:
    """Oil change specifications for a vehicle"""

    oil_capacity_quarts: float
    oil_type_recommended: OilType
    filter_type: str


class VehicleOilDatabase:
    """Database for vehicle oil specifications"""

    def __init__(self, db_path: str = "vehicle_oil_specs.db"):
        self.db_path = db_path
        self._init_database()
        self._populate_common_vehicles()

    def _init_database(self):
        """Initialize vehicle oil specifications database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS vehicle_oil_specs (
                    id INTEGER PRIMARY KEY, year INTEGER NOT NULL, make TEXT NOT NULL,
                    model TEXT NOT NULL, engine_size TEXT, oil_capacity REAL NOT NULL,
                    recommended_oil_type TEXT NOT NULL, filter_type TEXT NOT NULL,
                    UNIQUE(year, make, model, engine_size)
                )
            """
            )
            conn.commit()

    def _populate_common_vehicles(self):
        """Populate database with common vehicle oil specifications"""
        common_vehicles = [
            (2018, "Ford", "F-150", "3.5L V6", 6.0, "full_synthetic", "FL-820-S"),
            (
                2020,
                "Toyota",
                "Camry",
                "2.5L I4",
                4.8,
                "synthetic_blend",
                "Toyota 90915-YZZD4",
            ),
            (
                2019,
                "Honda",
                "Civic",
                "1.5L I4",
                3.7,
                "synthetic_blend",
                "Honda 15400-PLM-A02",
            ),
            (
                2018,
                "Chevrolet",
                "Silverado",
                "5.3L V8",
                8.0,
                "full_synthetic",
                "AC Delco PF48",
            ),
        ]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT OR IGNORE INTO vehicle_oil_specs
                (year, make, model, engine_size, oil_capacity, recommended_oil_type, filter_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                common_vehicles,
            )
            conn.commit()

    def get_oil_specs(self, vehicle: VehicleInfo) -> Optional[OilChangeSpecs]:
        """Get oil specifications for a vehicle using the VehicleInfo object"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT oil_capacity, recommended_oil_type, filter_type
                    FROM vehicle_oil_specs
                    WHERE year = ? AND LOWER(make) = LOWER(?) AND LOWER(model) = LOWER(?)
                """
                params = [vehicle.year, vehicle.make, vehicle.model]
                if vehicle.engine:
                    query += " AND engine_size = ?"
                    params.append(vehicle.engine)

                cursor.execute(query, tuple(params))
                result = cursor.fetchone()

                if result:
                    return OilChangeSpecs(
                        oil_capacity_quarts=result[0],
                        oil_type_recommended=OilType(result[1]),
                        filter_type=result[2],
                    )
            return None
        except Exception as e:
            logger.error(f"Error getting oil specs: {str(e)}")
            return None


class MileXPricingEngine:
    """MileX custom pricing engine for maintenance and oil changes"""

    def __init__(self, pricing_config_path: str = "milex_pricing_config.json"):
        self.oil_database = VehicleOilDatabase()
        self.pricing_config = self._load_pricing_config(pricing_config_path)
        logger.info("MileX Pricing Engine initialized")

    def _load_pricing_config(self, path: str) -> Dict[str, Any]:
        """Load pricing configuration from file or create a default."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            default_config = self._create_default_pricing_config()
            with open(path, "w") as f:
                json.dump(default_config, f, indent=2)
            return default_config

    def _create_default_pricing_config(self) -> Dict[str, Any]:
        """Create a default pricing configuration for MileX Durham."""
        return {
            "oil_change_pricing": {
                "conventional": {
                    "price_per_quart": 4.50,
                    "filter_cost": 8.95,
                    "labor_cost": 19.95,
                },
                "high_mileage": {
                    "price_per_quart": 5.25,
                    "filter_cost": 9.95,
                    "labor_cost": 19.95,
                },
                "synthetic_blend": {
                    "price_per_quart": 6.00,
                    "filter_cost": 10.95,
                    "labor_cost": 24.95,
                },
                "full_synthetic": {
                    "price_per_quart": 7.50,
                    "filter_cost": 12.95,
                    "labor_cost": 29.95,
                },
            },
            "maintenance_services": {
                "radiator_flush": {"base_price": 129.95, "labor_hours": 1.5},
                "transmission_flush": {"base_price": 179.95, "labor_hours": 2.0},
                "tire_rotation": {"base_price": 24.95, "labor_hours": 0.5},
            },
            "taxes": {"sales_tax_rate": 0.075},  # 7.5% for Durham, NC
        }

    def get_oil_change_pricing(
        self, vehicle: VehicleInfo, preferred_oil_type: Optional[OilType] = None
    ) -> Optional[Dict[str, Any]]:
        """Get oil change pricing for a specific vehicle using the VehicleInfo object."""
        try:
            oil_specs = self.oil_database.get_oil_specs(vehicle)
            if not oil_specs:
                logger.warning(
                    f"Oil specs not found for {vehicle.display_name()}, using generic 5-quart estimate."
                )
                oil_specs = OilChangeSpecs(
                    oil_capacity_quarts=5.0,
                    oil_type_recommended=OilType.CONVENTIONAL,
                    filter_type="Standard",
                )

            oil_type = preferred_oil_type or oil_specs.oil_type_recommended
            pricing_data = self.pricing_config["oil_change_pricing"][oil_type.value]

            oil_cost = pricing_data["price_per_quart"] * oil_specs.oil_capacity_quarts
            total = oil_cost + pricing_data["filter_cost"] + pricing_data["labor_cost"]
            sales_tax = total * self.pricing_config["taxes"]["sales_tax_rate"]
            final_total = total + sales_tax

            return {
                "vehicle": vehicle.display_name(),
                "oil_type": oil_type.value,
                "oil_capacity": oil_specs.oil_capacity_quarts,
                "final_total": round(final_total, 2),
            }
        except Exception as e:
            logger.error(f"Error calculating oil change pricing: {str(e)}")
            return None

    def get_maintenance_service_pricing(
        self, service_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get pricing for a general maintenance service."""
        service_key = service_name.lower().replace(" ", "_")
        service_config = self.pricing_config.get("maintenance_services", {}).get(
            service_key
        )

        if not service_config:
            return None

        total = service_config["base_price"]
        sales_tax = total * self.pricing_config["taxes"]["sales_tax_rate"]
        final_total = total + sales_tax

        return {
            "service_name": service_name,
            "base_price": service_config["base_price"],
            "final_total": round(final_total, 2),
        }


def test_milex_pricing_engine():
    """Test the MileX pricing engine"""
    engine = MileXPricingEngine()
    print("Testing MileX Pricing Engine:")
    print("=" * 50)

    print("\n1. Oil Change Pricing:")
    vehicle1 = VehicleInfo(year=2018, make="Ford", model="F-150", engine="3.5L V6")
    pricing1 = engine.get_oil_change_pricing(vehicle1, OilType.FULL_SYNTHETIC)
    if pricing1:
        print(
            f"  {vehicle1.display_name()} (Full Synthetic): ${pricing1['final_total']:.2f}"
        )

    vehicle2 = VehicleInfo(year=2020, make="Toyota", model="Camry")
    pricing2 = engine.get_oil_change_pricing(vehicle2)
    if pricing2:
        print(
            f"  {vehicle2.display_name()} (Recommended): ${pricing2['final_total']:.2f}"
        )

    print("\n2. Maintenance Services:")
    pricing3 = engine.get_maintenance_service_pricing("Tire Rotation")
    if pricing3:
        print(f"  Tire Rotation: ${pricing3['final_total']:.2f}")


if __name__ == "__main__":
    test_milex_pricing_engine()
