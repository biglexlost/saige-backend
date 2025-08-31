"""
Test configuration and shared fixtures for JAIMES testing.
"""
import pytest
import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Set test environment
os.environ["ENVIRONMENT"] = "TEST"
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["VAPI_API_KEY"] = "test-vapi-key"
os.environ["REDIS_URL"] = "redis://localhost:6379"

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch('redis.from_url') as mock_redis_client:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_redis_client.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_groq():
    """Mock Groq client for testing."""
    with patch('groq.AsyncGroq') as mock_groq_client:
        mock_client = MagicMock()
        mock_groq_client.return_value = mock_client
        yield mock_client

@pytest.fixture
def client():
    """FastAPI test client."""
    from main import app
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def sample_session():
    """Sample JAIMES session for testing."""
    from models import SAIGESession, ConversationState
    from datetime import datetime
    
    return SAIGESession(
        session_id="test-session-123",
        caller_phone="1234567890",
        conversation_state=ConversationState.CUSTOMER_VERIFICATION,
        conversation_history=[],
        symptoms=[],
        created_at=datetime.now(),
        last_updated=datetime.now(),
        total_interactions=0,
        temp_data={},
        pending_questions=[],
        diagnostic_turn_count=0,
        services_to_book=[]
    )
