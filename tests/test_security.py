"""
Security-focused tests for JAIMES application.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


class TestCORSSecurity:
    """Test CORS security configuration."""
    
    def test_cors_policy_dev_environment(self, client):
        """Test CORS allows localhost in DEV environment."""
        with patch('config.config.environment', 'DEV'):
            response = client.options("/", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            })
            assert response.status_code == 200
            assert "Access-Control-Allow-Origin" in response.headers
    
    def test_cors_policy_prod_environment(self, client):
        """Test CORS restricts to VAPI domains in PROD."""
        with patch('config.config.environment', 'PROD'):
            # Test allowed origin
            response = client.options("/", headers={
                "Origin": "https://dashboard.vapi.ai",
                "Access-Control-Request-Method": "POST"
            })
            assert response.status_code == 200
            
    def test_cors_blocks_unauthorized_origins(self, client):
        """Test CORS blocks unauthorized origins."""
        response = client.options("/", headers={
            "Origin": "https://malicious-site.com",
            "Access-Control-Request-Method": "POST"
        })
        # Should not have CORS headers for unauthorized origin
        assert response.status_code == 400 or "Access-Control-Allow-Origin" not in response.headers


class TestSecurityHeaders:
    """Test security headers are properly set."""
    
    def test_security_headers_present(self, client):
        """Test that all required security headers are present."""
        response = client.get("/")
        
        # Check critical security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    
    def test_hsts_header_in_prod(self, client):
        """Test HSTS header is set in production environment."""
        with patch('config.config.environment', 'PROD'):
            response = client.get("/")
            assert "Strict-Transport-Security" in response.headers
    
    def test_no_hsts_in_dev(self, client):
        """Test HSTS header is not set in development."""
        with patch('config.config.environment', 'DEV'):
            response = client.get("/")
            assert "Strict-Transport-Security" not in response.headers


class TestConfigurationSecurity:
    """Test configuration security."""
    
    def test_secrets_are_secure_strings(self):
        """Test that API keys are stored as SecretStr."""
        import os
        from config import Config
        from pydantic import SecretStr
        
        # Create a test config with environment variables
        test_env = {
            "VAPI_API_KEY": "test-vapi-key",
            "GROQ_API_KEY": "test-groq-key", 
            "GROQ_MODEL": "test-model",
            "REDIS_URL": "redis://localhost:6379"
        }
        
        # Temporarily set environment variables
        original_env = {}
        for key, value in test_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            # Create fresh config instance
            test_config = Config()
            
            # Test that sensitive fields are SecretStr types
            assert isinstance(test_config.vapi_api_key, SecretStr)
            assert isinstance(test_config.groq_api_key, SecretStr)
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    
    def test_secrets_not_exposed_in_repr(self):
        """Test that secrets are not exposed in string representation."""
        from config import config
        
        config_str = str(config)
        config_repr = repr(config)
        
        # Should not contain actual API key values
        assert "test-groq-key" not in config_str
        assert "test-vapi-key" not in config_str
        assert "test-groq-key" not in config_repr
        assert "test-vapi-key" not in config_repr


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_chat_completions_validates_payload(self, client):
        """Test that chat completions endpoint validates payload."""
        # Empty payload should be rejected
        response = client.post("/chat/completions", json={})
        assert response.status_code == 422  # Validation error
        
    def test_chat_completions_validates_required_fields(self, client):
        """Test required fields validation."""
        invalid_payload = {
            "model": "test",
            # missing required fields
        }
        response = client.post("/chat/completions", json=invalid_payload)
        assert response.status_code == 422
        
    @patch('main.jaimes')
    def test_handles_missing_jaimes_gracefully(self, mock_jaimes, client):
        """Test graceful handling when JAIMES system is unavailable."""
        mock_jaimes = None
        
        payload = {
            "model": "test",
            "messages": [],
            "temperature": 0.7,
            "call": {"id": "test"},
            "timestamp": 1234567890,
            "stream": True
        }
        response = client.post("/chat/completions", json=payload)
        assert response.status_code == 503  # Service unavailable


class TestSessionSecurity:
    """Test session security."""
    
    def test_session_id_validation(self, client):
        """Test session ID validation."""
        # Test invalid session ID
        response = client.get("/sessions/invalid-session-id-with-special-chars@#$")
        # Should handle gracefully (404 or validation error)
        assert response.status_code in [404, 422]
    
    @patch('main.jaimes')
    def test_session_not_found_handling(self, mock_jaimes, client):
        """Test handling of non-existent sessions."""
        mock_jaimes.get_session.return_value = None
        
        response = client.get("/sessions/non-existent-session")
        assert response.status_code == 404
