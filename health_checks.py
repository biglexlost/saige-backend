#!/usr/bin/env python3
"""
Health Check System for JAIMES AI Executive
Provides comprehensive health monitoring for all system components
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import redis.exceptions
from groq import AsyncGroq

logger = structlog.get_logger(__name__)

class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class ComponentHealth:
    """Health status for individual component"""
    name: str
    status: HealthStatus
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    last_check: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "last_check": self.last_check,
            "details": self.details or {}
        }

@dataclass
class SystemHealth:
    """Overall system health status"""
    overall_status: HealthStatus
    components: List[ComponentHealth]
    timestamp: float
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "components": [comp.to_dict() for comp in self.components],
            "timestamp": self.timestamp,
            "version": self.version,
            "healthy_components": len([c for c in self.components if c.status == HealthStatus.HEALTHY]),
            "total_components": len(self.components)
        }

class HealthChecker:
    """Comprehensive health checker for JAIMES system"""
    
    def __init__(self, jaimes_system=None):
        self.jaimes_system = jaimes_system
        self.logger = structlog.get_logger(__name__)
        
    async def check_groq_health(self) -> ComponentHealth:
        """Check Groq API health"""
        start_time = time.time()
        
        try:
            if not self.jaimes_system or not self.jaimes_system.groq_client:
                return ComponentHealth(
                    name="groq_api",
                    status=HealthStatus.UNHEALTHY,
                    error_message="Groq client not initialized",
                    last_check=time.time()
                )
            
            # Simple health check - create a minimal completion
            test_messages = [{"role": "user", "content": "health check"}]
            
            response = await self.jaimes_system.groq_client.chat.completions.create(
                messages=test_messages,
                model=self.jaimes_system.groq_model,
                max_tokens=5
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response and response.choices:
                status = HealthStatus.HEALTHY if response_time < 5000 else HealthStatus.DEGRADED
                return ComponentHealth(
                    name="groq_api",
                    status=status,
                    response_time_ms=response_time,
                    last_check=time.time(),
                    details={"model": self.jaimes_system.groq_model}
                )
            else:
                return ComponentHealth(
                    name="groq_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    error_message="Empty response from Groq API",
                    last_check=time.time()
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="groq_api",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error_message=str(e),
                last_check=time.time()
            )
    
    async def check_redis_health(self) -> ComponentHealth:
        """Check Redis connection health"""
        start_time = time.time()
        
        try:
            if not self.jaimes_system or not self.jaimes_system.redis_client:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    error_message="Redis client not available (using memory fallback)",
                    last_check=time.time()
                )
            
            # Test Redis connection
            await asyncio.to_thread(self.jaimes_system.redis_client.ping)
            response_time = (time.time() - start_time) * 1000
            
            # Get additional Redis info
            info = await asyncio.to_thread(self.jaimes_system.redis_client.info)
            used_memory = info.get('used_memory_human', 'unknown')
            connected_clients = info.get('connected_clients', 'unknown')
            
            status = HealthStatus.HEALTHY if response_time < 100 else HealthStatus.DEGRADED
            
            return ComponentHealth(
                name="redis",
                status=status,
                response_time_ms=response_time,
                last_check=time.time(),
                details={
                    "used_memory": used_memory,
                    "connected_clients": connected_clients
                }
            )
            
        except redis.exceptions.ConnectionError as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error_message=f"Redis connection failed: {e}",
                last_check=time.time()
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error_message=str(e),
                last_check=time.time()
            )
    
    async def check_enhanced_modules_health(self) -> List[ComponentHealth]:
        """Check health of enhanced modules"""
        components = []
        
        # Check accent handler
        try:
            if self.jaimes_system and self.jaimes_system.accent_handler:
                # Simple test of accent handler
                test_input = "hello y'all"
                start_time = time.time()
                result = self.jaimes_system.accent_handler.normalize_speech(test_input)
                response_time = (time.time() - start_time) * 1000
                
                components.append(ComponentHealth(
                    name="accent_handler",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    last_check=time.time(),
                    details={"test_result": result}
                ))
            else:
                components.append(ComponentHealth(
                    name="accent_handler",
                    status=HealthStatus.UNHEALTHY,
                    error_message="Accent handler not initialized",
                    last_check=time.time()
                ))
        except Exception as e:
            components.append(ComponentHealth(
                name="accent_handler",
                status=HealthStatus.UNHEALTHY,
                error_message=str(e),
                last_check=time.time()
            ))
        
        # Check conversation intelligence
        try:
            if self.jaimes_system and self.jaimes_system.conversation_intelligence:
                components.append(ComponentHealth(
                    name="conversation_intelligence",
                    status=HealthStatus.HEALTHY,
                    last_check=time.time(),
                    details={"module": "loaded"}
                ))
            else:
                components.append(ComponentHealth(
                    name="conversation_intelligence",
                    status=HealthStatus.UNHEALTHY,
                    error_message="Conversation intelligence not initialized",
                    last_check=time.time()
                ))
        except Exception as e:
            components.append(ComponentHealth(
                name="conversation_intelligence",
                status=HealthStatus.UNHEALTHY,
                error_message=str(e),
                last_check=time.time()
            ))
        
        # Check streaming manager
        try:
            if self.jaimes_system and self.jaimes_system.streaming_manager:
                components.append(ComponentHealth(
                    name="streaming_manager",
                    status=HealthStatus.HEALTHY,
                    last_check=time.time(),
                    details={"module": "loaded"}
                ))
            else:
                components.append(ComponentHealth(
                    name="streaming_manager",
                    status=HealthStatus.UNHEALTHY,
                    error_message="Streaming manager not initialized",
                    last_check=time.time()
                ))
        except Exception as e:
            components.append(ComponentHealth(
                name="streaming_manager",
                status=HealthStatus.UNHEALTHY,
                error_message=str(e),
                last_check=time.time()
            ))
        
        return components
    
    async def check_system_resources(self) -> ComponentHealth:
        """Check system resource usage"""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (current directory)
            disk = psutil.disk_usage('.')
            disk_percent = (disk.used / disk.total) * 100
            
            # Determine status based on resource usage
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 95:
                status = HealthStatus.UNHEALTHY
            elif cpu_percent > 70 or memory_percent > 70 or disk_percent > 85:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            return ComponentHealth(
                name="system_resources",
                status=status,
                last_check=time.time(),
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_percent": round(disk_percent, 2),
                    "memory_available_gb": round(memory.available / (1024**3), 2)
                }
            )
            
        except ImportError:
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.DEGRADED,
                error_message="psutil not available for resource monitoring",
                last_check=time.time()
            )
        except Exception as e:
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                error_message=str(e),
                last_check=time.time()
            )
    
    async def check_cache_health(self) -> ComponentHealth:
        """Check performance cache health"""
        try:
            if not self.jaimes_system:
                return ComponentHealth(
                    name="performance_cache",
                    status=HealthStatus.UNHEALTHY,
                    error_message="JAIMES system not available",
                    last_check=time.time()
                )
            
            accent_cache_size = len(getattr(self.jaimes_system, '_accent_cache', {}))
            intelligence_cache_size = len(getattr(self.jaimes_system, '_intelligence_cache', {}))
            
            # Warn if caches are getting too large
            total_cache_entries = accent_cache_size + intelligence_cache_size
            
            if total_cache_entries > 500:
                status = HealthStatus.DEGRADED
                message = "Cache sizes are large, consider cleanup"
            elif total_cache_entries > 1000:
                status = HealthStatus.UNHEALTHY
                message = "Cache sizes are critical, cleanup needed"
            else:
                status = HealthStatus.HEALTHY
                message = None
            
            return ComponentHealth(
                name="performance_cache",
                status=status,
                error_message=message,
                last_check=time.time(),
                details={
                    "accent_cache_entries": accent_cache_size,
                    "intelligence_cache_entries": intelligence_cache_size,
                    "total_cache_entries": total_cache_entries
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="performance_cache",
                status=HealthStatus.UNHEALTHY,
                error_message=str(e),
                last_check=time.time()
            )
    
    async def perform_comprehensive_health_check(self) -> SystemHealth:
        """Perform comprehensive health check of all system components"""
        logger.info("Starting comprehensive health check")
        
        # Run all health checks concurrently
        health_checks = await asyncio.gather(
            self.check_groq_health(),
            self.check_redis_health(),
            self.check_system_resources(),
            self.check_cache_health(),
            return_exceptions=True
        )
        
        # Add enhanced modules health checks
        enhanced_modules = await self.check_enhanced_modules_health()
        
        # Combine all health checks
        all_components = []
        
        for result in health_checks:
            if isinstance(result, ComponentHealth):
                all_components.append(result)
            elif isinstance(result, Exception):
                all_components.append(ComponentHealth(
                    name="unknown_component",
                    status=HealthStatus.UNHEALTHY,
                    error_message=str(result),
                    last_check=time.time()
                ))
        
        all_components.extend(enhanced_modules)
        
        # Determine overall system health
        unhealthy_count = len([c for c in all_components if c.status == HealthStatus.UNHEALTHY])
        degraded_count = len([c for c in all_components if c.status == HealthStatus.DEGRADED])
        
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        system_health = SystemHealth(
            overall_status=overall_status,
            components=all_components,
            timestamp=time.time()
        )
        
        logger.info("Health check completed", 
                   overall_status=overall_status.value,
                   healthy_components=len([c for c in all_components if c.status == HealthStatus.HEALTHY]),
                   total_components=len(all_components))
        
        return system_health

# FastAPI endpoints integration
def create_health_endpoints(app, jaimes_system):
    """Add health check endpoints to FastAPI app"""
    from fastapi import HTTPException
    
    health_checker = HealthChecker(jaimes_system)
    
    @app.get("/health")
    async def health_check():
        """Quick health check endpoint"""
        try:
            health = await health_checker.perform_comprehensive_health_check()
            
            if health.overall_status == HealthStatus.UNHEALTHY:
                raise HTTPException(status_code=503, detail=health.to_dict())
            elif health.overall_status == HealthStatus.DEGRADED:
                raise HTTPException(status_code=207, detail=health.to_dict())
            else:
                return health.to_dict()
                
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            raise HTTPException(status_code=500, detail={"error": "Health check failed"})
    
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with full component status"""
        try:
            health = await health_checker.perform_comprehensive_health_check()
            return health.to_dict()
        except Exception as e:
            logger.error("Detailed health check failed", error=str(e))
            raise HTTPException(status_code=500, detail={"error": "Detailed health check failed"})
    
    @app.get("/health/ready")
    async def readiness_check():
        """Kubernetes-style readiness check"""
        try:
            health = await health_checker.perform_comprehensive_health_check()
            
            # System is ready if it's not unhealthy
            if health.overall_status == HealthStatus.UNHEALTHY:
                raise HTTPException(status_code=503, detail={"status": "not_ready"})
            else:
                return {"status": "ready"}
                
        except Exception as e:
            logger.error("Readiness check failed", error=str(e))
            raise HTTPException(status_code=503, detail={"status": "not_ready"})
    
    @app.get("/health/live")
    async def liveness_check():
        """Kubernetes-style liveness check"""
        # Simple liveness check - just verify the app is responding
        return {"status": "alive", "timestamp": time.time()}

if __name__ == "__main__":
    # Simple test
    import asyncio
    
    async def test_health_checker():
        health_checker = HealthChecker()
        health = await health_checker.perform_comprehensive_health_check()
        print("System Health:", health.to_dict())
    
    asyncio.run(test_health_checker())
