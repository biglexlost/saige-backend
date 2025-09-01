"""
VAPI Server-Side Client for AI Executive
No pyaudio dependency - works perfectly on Render
"""

import httpx
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class VAPIPhoneCall(BaseModel):
    """Phone call configuration"""

    phone_number: str
    assistant_id: str
    customer_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VAPIWebCall(BaseModel):
    """Web call configuration for browser-based calls"""

    assistant_id: str
    metadata: Optional[Dict[str, Any]] = None


class VAPIServerClient:
    """
    VAPI API client for server-side operations
    Handles all VAPI functionality without needing pyaudio
    """

    def __init__(self, api_key: str, base_url: str = "https://api.vapi.ai"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ===== PHONE CALLS =====

    async def create_phone_call(
        self,
        phone_number: str,
        assistant_id: str,
        customer_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create an outbound phone call
        The AI Executive will call the specified phone number
        """
        payload = {
            "phoneNumber": phone_number,
            "assistantId": assistant_id,
        }

        if customer_name:
            payload["customerName"] = customer_name

        if metadata:
            payload["metadata"] = metadata

        payload.update(kwargs)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/calls/phone", headers=self.headers, json=payload
            )
            response.raise_for_status()
            return response.json()

    # ===== WEB CALLS (Browser-based) =====

    async def create_web_call_url(
        self, assistant_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a web call URL that users can open in their browser
        No app installation needed - works directly in the browser
        """
        payload = {
            "assistantId": assistant_id,
        }

        if metadata:
            payload["metadata"] = metadata

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/calls/web", headers=self.headers, json=payload
            )
            response.raise_for_status()
            result = response.json()

            # The response includes a URL that users can open in their browser
            # Example: https://vapi.ai/call/xxxxx
            return result

    # ===== CALL MANAGEMENT =====

    async def get_call(self, call_id: str) -> Dict[str, Any]:
        """Get details about a specific call"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/calls/{call_id}", headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def list_calls(
        self,
        limit: int = 100,
        created_at_gt: Optional[datetime] = None,
        created_at_lt: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all calls with optional filters"""
        params = {"limit": limit}

        if created_at_gt:
            params["createdAtGt"] = created_at_gt.isoformat()
        if created_at_lt:
            params["createdAtLt"] = created_at_lt.isoformat()
        if status:
            params["status"] = status

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/calls", headers=self.headers, params=params
            )
            response.raise_for_status()
            return response.json()

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """End an ongoing call"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/calls/{call_id}/end", headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    # ===== ASSISTANTS =====

    async def create_assistant(
        self, assistant_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new AI assistant with specific configuration
        Example config:
        {
            "name": "Jaime's AI Executive",
            "voice": {
                "provider": "elevenlabs",
                "voiceId": "rachel"
            },
            "model": {
                "provider": "groq",
                "model": "llama-3.1-8b-8192",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an AI Executive Assistant..."
                    }
                ]
            },
            "firstMessage": "Hello, I'm calling on behalf of Jaime..."
        }
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/assistants",
                headers=self.headers,
                json=assistant_config,
            )
            response.raise_for_status()
            return response.json()

    async def update_assistant(
        self, assistant_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing assistant"""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/v1/assistants/{assistant_id}",
                headers=self.headers,
                json=updates,
            )
            response.raise_for_status()
            return response.json()

    async def get_assistant(self, assistant_id: str) -> Dict[str, Any]:
        """Get assistant details"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/assistants/{assistant_id}", headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def list_assistants(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all assistants"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/assistants",
                headers=self.headers,
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()

    # ===== PHONE NUMBERS =====

    async def list_phone_numbers(self) -> List[Dict[str, Any]]:
        """List available phone numbers for outbound calls"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/phone-numbers", headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    # ===== ANALYTICS =====

    async def get_analytics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get call analytics for a date range"""
        params = {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/analytics", headers=self.headers, params=params
            )
            response.raise_for_status()
            return response.json()


# ===== USAGE EXAMPLE =====


async def example_usage():
    """Example of how to use the VAPI client in your FastAPI app"""

    # Initialize client
    vapi = VAPIServerClient(api_key="your-vapi-api-key")

    # 1. Create an outbound phone call
    call_result = await vapi.create_phone_call(
        phone_number="+1234567890",
        assistant_id="your-assistant-id",
        customer_name="John Doe",
        metadata={"purpose": "follow_up", "account_id": "12345"},
    )
    print(f"Call initiated: {call_result['id']}")

    # 2. Create a web call URL (for browser-based calls)
    web_call = await vapi.create_web_call_url(
        assistant_id="your-assistant-id", metadata={"session_id": "abc123"}
    )
    print(f"Web call URL: {web_call['url']}")

    # 3. Check call status
    call_details = await vapi.get_call(call_result["id"])
    print(f"Call status: {call_details['status']}")

    # 4. List recent calls
    recent_calls = await vapi.list_calls(limit=10)
    for call in recent_calls:
        print(f"Call {call['id']}: {call['status']}")


# ===== INTEGRATION WITH YOUR FASTAPI APP =====

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel

app = FastAPI()

# Initialize VAPI client
vapi_client = VAPIServerClient(api_key="your-vapi-api-key")


class CallRequest(PydanticBaseModel):
    phone_number: str
    customer_name: str
    purpose: str


@app.post("/api/make-executive-call")
async def make_executive_call(request: CallRequest):
    """Endpoint to initiate an AI Executive call"""
    try:
        result = await vapi_client.create_phone_call(
            phone_number=request.phone_number,
            assistant_id="your-executive-assistant-id",
            customer_name=request.customer_name,
            metadata={
                "purpose": request.purpose,
                "initiated_at": datetime.utcnow().isoformat(),
            },
        )
        return {"success": True, "call_id": result["id"], "status": result["status"]}
    except Exception as e:
        logger.error(f"Failed to create call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/web-call-url")
async def get_web_call_url():
    """Get a URL for browser-based AI Executive calls"""
    try:
        result = await vapi_client.create_web_call_url(
            assistant_id="your-executive-assistant-id"
        )
        return {
            "success": True,
            "url": result["url"],
            "expires_at": result.get("expiresAt"),
        }
    except Exception as e:
        logger.error(f"Failed to create web call URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))
