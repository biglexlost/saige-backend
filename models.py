# /src/models.py
# extracomment
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional
from config import config

# --- Enums for Controlled Vocabularies ---


class CustomerType(Enum):
    NEW = "new"
    RETURNING = "returning"


class VerificationStatus(Enum):
    VERIFIED = "verified"
    PENDING = "pending"


class ConversationState(str, Enum):
    # --- Start of Conversation ---
    CUSTOMER_VERIFICATION = "customer_verification"
    # --- NEW STREAMLINED STATE ---
    PRIOR_SERVICE_CONFIRMATION = "prior_service_confirmation"
    PHONE_NUMBER_CLARIFICATION = "phone_number_clarification"

    # --- Med-spa specific states ---
    CONSENT = "consent"
    SERVICE_SELECTION = "service_selection"
    INTAKE_QA = "intake_qa"
    PROPOSE_SCHEDULING = "propose_scheduling"
    CONFIRM_APPOINTMENT = "confirm_appointment"
    CONVERSATION_COMPLETE = "conversation_complete"


# --- Pydantic Request Models ---


class ChatMessage(BaseModel):
    role: str
    content: str


class CallDetails(BaseModel):
    id: str


class IdentificationResult(BaseModel):
    customer_type: CustomerType = CustomerType.NEW
    verification_status: VerificationStatus
    customer_id: Optional[str] = None
    greeting: str = Field(
        default=f"Thank you for calling {config.shop_name}, this is {config.assistant_name}. How can I help you today?"
    )


# CORRECT ORDER: Define VehicleInfo and ServiceHistoryEntry BEFORE they are used in CustomerProfile.
class VehicleInfo(BaseModel):
    year: int
    make: str
    model: str
    vin: Optional[str] = None


class ServiceHistoryEntry(BaseModel):
    service_date: date
    vehicle_description: str
    service_description: str


# CORRECTED: CustomerProfile is now defined only ONCE, after its dependencies.
class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    phone: str
    vehicles: List[VehicleInfo] = Field(default_factory=list)
    service_history: List[ServiceHistoryEntry] = Field(default_factory=list)


class SAIGESession(BaseModel):
    """Complete SAIGE conversation session for med-spa"""

    session_id: str
    caller_phone: str
    conversation_state: ConversationState
    identification_result: Optional[IdentificationResult] = None
    customer_profile: Optional[CustomerProfile] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    total_interactions: int = 0
    temp_data: Dict[str, Any] = Field(default_factory=dict)
    pending_questions: List[str] = Field(default_factory=list)
    last_question_asked: Optional[str] = None
    services_to_book: List[str] = Field(default_factory=list)
    consent_given: bool = False
    service_preferences: List[str] = Field(default_factory=list)
    scheduling_preferences: Dict[str, Any] = Field(default_factory=dict)

    def update_state(self, new_state: ConversationState):
        """Update conversation state and timestamp"""
        self.conversation_state = new_state
        self.last_updated = datetime.now()
