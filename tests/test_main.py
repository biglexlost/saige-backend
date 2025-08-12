"""
Main application tests for JAIMES.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


class TestHealthAndBasicEndpoints:
    """Test basic application endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns success."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "JAIMES AI Executive is running!"}
    
    def test_application_startup(self, client):
        """Test application starts successfully."""
        # Just testing that the app initializes without crashing
        assert client is not None


class TestChatCompletions:
    """Test the main chat completions endpoint."""
    
    @patch('main.jaimes')
    def test_chat_completions_requires_valid_payload(self, mock_jaimes, client):
        """Test chat completions endpoint validates payload."""
        response = client.post("/chat/completions", json={})
        assert response.status_code == 422  # Validation error
        
    @patch('main.jaimes')
    def test_chat_completions_handles_missing_jaimes(self, mock_jaimes, client):
        """Test graceful handling when JAIMES system is unavailable."""
        # Set jaimes to None to simulate initialization failure
        with patch('main.jaimes', None):
            payload = {
                "model": "test",
                "messages": [{"role": "user", "content": "Hello"}],
                "temperature": 0.7,
                "call": {"id": "test-call-id"},
                "timestamp": 1234567890.0,
                "stream": True
            }
            response = client.post("/chat/completions", json=payload)
            assert response.status_code == 503
            assert "JAIMES system not available" in response.json()["detail"]
    
    @patch('main.jaimes')
    def test_chat_completions_extracts_session_id(self, mock_jaimes, client):
        """Test session ID extraction from call data."""
        mock_jaimes_instance = MagicMock()
        mock_jaimes_instance.get_session.return_value = MagicMock()
        
        # Mock the async generator for streaming
        async def mock_stream():
            yield "Test response"
        
        mock_jaimes_instance.start_conversation.return_value = mock_stream()
        mock_jaimes.return_value = mock_jaimes_instance
        
        payload = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "call": {"id": "test-session-123"},
            "customer": {"number": "+1234567890"},
            "metadata": {"numAssistantTurns": 0, "numUserTurns": 0},
            "timestamp": 1234567890.0,
            "stream": True
        }
        
        response = client.post("/chat/completions", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


class TestSessionManagement:
    """Test session management endpoints."""
    
    @patch('main.jaimes')
    def test_get_session_success(self, mock_jaimes, client, sample_session):
        """Test successful session retrieval."""
        mock_jaimes.get_session.return_value = sample_session
        
        response = client.get("/sessions/test-session-123")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["caller_phone"] == "1234567890"
    
    @patch('main.jaimes')
    def test_get_session_not_found(self, mock_jaimes, client):
        """Test session not found handling."""
        mock_jaimes.get_session.return_value = None
        
        response = client.get("/sessions/non-existent-session")
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]
    
    @patch('main.jaimes')
    def test_get_session_jaimes_unavailable(self, mock_jaimes, client):
        """Test session endpoint when JAIMES unavailable."""
        with patch('main.jaimes', None):
            response = client.get("/sessions/test-session")
            assert response.status_code == 503


class TestErrorHandling:
    """Test error handling throughout the application."""
    
    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payload."""
        response = client.post(
            "/chat/completions", 
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_required_headers(self, client):
        """Test handling of missing Content-Type header."""
        response = client.post("/chat/completions", data="{}")
        # Should still be handled gracefully
        assert response.status_code in [422, 415]  # Unprocessable Entity or Unsupported Media Type
    
    @patch('main.jaimes')
    def test_internal_server_error_handling(self, mock_jaimes, client):
        """Test internal server error handling."""
        mock_jaimes.get_session.side_effect = Exception("Database connection failed")
        
        response = client.get("/sessions/test-session")
        # Should handle the exception gracefully
        assert response.status_code == 500


class TestStreamingResponse:
    """Test streaming response functionality."""
    
    @patch('main.jaimes')
    def test_streaming_response_format(self, mock_jaimes, client):
        """Test streaming response format matches expected SSE format."""
        mock_jaimes_instance = MagicMock()
        
        # Mock streaming generator
        async def mock_stream():
            yield "Hello"
            yield " world"
        
        mock_jaimes_instance.start_conversation.return_value = mock_stream()
        mock_jaimes.return_value = mock_jaimes_instance
        
        payload = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "call": {"id": "test-session"},
            "customer": {"number": "+1234567890"},
            "metadata": {"numAssistantTurns": 0, "numUserTurns": 0},
            "timestamp": 1234567890.0,
            "stream": True
        }
        
        response = client.post("/chat/completions", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Check that response is streaming
        content = response.content.decode()
        assert "data:" in content  # SSE format
