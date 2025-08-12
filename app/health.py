"""
Health check endpoints for JAIMES application.
Provides comprehensive health monitoring for production deployments.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any
import asyncio
import redis
import sqlite3
import os
from config import config

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    environment: str
    checks: Dict[str, Any]

class SimpleHealthResponse(BaseModel):
    status: str
    timestamp: datetime

async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity and performance."""
    try:
        start_time = datetime.now()
        client = redis.from_url(config.redis_url, decode_responses=True)
        
        # Test basic connectivity
        await asyncio.to_thread(client.ping)
        
        # Test write/read performance
        test_key = "health_check_test"
        await asyncio.to_thread(client.set, test_key, "test_value", ex=5)
        result = await asyncio.to_thread(client.get, test_key)
        await asyncio.to_thread(client.delete, test_key)
        
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "write_read_test": "passed" if result == "test_value" else "failed"
        }
    except redis.ConnectionError as e:
        return {
            "status": "unhealthy", 
            "error": f"Connection failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": f"Unexpected error: {str(e)}"
        }

async def check_databases() -> Dict[str, Any]:
    """Check SQLite databases health."""
    checks = {}
    
    # Check analytics database
    try:
        conn = sqlite3.connect("conversation_analytics.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]
        conn.close()
        
        checks["analytics_db"] = {
            "status": "healthy",
            "event_count": event_count
        }
    except Exception as e:
        checks["analytics_db"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check pricing cache database  
    try:
        conn = sqlite3.connect("vehicle_pricing_cache.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM price_cache")
        cache_count = cursor.fetchone()[0]
        conn.close()
        
        checks["pricing_cache_db"] = {
            "status": "healthy", 
            "cached_entries": cache_count
        }
    except Exception as e:
        checks["pricing_cache_db"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    return checks

async def check_external_apis() -> Dict[str, Any]:
    """Check external API connectivity (lightweight checks)."""
    checks = {}
    
    # For now, we'll do basic DNS resolution checks
    # In a full implementation, you'd do actual API health checks
    
    checks["groq_api"] = {
        "status": "unknown", 
        "reason": "Lightweight check - API key present",
        "configured": bool(config.groq_api_key)
    }
    
    checks["vapi_api"] = {
        "status": "unknown",
        "reason": "Lightweight check - API key present", 
        "configured": bool(config.vapi_api_key)
    }
    
    checks["vehicle_db_api"] = {
        "status": "unknown",
        "reason": "Lightweight check - API key present",
        "configured": bool(config.vehicle_db_api_key)
    }
    
    return checks

async def check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        statvfs = os.statvfs('.')
        free_bytes = statvfs.f_frsize * statvfs.f_bavail
        total_bytes = statvfs.f_frsize * statvfs.f_blocks
        free_gb = free_bytes / (1024**3)
        total_gb = total_bytes / (1024**3)
        usage_percent = ((total_bytes - free_bytes) / total_bytes) * 100
        
        status = "healthy"
        if usage_percent > 90:
            status = "critical"
        elif usage_percent > 80:
            status = "warning"
            
        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "usage_percent": round(usage_percent, 1)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.
    Returns detailed system health information.
    """
    checks = {
        "redis": await check_redis(),
        "databases": await check_databases(),
        "external_apis": await check_external_apis(),
        "disk_space": await check_disk_space()
    }
    
    # Determine overall status
    overall_status = "healthy"
    critical_issues = 0
    warning_issues = 0
    
    for check_name, check_result in checks.items():
        if isinstance(check_result, dict):
            if check_result.get("status") == "unhealthy" or check_result.get("status") == "critical":
                critical_issues += 1
            elif check_result.get("status") == "warning":
                warning_issues += 1
        else:
            # Handle nested checks (like databases)
            for sub_check in check_result.values():
                if isinstance(sub_check, dict):
                    if sub_check.get("status") == "unhealthy" or sub_check.get("status") == "critical":
                        critical_issues += 1
                    elif sub_check.get("status") == "warning":
                        warning_issues += 1
    
    if critical_issues > 0:
        overall_status = "unhealthy"
    elif warning_issues > 0:
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",  # TODO: Get from package metadata
        environment=config.environment,
        checks=checks
    )

@router.get("/health/live", response_model=SimpleHealthResponse)
async def liveness_check():
    """
    Simple liveness check for container orchestration.
    Returns 200 if the application is running.
    """
    return SimpleHealthResponse(
        status="alive",
        timestamp=datetime.utcnow()
    )

@router.get("/health/ready", response_model=SimpleHealthResponse)
async def readiness_check():
    """
    Readiness check to ensure service can handle requests.
    Checks critical dependencies before marking as ready.
    """
    # Check critical dependencies
    redis_check = await check_redis()
    
    if redis_check["status"] == "unhealthy":
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "not ready", 
                "reason": "redis unavailable",
                "redis_error": redis_check.get("error")
            }
        )
    
    # Check if databases are accessible
    db_checks = await check_databases()
    analytics_status = db_checks.get("analytics_db", {}).get("status")
    
    if analytics_status == "unhealthy":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not ready",
                "reason": "analytics database unavailable"
            }
        )
    
    return SimpleHealthResponse(
        status="ready",
        timestamp=datetime.utcnow()
    )

@router.get("/health/metrics")
async def health_metrics():
    """
    Health metrics endpoint for monitoring systems.
    Returns metrics in a format suitable for Prometheus or similar.
    """
    redis_check = await check_redis()
    db_checks = await check_databases()
    disk_check = await check_disk_space()
    
    # Simple metrics format
    metrics = {
        "jaimes_redis_healthy": 1 if redis_check["status"] == "healthy" else 0,
        "jaimes_redis_latency_ms": redis_check.get("latency_ms", 0),
        "jaimes_analytics_events_total": db_checks.get("analytics_db", {}).get("event_count", 0),
        "jaimes_pricing_cache_entries_total": db_checks.get("pricing_cache_db", {}).get("cached_entries", 0),
        "jaimes_disk_usage_percent": disk_check.get("usage_percent", 0),
        "jaimes_disk_free_gb": disk_check.get("free_gb", 0),
    }
    
    return metrics
