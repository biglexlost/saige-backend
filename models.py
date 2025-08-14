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

    # --- Vehicle & Service Identification ---
    VEHICLE_CONFIRMATION = "vehicle_confirmation"  # Now used for new vehicles
    VEHICLE_COLLECTION = "vehicle_collection"
    COLLECT_MILEAGE = "collect_mileage"
    COLLECT_NEW_CUSTOMER_NAME = "collect_new_customer_name"
    CONFIRM_NEW_CUSTOMER_PHONE = "confirm_new_customer_phone"
    SERVICE_INTAKE = "service_intake"
    DIAGNOSTIC_QUESTIONING = "diagnostic_questioning"

    # --- Scheduling Flow ---
    ASK_ABOUT_ESTIMATE = "ask_about_estimate"
    REQUEST_LICENSE_PLATE = "request_license_plate"
    OFFER_ESTIMATE = "offer_estimate"
    PROPOSE_SCHEDULING = "propose_scheduling"
    AWAITING_TIMESLOT = "awaiting_timeslot"
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


class JAIMESSession(BaseModel):
    """Complete JAIMES conversation session"""

    session_id: str
    caller_phone: str
    conversation_state: ConversationState
    identification_result: Optional[IdentificationResult] = None
    customer_profile: Optional[CustomerProfile] = None
    vehicle_info: Optional[VehicleInfo] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    symptoms: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    total_interactions: int = 0
    last_service_date: Optional[datetime] = None
    temp_data: Dict[str, Any] = Field(default_factory=dict)
    pending_questions: List[str] = Field(default_factory=list)
    last_question_asked: Optional[str] = None
    upsell_service_description: Optional[str] = None
    diagnostic_turn_count: int = 0
    services_to_book: List[str] = Field(default_factory=list)

    def update_state(self, new_state: ConversationState):
        """Update conversation state and timestamp"""
        self.conversation_state = new_state
        self.last_updated = datetime.now()
