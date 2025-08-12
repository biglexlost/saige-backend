#!/usr/bin/env python3
"""
Smart Pricing Manager
Implements intelligent price refresh logic and database optimization
Manages both Vehicle Database API cache and MileX custom pricing
"""

import asyncio
import sqlite3
import json
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor
import statistics

from vehicle_database_api_client import (
    VehicleDatabaseAPIClient,
    VehicleInfo,
    PriceValidityPeriod,
)
from milex_pricing_engine import MileXPricingEngine, OilType

logger = logging.getLogger(__name__)


class PriceRefreshStrategy(Enum):
    """Price refresh strategies"""

    IMMEDIATE = "immediate"  # Refresh immediately when expired
    SCHEDULED = "scheduled"  # Refresh during scheduled maintenance windows
    DEMAND_BASED = "demand_based"  # Refresh based on request frequency
    PREDICTIVE = "predictive"  # Refresh based on predicted demand


class MarketCondition(Enum):
    """Market condition indicators"""

    STABLE = "stable"
    VOLATILE = "volatile"
    SEASONAL_HIGH = "seasonal_high"
    SEASONAL_LOW = "seasonal_low"
    EMERGENCY = "emergency"


@dataclass
class PriceAnalytics:
    """Price analytics and trends"""

    service_name: str
    average_price: float
    price_trend: str  # "increasing", "decreasing", "stable"
    volatility_score: float
    request_frequency: int
    last_updated: datetime
    confidence_score: float


@dataclass
class RefreshJob:
    """Price refresh job"""

    job_id: str
    vehicle_info: VehicleInfo
    repair_description: str
    zip_code: str
    priority: int
    scheduled_time: datetime
    strategy: PriceRefreshStrategy
    retry_count: int = 0
    max_retries: int = 3


class SmartPricingManager:
    """Smart pricing manager with intelligent refresh logic"""

    def __init__(
        self,
        vehicle_api_client: VehicleDatabaseAPIClient,
        milex_engine: MileXPricingEngine,
        analytics_db_path: str = "pricing_analytics.db",
    ):
        self.vehicle_api = vehicle_api_client
        self.milex_engine = milex_engine
        self.analytics_db_path = analytics_db_path

        # Initialize analytics database
        self._init_analytics_database()

        # Refresh job queue
        self.refresh_queue: List[RefreshJob] = []
        self.queue_lock = threading.Lock()

        # Background scheduler
        self.scheduler_running = False
        self.scheduler_thread: Optional[threading.Thread] = None

        # Market condition tracking
        self.current_market_condition = MarketCondition.STABLE

        # Performance metrics
        self.performance_metrics = {
            "cache_hit_rate": 0.0,
            "api_cost_savings": 0.0,
            "average_response_time": 0.0,
            "refresh_success_rate": 0.0,
        }

        logger.info("Smart Pricing Manager initialized")

    def _init_analytics_database(self):
        """Initialize pricing analytics database"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            # Price history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_hash TEXT NOT NULL,
                    repair_hash TEXT NOT NULL,
                    zip_code TEXT NOT NULL,
                    price REAL NOT NULL,
                    source TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    market_condition TEXT
                )
            """
            )

            # Request frequency tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS request_frequency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_hash TEXT NOT NULL,
                    repair_hash TEXT NOT NULL,
                    zip_code TEXT NOT NULL,
                    request_count INTEGER DEFAULT 1,
                    last_request TIMESTAMP NOT NULL,
                    hour_of_day INTEGER,
                    day_of_week INTEGER,
                    UNIQUE(vehicle_hash, repair_hash, zip_code, hour_of_day, day_of_week)
                )
            """
            )

            # Price volatility tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_volatility (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repair_category TEXT NOT NULL,
                    zip_code TEXT NOT NULL,
                    volatility_score REAL NOT NULL,
                    calculated_at TIMESTAMP NOT NULL,
                    sample_size INTEGER,
                    UNIQUE(repair_category, zip_code)
                )
            """
            )

            # Refresh job history
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    vehicle_hash TEXT NOT NULL,
                    repair_hash TEXT NOT NULL,
                    zip_code TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    scheduled_time TIMESTAMP NOT NULL,
                    executed_time TIMESTAMP,
                    success BOOLEAN,
                    error_message TEXT,
                    execution_time_ms INTEGER
                )
            """
            )

            # Performance metrics
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    recorded_at TIMESTAMP NOT NULL
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_performance_metrics_lookup 
                    ON performance_metrics(metric_name, recorded_at)
            """
            )

            conn.commit()
            conn.close()

            logger.info("Analytics database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize analytics database: {str(e)}")
            raise

    def track_price_request(
        self,
        vehicle_info: VehicleInfo,
        repair_description: str,
        zip_code: str,
        price: Optional[float] = None,
        source: str = "cache",
    ):
        """Track price request for analytics"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            vehicle_hash = self.vehicle_api._generate_vehicle_hash(vehicle_info)
            repair_hash = self.vehicle_api._generate_repair_hash(repair_description)
            now = datetime.now()

            # Track request frequency
            cursor.execute(
                """
                INSERT OR IGNORE INTO request_frequency 
                (vehicle_hash, repair_hash, zip_code, request_count, last_request, hour_of_day, day_of_week)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
                (vehicle_hash, repair_hash, zip_code, now, now.hour, now.weekday()),
            )

            cursor.execute(
                """
                UPDATE request_frequency 
                SET request_count = request_count + 1, last_request = ?
                WHERE vehicle_hash = ? AND repair_hash = ? AND zip_code = ? 
                AND hour_of_day = ? AND day_of_week = ?
            """,
                (now, vehicle_hash, repair_hash, zip_code, now.hour, now.weekday()),
            )

            # Track price history if price provided
            if price is not None:
                cursor.execute(
                    """
                    INSERT INTO price_history 
                    (vehicle_hash, repair_hash, zip_code, price, source, timestamp, market_condition)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        vehicle_hash,
                        repair_hash,
                        zip_code,
                        price,
                        source,
                        now,
                        self.current_market_condition.value,
                    ),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error tracking price request: {str(e)}")

    def calculate_price_volatility(
        self, repair_category: str, zip_code: str, days_back: int = 30
    ) -> float:
        """Calculate price volatility for a repair category"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            # Get price history for the category
            since_date = datetime.now() - timedelta(days=days_back)
            cursor.execute(
                """
                SELECT price FROM price_history 
                WHERE repair_hash IN (
                    SELECT DISTINCT repair_hash FROM price_history 
                    WHERE timestamp >= ? AND zip_code = ?
                ) AND zip_code = ? AND timestamp >= ?
                ORDER BY timestamp
            """,
                (since_date, zip_code, zip_code, since_date),
            )

            prices = [row[0] for row in cursor.fetchall()]
            conn.close()

            if len(prices) < 3:
                return 0.0  # Not enough data

            # Calculate coefficient of variation as volatility measure
            mean_price = statistics.mean(prices)
            std_dev = statistics.stdev(prices)
            volatility = (std_dev / mean_price) * 100 if mean_price > 0 else 0.0

            # Update volatility tracking
            self._update_volatility_tracking(
                repair_category, zip_code, volatility, len(prices)
            )

            return volatility

        except Exception as e:
            logger.error(f"Error calculating price volatility: {str(e)}")
            return 0.0

    def _update_volatility_tracking(
        self, repair_category: str, zip_code: str, volatility: float, sample_size: int
    ):
        """Update volatility tracking in database"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO price_volatility 
                (repair_category, zip_code, volatility_score, calculated_at, sample_size)
                VALUES (?, ?, ?, ?, ?)
            """,
                (repair_category, zip_code, volatility, datetime.now(), sample_size),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating volatility tracking: {str(e)}")

    def predict_demand(
        self, vehicle_info: VehicleInfo, repair_description: str, zip_code: str
    ) -> Tuple[float, str]:
        """Predict demand for a specific repair based on historical patterns"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            vehicle_hash = self.vehicle_api._generate_vehicle_hash(vehicle_info)
            repair_hash = self.vehicle_api._generate_repair_hash(repair_description)
            now = datetime.now()

            # Get historical request patterns
            cursor.execute(
                """
                SELECT request_count, hour_of_day, day_of_week 
                FROM request_frequency 
                WHERE vehicle_hash = ? AND repair_hash = ? AND zip_code = ?
            """,
                (vehicle_hash, repair_hash, zip_code),
            )

            patterns = cursor.fetchall()
            conn.close()

            if not patterns:
                return 0.1, "low"  # Default low demand for new requests

            # Calculate demand score based on current time patterns
            current_hour = now.hour
            current_day = now.weekday()

            relevant_patterns = [
                count
                for count, hour, day in patterns
                if abs(hour - current_hour) <= 2 and day == current_day
            ]

            if relevant_patterns:
                avg_demand = statistics.mean(relevant_patterns)
                max_demand = max(count for count, _, _ in patterns)
                demand_score = avg_demand / max_demand if max_demand > 0 else 0.1
            else:
                # Fallback to overall average
                avg_demand = statistics.mean([count for count, _, _ in patterns])
                demand_score = min(avg_demand / 10.0, 1.0)  # Normalize to 0-1

            # Classify demand level
            if demand_score >= 0.7:
                demand_level = "high"
            elif demand_score >= 0.4:
                demand_level = "medium"
            else:
                demand_level = "low"

            return demand_score, demand_level

        except Exception as e:
            logger.error(f"Error predicting demand: {str(e)}")
            return 0.1, "low"

    def determine_refresh_strategy(
        self, vehicle_info: VehicleInfo, repair_description: str, zip_code: str
    ) -> PriceRefreshStrategy:
        """Determine optimal refresh strategy for a price request"""
        try:
            # Get demand prediction
            demand_score, demand_level = self.predict_demand(
                vehicle_info, repair_description, zip_code
            )

            # Get price volatility
            repair_category = self.vehicle_api._categorize_repair(repair_description)
            volatility = self.calculate_price_volatility(repair_category, zip_code)

            # Determine strategy based on demand and volatility
            if demand_level == "high" and volatility > 15.0:
                return PriceRefreshStrategy.IMMEDIATE
            elif demand_level == "high" or volatility > 10.0:
                return PriceRefreshStrategy.DEMAND_BASED
            elif volatility > 5.0:
                return PriceRefreshStrategy.PREDICTIVE
            else:
                return PriceRefreshStrategy.SCHEDULED

        except Exception as e:
            logger.error(f"Error determining refresh strategy: {str(e)}")
            return PriceRefreshStrategy.SCHEDULED

    def schedule_price_refresh(
        self,
        vehicle_info: VehicleInfo,
        repair_description: str,
        zip_code: str,
        strategy: Optional[PriceRefreshStrategy] = None,
    ) -> str:
        """Schedule a price refresh job"""
        try:
            if strategy is None:
                strategy = self.determine_refresh_strategy(
                    vehicle_info, repair_description, zip_code
                )

            # Generate job ID
            job_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash((vehicle_info.year, vehicle_info.make, vehicle_info.model, repair_description))}"

            # Determine scheduling time based on strategy
            now = datetime.now()
            if strategy == PriceRefreshStrategy.IMMEDIATE:
                scheduled_time = now
                priority = 1
            elif strategy == PriceRefreshStrategy.DEMAND_BASED:
                scheduled_time = now + timedelta(minutes=5)
                priority = 2
            elif strategy == PriceRefreshStrategy.PREDICTIVE:
                scheduled_time = now + timedelta(hours=1)
                priority = 3
            else:  # SCHEDULED
                # Schedule during off-peak hours (2-4 AM)
                next_maintenance = now.replace(
                    hour=2, minute=0, second=0, microsecond=0
                )
                if next_maintenance <= now:
                    next_maintenance += timedelta(days=1)
                scheduled_time = next_maintenance
                priority = 4

            # Create refresh job
            refresh_job = RefreshJob(
                job_id=job_id,
                vehicle_info=vehicle_info,
                repair_description=repair_description,
                zip_code=zip_code,
                priority=priority,
                scheduled_time=scheduled_time,
                strategy=strategy,
            )

            # Add to queue
            with self.queue_lock:
                self.refresh_queue.append(refresh_job)
                self.refresh_queue.sort(key=lambda x: (x.priority, x.scheduled_time))

            # Log the job
            self._log_refresh_job(refresh_job)

            logger.info(
                f"Scheduled price refresh job {job_id} with strategy {strategy.value}"
            )
            return job_id

        except Exception as e:
            logger.error(f"Error scheduling price refresh: {str(e)}")
            return ""

    def _log_refresh_job(self, job: RefreshJob):
        """Log refresh job to database"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            vehicle_hash = self.vehicle_api._generate_vehicle_hash(job.vehicle_info)
            repair_hash = self.vehicle_api._generate_repair_hash(job.repair_description)

            cursor.execute(
                """
                INSERT INTO refresh_jobs 
                (job_id, vehicle_hash, repair_hash, zip_code, strategy, scheduled_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    job.job_id,
                    vehicle_hash,
                    repair_hash,
                    job.zip_code,
                    job.strategy.value,
                    job.scheduled_time,
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error logging refresh job: {str(e)}")

    async def execute_refresh_job(self, job: RefreshJob) -> bool:
        """Execute a price refresh job"""
        start_time = datetime.now()
        success = False
        error_message = None

        try:
            logger.info(f"Executing refresh job {job.job_id}")

            # Force refresh the price
            estimate = await self.vehicle_api.get_repair_estimate(
                job.vehicle_info,
                job.repair_description,
                job.zip_code,
                force_refresh=True,
            )

            if estimate:
                # Track the new price
                self.track_price_request(
                    job.vehicle_info,
                    job.repair_description,
                    job.zip_code,
                    estimate.total_estimate,
                    "api_refresh",
                )
                success = True
                logger.info(f"Successfully refreshed price for job {job.job_id}")
            else:
                error_message = "API request failed"
                logger.error(f"Failed to refresh price for job {job.job_id}")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error executing refresh job {job.job_id}: {error_message}")

        # Log execution result
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        self._log_job_execution(job, success, error_message, int(execution_time))

        return success

    def _log_job_execution(
        self,
        job: RefreshJob,
        success: bool,
        error_message: Optional[str],
        execution_time_ms: int,
    ):
        """Log job execution result"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            vehicle_hash = self.vehicle_api._generate_vehicle_hash(job.vehicle_info)
            repair_hash = self.vehicle_api._generate_repair_hash(job.repair_description)

            cursor.execute(
                """
                UPDATE refresh_jobs 
                SET executed_time = ?, success = ?, error_message = ?, execution_time_ms = ?
                WHERE job_id = ?
            """,
                (datetime.now(), success, error_message, execution_time_ms, job.job_id),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error logging job execution: {str(e)}")

    def start_background_scheduler(self):
        """Start background scheduler for price refresh jobs"""
        if self.scheduler_running:
            return

        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()

        logger.info("Background scheduler started")

    def stop_background_scheduler(self):
        """Stop background scheduler"""
        self.scheduler_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        logger.info("Background scheduler stopped")

    def _scheduler_loop(self):
        """Background scheduler loop"""
        while self.scheduler_running:
            try:
                now = datetime.now()
                jobs_to_execute = []

                # Find jobs ready for execution
                with self.queue_lock:
                    jobs_to_execute = [
                        job for job in self.refresh_queue if job.scheduled_time <= now
                    ]

                    # Remove executed jobs from queue
                    self.refresh_queue = [
                        job for job in self.refresh_queue if job.scheduled_time > now
                    ]

                # Execute jobs
                if jobs_to_execute:
                    asyncio.run(self._execute_jobs_batch(jobs_to_execute))

                # Clean up old completed jobs
                self._cleanup_old_jobs()

                # Update performance metrics
                self._update_performance_metrics()

                # Sleep for 30 seconds before next check
                time.sleep(30)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)  # Wait longer on error

    async def _execute_jobs_batch(self, jobs: List[RefreshJob]):
        """Execute a batch of refresh jobs"""
        with ThreadPoolExecutor(max_workers=5) as executor:
            tasks = []
            for job in jobs:
                task = asyncio.create_task(self.execute_refresh_job(job))
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

    def _cleanup_old_jobs(self):
        """Clean up old job records"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            # Delete job records older than 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            cursor.execute(
                "DELETE FROM refresh_jobs WHERE scheduled_time < ?", (cutoff_date,)
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {str(e)}")

    def _update_performance_metrics(self):
        """Update performance metrics"""
        try:
            # Get cache statistics
            cache_stats = asyncio.run(self.vehicle_api.get_cache_statistics())

            # Update metrics
            self.performance_metrics.update(
                {
                    "cache_hit_rate": cache_stats.get("cache_hit_ratio", 0.0),
                    "api_cost_savings": cache_stats.get("estimated_cost_saved", 0.0),
                }
            )

            # Log metrics to database
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            now = datetime.now()
            for metric_name, metric_value in self.performance_metrics.items():
                cursor.execute(
                    """
                    INSERT INTO performance_metrics (metric_name, metric_value, recorded_at)
                    VALUES (?, ?, ?)
                """,
                    (metric_name, metric_value, now),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating performance metrics: {str(e)}")

    def get_pricing_analytics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive pricing analytics"""
        try:
            conn = sqlite3.connect(self.analytics_db_path)
            cursor = conn.cursor()

            since_date = datetime.now() - timedelta(days=days_back)

            # Get request frequency stats
            cursor.execute(
                """
                SELECT COUNT(*) as total_requests, 
                       AVG(request_count) as avg_frequency,
                       MAX(request_count) as max_frequency
                FROM request_frequency 
                WHERE last_request >= ?
            """,
                (since_date,),
            )

            request_stats = cursor.fetchone()

            # Get price volatility stats
            cursor.execute(
                """
                SELECT AVG(volatility_score) as avg_volatility,
                       MAX(volatility_score) as max_volatility,
                       COUNT(*) as categories_tracked
                FROM price_volatility
            """
            )

            volatility_stats = cursor.fetchone()

            # Get job execution stats
            cursor.execute(
                """
                SELECT COUNT(*) as total_jobs,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_jobs,
                       AVG(execution_time_ms) as avg_execution_time
                FROM refresh_jobs 
                WHERE scheduled_time >= ?
            """,
                (since_date,),
            )

            job_stats = cursor.fetchone()

            conn.close()

            # Calculate success rate
            total_jobs, successful_jobs, avg_execution_time = job_stats
            success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0

            return {
                "period_days": days_back,
                "request_analytics": {
                    "total_requests": request_stats[0] or 0,
                    "average_frequency": round(request_stats[1] or 0, 2),
                    "max_frequency": request_stats[2] or 0,
                },
                "volatility_analytics": {
                    "average_volatility": round(volatility_stats[0] or 0, 2),
                    "max_volatility": round(volatility_stats[1] or 0, 2),
                    "categories_tracked": volatility_stats[2] or 0,
                },
                "job_execution": {
                    "total_jobs": total_jobs or 0,
                    "successful_jobs": successful_jobs or 0,
                    "success_rate": round(success_rate, 2),
                    "avg_execution_time_ms": round(avg_execution_time or 0, 2),
                },
                "performance_metrics": self.performance_metrics,
            }

        except Exception as e:
            logger.error(f"Error getting pricing analytics: {str(e)}")
            return {}

    def optimize_cache_settings(self) -> Dict[str, Any]:
        """Optimize cache settings based on analytics"""
        try:
            analytics = self.get_pricing_analytics()

            recommendations = {
                "current_hit_rate": analytics["performance_metrics"]["cache_hit_rate"],
                "recommendations": [],
            }

            hit_rate = analytics["performance_metrics"]["cache_hit_rate"]
            avg_volatility = analytics["volatility_analytics"]["average_volatility"]

            # Recommend cache duration adjustments
            if hit_rate < 70:
                recommendations["recommendations"].append(
                    {
                        "type": "increase_cache_duration",
                        "reason": "Low cache hit rate suggests cache expires too quickly",
                        "suggested_action": "Increase cache duration for stable repairs by 25%",
                    }
                )

            if avg_volatility > 15:
                recommendations["recommendations"].append(
                    {
                        "type": "decrease_volatile_cache",
                        "reason": "High price volatility detected",
                        "suggested_action": "Reduce cache duration for volatile repairs to 3-5 days",
                    }
                )

            if analytics["job_execution"]["success_rate"] < 90:
                recommendations["recommendations"].append(
                    {
                        "type": "improve_refresh_reliability",
                        "reason": "Low refresh job success rate",
                        "suggested_action": "Implement retry logic and error handling improvements",
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error optimizing cache settings: {str(e)}")
            return {}


# Example usage and testing
async def test_smart_pricing_manager():
    """Test the smart pricing manager"""

    # Initialize components
    api_key = "test_api_key"
    vehicle_api = VehicleDatabaseAPIClient(api_key)
    milex_engine = MileXPricingEngine()
    pricing_manager = SmartPricingManager(vehicle_api, milex_engine)

    try:
        # Start background scheduler
        pricing_manager.start_background_scheduler()

        # Test vehicle
        vehicle = VehicleInfo(
            year=2018, make="Ford", model="F-150", engine_size="5.0L V8"
        )

        repair = "Brake pad replacement"
        zip_code = "27701"

        print("Testing Smart Pricing Manager:")
        print("=" * 50)

        # Track some requests
        for i in range(5):
            pricing_manager.track_price_request(
                vehicle, repair, zip_code, 250.0 + i * 10, "test"
            )
            await asyncio.sleep(0.1)

        # Test demand prediction
        demand_score, demand_level = pricing_manager.predict_demand(
            vehicle, repair, zip_code
        )
        print(f"Demand Prediction: {demand_score:.2f} ({demand_level})")

        # Test volatility calculation
        volatility = pricing_manager.calculate_price_volatility("brakes", zip_code)
        print(f"Price Volatility: {volatility:.2f}%")

        # Test refresh strategy determination
        strategy = pricing_manager.determine_refresh_strategy(vehicle, repair, zip_code)
        print(f"Recommended Strategy: {strategy.value}")

        # Schedule a refresh job
        job_id = pricing_manager.schedule_price_refresh(vehicle, repair, zip_code)
        print(f"Scheduled Job: {job_id}")

        # Wait a bit for background processing
        await asyncio.sleep(2)

        # Get analytics
        analytics = pricing_manager.get_pricing_analytics()
        print("\nAnalytics:")
        for key, value in analytics.items():
            print(f"  {key}: {value}")

        # Get optimization recommendations
        recommendations = pricing_manager.optimize_cache_settings()
        print(
            f"\nOptimization Recommendations: {len(recommendations.get('recommendations', []))}"
        )

    finally:
        pricing_manager.stop_background_scheduler()
        await vehicle_api.close()


if __name__ == "__main__":
    asyncio.run(test_smart_pricing_manager())
