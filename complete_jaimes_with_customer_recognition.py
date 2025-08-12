# /src/complete_jaimes_with_customer_recognition.py

import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
import redis
import redis.exceptions
from groq import Groq, AsyncGroq
from models import JAIMESSession, ConversationState, CustomerProfile, ChatMessage
from mock_db import MockCustomerEngine
from config import config
from num2words import num2words
from analytics import init_analytics_db, log_event
from smart_pricing_manager import SmartPricingManager
from vehicle_database_api_client import VehicleDatabaseAPIClient, VehicleInfo
from milex_pricing_engine import MileXPricingEngine
from vehicle_recall_service import VehicleRecallService
from enhanced_accent_handler import SouthernAccentHandler
from enhanced_conversation_intelligence import EnhancedConversationIntelligence as ConversationIntelligence, EmotionalState, IntentType
from enhanced_streaming import EnhancedStreamer as StreamingResponseManager, StreamingMode
# Temporarily disabled for deployment stability
# from returning_customer_flow import ReturningCustomerFlowManager as ReturningCustomerManager, ReturningCustomerContext
import json
import asyncio
from datetime import datetime
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog
from functools import wraps
from pydantic import BaseModel, validator, Field
import html
import re
from typing import Union

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Input validation models
class UserInputValidator(BaseModel):
    """Validates and sanitizes user input"""
    content: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1, max_length=100)
    
    @validator('content')
    def sanitize_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Input cannot be empty")
        
        # Remove potential XSS/injection attempts
        sanitized = html.escape(v.strip())
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Block potential injection patterns
        dangerous_patterns = [
            r'<script', r'javascript:', r'vbscript:', r'onload=', r'onerror=',
            r'eval\(', r'exec\(', r'system\(', r'import\s+os', r'__import__'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                raise ValueError("Input contains potentially dangerous content")
        
        return sanitized
    
    @validator('session_id')
    def validate_session_id(cls, v):
        # Session ID should be alphanumeric with hyphens only
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError("Invalid session ID format")
        return v

class PhoneNumberValidator(BaseModel):
    """Validates phone numbers"""
    phone: str = Field(..., min_length=10, max_length=15)
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove all non-digit characters for validation
        digits_only = re.sub(r'\D', '', v)
        
        # US phone numbers should be 10 or 11 digits
        if len(digits_only) not in [10, 11]:
            raise ValueError("Phone number must be 10 or 11 digits")
        
        # If 11 digits, must start with 1
        if len(digits_only) == 11 and not digits_only.startswith('1'):
            raise ValueError("11-digit phone number must start with 1")
            
        return digits_only

# Resilience decorators for critical services
def groq_circuit_breaker():
    """Circuit breaker for Groq API calls"""
    return circuit(failure_threshold=5, recovery_timeout=30, expected_exception=Exception)

def redis_circuit_breaker():
    """Circuit breaker for Redis operations"""
    return circuit(failure_threshold=3, recovery_timeout=10, expected_exception=Exception)

def vehicle_api_circuit_breaker():
    """Circuit breaker for Vehicle Database API"""
    return circuit(failure_threshold=3, recovery_timeout=15, expected_exception=Exception)

def groq_retry():
    """Retry logic for Groq API with exponential backoff"""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception))
    )

def redis_retry():
    """Retry logic for Redis operations"""
    return retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )


def normalize_phone_number(phone: str) -> str:
    """Strips all non-digit characters and the leading '1' if it's a US number."""
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) == 11 and digits_only.startswith("1"):
        return digits_only[1:]
    return digits_only


class CompleteJAIMESSystem:
    def __init__(self, groq_api_key: str, redis_url: str, **kwargs):
        logger.info(f"Initializing JAIMES in [{config.environment}] mode...")
        self.customer_engine = MockCustomerEngine()
        self.groq_client = AsyncGroq(api_key=groq_api_key)
        self.groq_model = config.groq_model
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Successfully connected to Redis server.")
        except Exception as e:
            logger.error(
                f"Failed to connect to Redis: {e}. Relying on in-memory fallback."
            )
            self.redis_client = None
        self.in_memory_sessions: Dict[str, JAIMESSession] = {}

        # Initialize analytics DB
        init_analytics_db()

        # Load diagnostic cheat sheet
        try:
            with open('diagnostic_cheat_sheet.json', 'r') as f:
                self.diagnostic_cheat_sheet = json.load(f)
            logger.info("Loaded diagnostic cheat sheet")
        except Exception as e:
            logger.warning(f"Failed to load diagnostic cheat sheet: {e}")
            self.diagnostic_cheat_sheet = None

        # Initialize enhanced modules with performance optimizations
        try:
            self.accent_handler = SouthernAccentHandler()
            self.conversation_intelligence = ConversationIntelligence()
            self.streaming_manager = StreamingResponseManager()
            # Temporarily disable returning customer manager for deployment stability
            self.returning_customer_manager = None  # ReturningCustomerManager()
            
            # Performance caches
            self._accent_cache = {}  # Cache accent processing results
            self._intelligence_cache = {}  # Cache conversation analysis
            self._cache_ttl = 300  # 5 minutes cache TTL
            
            logger.info("Initialized enhanced modules with performance optimizations (returning customer manager temporarily disabled)")
        except Exception as e:
            logger.warning(f"Failed to initialize enhanced modules: {e}")
            self.accent_handler = None
            self.conversation_intelligence = None
            self.streaming_manager = None
            self.returning_customer_manager = None
            self._accent_cache = {}
            self._intelligence_cache = {}

        # Initialize pricing components (API will only be used in PROD)
        try:
            self.vehicle_api_client = VehicleDatabaseAPIClient(
                api_key=(config.vehicle_db_api_key or "DEV_KEY")
            )
            self.milex_engine = MileXPricingEngine()
            self.pricing_manager = SmartPricingManager(
                vehicle_api_client=self.vehicle_api_client,
                milex_engine=self.milex_engine,
            )
            logger.info("Pricing components initialized")
        except Exception as e:
            logger.error(f"Failed to init pricing components: {e}")
            self.vehicle_api_client = None
            self.milex_engine = None
            self.pricing_manager = None

        # Initialize recall service (uses Redis; safe to skip if not available)
        try:
            if self.redis_client:
                self.recall_service = VehicleRecallService(redis_url)
            else:
                self.recall_service = None
        except Exception as e:
            logger.warning(f"Recall service init skipped: {e}")
            self.recall_service = None

    @redis_circuit_breaker()
    @redis_retry()
    def get_session(self, session_id: str) -> Optional[JAIMESSession]:
        try:
            if self.redis_client and self.redis_client.ping():
                session_json = self.redis_client.get(session_id)
                if session_json:
                    return JAIMESSession.model_validate_json(session_json)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.warning(f"Redis connection/timeout error on GET: {e}. Falling back to memory.")
        except Exception as e:
            logger.warning(f"Redis error on GET session {session_id}: {e}. Falling back to memory.")
        return self.in_memory_sessions.get(session_id)

    @redis_circuit_breaker()
    @redis_retry()
    def save_session(self, session_id: str, session: JAIMESSession):
        try:
            if self.redis_client and self.redis_client.ping():
                self.redis_client.set(session_id, session.model_dump_json(), ex=3600)
                if session_id in self.in_memory_sessions:
                    del self.in_memory_sessions[session_id]
                return
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.warning(f"Redis connection/timeout error on SET: {e}. Falling back to memory.")
        except Exception as e:
            logger.warning(f"Redis error on SET session {session_id}: {e}. Falling back to memory.")
        self.in_memory_sessions[session_id] = session

    async def start_conversation(
        self, caller_phone: str, session_id: str
    ) -> AsyncGenerator[str, None]:
        # Validate phone number and session ID
        try:
            validated_phone = PhoneNumberValidator(phone=caller_phone)
            validated_session = UserInputValidator(content="<BEGIN_CONVERSATION>", session_id=session_id)
            caller_phone = validated_phone.phone
            session_id = validated_session.session_id
        except ValueError as e:
            logger.warning(f"Phone/session validation failed: {e}")
            yield "I'm sorry, there seems to be an issue with the call setup. Please try calling back."
            return
        except Exception as e:
            logger.error(f"Unexpected validation error in start_conversation: {e}")
            yield "I'm experiencing a technical issue. Please try calling back."
            return
            
        logger.info(f"Starting conversation for {caller_phone} (session: {session_id})")
        normalized_phone = normalize_phone_number(caller_phone)
        logger.info(f"Normalized phone number to {normalized_phone} for lookup.")
        customer_profile = await self.customer_engine.find_customer_by_phone(
            normalized_phone
        )
        session_state = (
            ConversationState.CUSTOMER_VERIFICATION
            if customer_profile
            else ConversationState.PRIOR_SERVICE_CONFIRMATION
        )
        session = JAIMESSession(
            session_id=session_id,
            caller_phone=caller_phone,
            conversation_state=session_state,
            customer_profile=customer_profile,
        )
        # mark call start
        session.temp_data["call_started_at"] = datetime.utcnow().isoformat()
        try:
            log_event("call_started", session_id, {"user_type": "returning" if customer_profile else "new"})
        except Exception as e:
            logger.warning(f"Analytics logging (call_started) failed: {e}")
        self.save_session(session_id, session)
        async for chunk in self.process_conversation(
            user_input="<BEGIN_CONVERSATION>", session_id=session_id
        ):
            yield chunk

    async def _prepare_llm_turn(self, user_input: str, session: JAIMESSession) -> (str, ConversationState):
        # Safety check for input and decode HTML entities
        if not user_input:
            user_input = ""
        
        # Decode HTML entities (e.g., &lt;BEGIN_CONVERSATION&gt; -> <BEGIN_CONVERSATION>)
        user_input = html.unescape(user_input)
        
        state = session.conversation_state
        next_state = state
        mission = ""
        
        logger.info(f"PREPARE_LLM_TURN: Current state: {state}, User input: '{user_input}'")
        
        base_prompt = """
You are James, an AI assistant for My-Lex Complete Auto Care. You're a helpful, friendly local from Durham, NC. Be relaxed and casual while staying about 55% professional.

Tone and style:
- Keep it calm and approachable; avoid corporate language
- Use plain words and contractions (I'm, we'll, that's) but no slang
- Short responses: usually 1–2 sentences before asking the next question
- No exclamation points
- Be concise: prefer 12–18 words per sentence; avoid filler and restating the user's answers

Conversation rules:
1. **One question at a time.** Ask a single, clear question, then wait.
2. **Mileage services.** ALWAYS say mileage in full words, never digits (e.g., "sixty-thousand miles" NOT "60000 miles").
3. **Use names sparingly.** Use the customer's name only once per conversation turn. Avoid repeating names in the same response.
4. **No mileage intervals during diagnosis.** Only mention 30/60/90 during explicit upsell moments.
5. **Vehicle accuracy.** Don’t change the user’s stated vehicle. If records differ, ask a quick confirmation instead of substituting.
6. **Professional phrasing.** Avoid speculative idioms (e.g., "stab in the dark"). Prefer: "Based on what you've told me, the most likely cause is… We'll confirm with an inspection."
7. **No unsupported options.** Do not invent service tiers (e.g., “standard” vs “express”), emails, or texts unless they are explicitly provided in the mission.
8. **Scheduling truthfulness.** Never say something is “scheduled” until the date and time are confirmed. When asked to output a specific sentence, output exactly and only that sentence.
"""
        # --- CHAPTER 1: CUSTOMER IDENTIFICATION ---

        if state == ConversationState.CUSTOMER_VERIFICATION:
            customer_name = session.customer_profile.name if session.customer_profile else "our customer"
            user_affirmed = any(word in user_input.lower() for word in ['yes', 'yeah', 'yep', 'correct'])
            if user_input == "<BEGIN_CONVERSATION>":
                mission = f"Say this exactly: 'Hi, this is James, your AI support specialist with My-Lex Complete Auto Care. I see this number is for {customer_name}. Am I speaking with the right person?'"
            elif user_affirmed:
                next_state = ConversationState.VEHICLE_CONFIRMATION
                if session.customer_profile and session.customer_profile.service_history:
                    last_service = sorted(session.customer_profile.service_history, key=lambda s: s.service_date, reverse=True)[0]
                    mission = (f"Say this, or something very close to: 'Great, thanks for confirming. I see the last time you were in, we performed {last_service.service_description} "
                            f"on your {last_service.vehicle_description}. How has that been holding up for you?'")
                else:
                    mission = "Great, thanks for confirming. What can I help you with today?"
            else:
                next_state = ConversationState.PRIOR_SERVICE_CONFIRMATION
                mission = "The user said they are NOT the person associated with this phone number. Apologize for the mistake, and then ask if they have ever had a vehicle serviced with you before."

        elif state == ConversationState.PRIOR_SERVICE_CONFIRMATION:
            if user_input == "<BEGIN_CONVERSATION>":
                mission = "Say this exactly: 'Hi, this is James, your AI support specialist with My-Lex Complete Auto Care. To get things started, have you had a vehicle serviced with us here before?'"
            elif any(word in user_input.lower() for word in ['yes', 'yeah', 'yep']):
                next_state = ConversationState.PHONE_NUMBER_CLARIFICATION
                mission = "The user is a returning customer. Say this exactly: 'Okay, thanks for clarifying. What phone number might the account be under?'"
            else:
                next_state = ConversationState.VEHICLE_COLLECTION
                mission = "The user is a new customer. Welcome them and then ask for the year, make, and model of their vehicle to get a file started."

        elif state == ConversationState.PHONE_NUMBER_CLARIFICATION:
            if any(char.isdigit() for char in user_input):
                try:
                    normalized_alt_phone = normalize_phone_number(user_input.strip())
                    customer_profile = await self.customer_engine.find_customer_by_phone(normalized_alt_phone)
                    if customer_profile:
                        session.customer_profile = customer_profile
                        next_state = ConversationState.VEHICLE_CONFIRMATION
                        if customer_profile.service_history:
                            last_service = sorted(customer_profile.service_history, key=lambda s: s.service_date, reverse=True)[0]
                            mission = f"Say this exactly: 'Great, I found the account for {customer_profile.name}. I see the last time you were in, we performed {last_service.service_description} on your {last_service.vehicle_description}. How has that been holding up for you?'"
                        else:
                            mission = f"Great, I found the account for {customer_profile.name}. What can I help you with today?"
                    else:
                        next_state = ConversationState.VEHICLE_COLLECTION
                        mission = "You still couldn't find a file with that number. Acknowledge this, and politely ask for their vehicle's year, make, and model to start a new file."
                except Exception as e:
                    logger.error(f"Error processing phone number clarification: {e}")
                    next_state = ConversationState.VEHICLE_COLLECTION
                    mission = "I'm having trouble looking up that number. Let me help you start a new file. What's the year, make, and model of your vehicle?"
            else:
                next_state = ConversationState.PHONE_NUMBER_CLARIFICATION
                mission = ("The user did not provide a phone number. Acknowledge their response (e.g., 'Okay, for your husband's account then.') "
                        "and then politely re-ask for the number itself. Say 'And what is that phone number?'")

        # --- CHAPTER 2: NEW CUSTOMER & VEHICLE ONBOARDING ---

        elif state == ConversationState.VEHICLE_CONFIRMATION:
            # Enhanced returning customer flow using the returning customer manager
            if self.returning_customer_manager and session.customer_profile:
                try:
                    # Create returning customer context manually
                    vehicles_data = [{"year": v.year, "make": v.make, "model": v.model} for v in session.customer_profile.vehicles] if session.customer_profile.vehicles else []
                    service_history = [{"service": s.service_description, "date": s.service_date} for s in session.customer_profile.service_history] if session.customer_profile.service_history else []
                    
                    returning_context = ReturningCustomerContext(
                        customer_id=session.customer_profile.customer_id,
                        name=session.customer_profile.name,
                        phone_number=session.customer_profile.phone_number,
                        vehicles=vehicles_data,
                        service_history=service_history
                    )
                    
                    # Get enhanced returning customer message
                    enhanced_mission = await self.returning_customer_manager.generate_proactive_greeting(
                        context=returning_context
                    )
                    
                    if enhanced_mission:
                        next_state = ConversationState.SERVICE_INTAKE
                        mission = enhanced_mission
                        logger.info("Used enhanced returning customer flow")
                    else:
                        # Fallback to standard logic
                        next_state = ConversationState.SERVICE_INTAKE
                        mission = self._standard_vehicle_confirmation_logic(session, user_input)
                except Exception as e:
                    logger.warning(f"Enhanced returning customer flow failed: {e}")
                    # Fallback to standard logic
                    next_state = ConversationState.SERVICE_INTAKE
                    mission = self._standard_vehicle_confirmation_logic(session, user_input)
            
            # Standard logic for customers without the enhanced flow
            elif session.customer_profile and session.customer_profile.vehicles:
                vehicles = [f"{v.year} {v.make} {v.model}" for v in session.customer_profile.vehicles]
                joined = ' or '.join(vehicles[:2]) if len(vehicles) <= 2 else ', '.join(vehicles[:-1]) + f", or {vehicles[-1]}"
                next_state = ConversationState.SERVICE_INTAKE
                mission = ("The user confirmed who they are. Confirm the vehicle rather than changing it. "
                           f"Say something like: 'I have {joined} on file. Which one are we working with today?' Then, once they pick, ask what's going on with that vehicle.")
            else:
                is_confused = any(word in user_input.lower() for word in ['what', 'say again', '?'])
                if is_confused:
                    next_state = state
                    mission = "The user seems confused. Re-ask the question clearly and simply: 'Sorry about that, which vehicle are you calling about today?'"
                else:
                    next_state = ConversationState.SERVICE_INTAKE
                    mission = (f"The user has identified their vehicle as a '{user_input}'. Acknowledge this without changing it. "
                               "Ask what problem they’re having or what service they need.")

        elif state == ConversationState.VEHICLE_COLLECTION:
            if session.customer_profile:
                next_state = ConversationState.SERVICE_INTAKE
                mission = ("The user (a returning customer) has provided the details for their new vehicle. "
                        "Acknowledge that you've added it to their file, and then ask what service they need for it today.")
            else:
                if "miles" in user_input.lower():
                    next_state = ConversationState.COLLECT_NEW_CUSTOMER_NAME
                    session.temp_data['new_vehicle_mileage'] = user_input
                    mission = "The user has provided their vehicle and mileage. Acknowledge this, and now ask for their name to complete the file."
                else:
                    next_state = ConversationState.COLLECT_MILEAGE
                    mission = ("The user (a new customer) has provided their vehicle's year, make, and model. "
                            "Acknowledge the vehicle, and to complete the new file, ask for the current mileage.")

        elif state == ConversationState.COLLECT_MILEAGE:
            next_state = ConversationState.COLLECT_NEW_CUSTOMER_NAME
            session.temp_data['new_vehicle_mileage'] = user_input
            logger.info(f"Stored mileage: '{user_input}' in session temp_data")
            mission = "The user has provided the mileage. Acknowledge this, and now ask for their first and last name so you can complete their new file."

        elif state == ConversationState.COLLECT_NEW_CUSTOMER_NAME:
            # THE FIX: This state now combines the name collection and phone confirmation into one smooth step.
            next_state = ConversationState.SERVICE_INTAKE
            session.temp_data['new_customer_name'] = user_input # Save the name
            caller_phone = session.caller_phone
            logger.info(f"Stored customer name: '{user_input}', mileage: '{session.temp_data.get('new_vehicle_mileage', 'NOT SET')}'")
            mission = (f"The user has provided their name: '{user_input}'. Your mission is to acknowledge their name and confirm their phone number in one go. "
                    f"Say this, or something very close to: 'Okay thanks, {user_input}. One last thing for your file, the number I have for you is {caller_phone}. "
                    "Is that the best number to keep on file?'")

        # --- CHAPTER 3: SERVICE, DIAGNOSTICS, AND ESTIMATES ---
        elif state == ConversationState.SERVICE_INTAKE:
            user_service_request = user_input.lower()
            logger.info(f"SERVICE_INTAKE: user_service_request='{user_service_request}'")
            
            # Check if this is a repeated request (VAPI interference protection)
            last_request = session.temp_data.get('last_service_request', '')
            if last_request and last_request in user_service_request and len(user_service_request) > len(last_request):
                # This looks like an extended version of the same request - use the original
                logger.info(f"Detected VAPI interference: '{user_service_request}' extends '{last_request}'")
                user_service_request = last_request
            else:
                # Store this as the last request for future comparison
                session.temp_data['last_service_request'] = user_service_request
            
            # Handle phone confirmation responses that get misrouted here
            if user_service_request.strip() in ['yes', 'yeah', 'yep', 'yes.', 'correct', 'right']:
                next_state = ConversationState.SERVICE_INTAKE
                mission = ("Thank you for confirming. Now, what brings you to My-Lex Complete Auto Care today? "
                        "Are you experiencing an issue with your vehicle, or are you due for some routine maintenance?")
            
            # 1. Check for out-of-scope requests first, using the config list.
            elif any(service in user_service_request for service in config.OUT_OF_SCOPE_SERVICES):
                next_state = ConversationState.CONVERSATION_COMPLETE
                mission = ("The user is asking for a service that is not offered (e.g., body work). "
                        "Politely inform them that you don't offer that service and list the general categories you do handle "
                        "(e.g., 'engine, transmission, brakes, and routine maintenance'). End the call politely.")
            
            # 2. Check if it's a known, in-scope service.
            elif any(service in user_service_request for service in config.IN_SCOPE_SERVICES):
                # Differentiate between simple and complex in-scope services
                simple_services = ['tire rotation', 'oil change', 'alignment'] # This list can also be moved to config
                is_simple_service = any(service in user_service_request for service in simple_services)
                
                if is_simple_service:
                    # Extract the actual service name, not the full garbled input
                    extracted_service = next((service for service in simple_services if service in user_service_request), "service")
                    session.services_to_book.append(extracted_service)
                    next_state = ConversationState.PROPOSE_SCHEDULING
                    # log schedule proposed for simple service
                    try:
                        log_event("schedule_proposed", session.session_id, {"context": "simple_service", "service": extracted_service})
                    except Exception as e:
                        logger.warning(f"Analytics logging (schedule_proposed simple) failed: {e}")
                    session.temp_data['came_from_offer_estimate'] = False
                    mission = f"The user wants a {extracted_service}. Acknowledge this and ask if they would like to schedule an appointment."
                else: # It's a complex, in-scope repair
                    session.services_to_book.append("Diagnostic Inspection")
                    next_state = ConversationState.DIAGNOSTIC_QUESTIONING
                    mission = f"The user has described a problem: '{user_input}'. Your mission is to begin a diagnostic conversation. Ask your FIRST clarifying question."
            
            # 3. Check for diagnostic issues (noises, problems, symptoms)
            elif any(symptom in user_service_request for symptom in ['noise', 'sound', 'humming', 'grinding', 'squealing', 'knocking', 'vibration', 'shaking', 'leak', 'smoke', 'smell', 'problem', 'issue', 'trouble', 'wrong']):
                logger.info("SERVICE_INTAKE: Detected diagnostic issue, moving to DIAGNOSTIC_QUESTIONING")
                session.services_to_book.append("Diagnostic Inspection")
                next_state = ConversationState.DIAGNOSTIC_QUESTIONING
                mission = f"The user has described a diagnostic issue: '{user_input}'. Your mission is to begin a diagnostic conversation. Ask your FIRST clarifying question to help identify the problem."
            
            # 4. Fallback for unclear requests.
            else:
                next_state = ConversationState.SERVICE_INTAKE # Loop back to try again
                mission = "I'm not sure what you need help with. Could you tell me what's going on with your vehicle?"
    
        elif state == ConversationState.DIAGNOSTIC_QUESTIONING:
            session.diagnostic_turn_count += 1
            logger.info(f"Diagnostic turn count: {session.diagnostic_turn_count}, user input: '{user_input}'")
            
            # Enhanced diagnostic logic - be more thorough and intelligent
            max_diagnostic_turns = 5  # Allow more turns for thorough diagnosis
            user_wants_to_schedule = any(word in user_input.lower() for word in ['schedule', 'appointment', 'book', 'come in', 'bring it in'])
            
            # Check if we have enough information for a confident diagnosis
            has_sufficient_info = self._has_sufficient_diagnostic_info(session)
            # Compute confidence score for a potential fast-path
            try:
                conversation_text_fp = ' '.join([msg.get('content', '') for msg in session.conversation_history]).lower()
                analysis_fp = self._analyze_diagnostic_symptoms(conversation_text_fp)
                confidence_fp = self._compute_diagnostic_confidence(session, analysis_fp)
                logger.info(f"Diagnostic fast-path confidence: {confidence_fp:.2f}, analysis: {analysis_fp}")
            except Exception as e:
                logger.warning(f"Diagnostic confidence computation failed: {e}")
                confidence_fp = 0.0
            
            # Fast-path: If confidence is very high (>= 0.9) after at least 2 turns AND we have a clear signature, jump to estimate/scheduling
            if (
                confidence_fp >= 0.9 and session.diagnostic_turn_count >= 2 and self._determine_fast_path_reason(session, analysis_fp)
            ) or user_wants_to_schedule or (session.diagnostic_turn_count >= max_diagnostic_turns and has_sufficient_info):
                # User wants to schedule OR we have enough info for a confident diagnosis
                next_state = ConversationState.ASK_ABOUT_ESTIMATE
                probable_cause = self._determine_probable_cause(session)
                session.temp_data['probable_cause'] = probable_cause
                reason = self._determine_fast_path_reason(session, analysis_fp)
                if reason:
                    logger.info(f"Fast-path triggered: {reason}")
                logger.info(f"Moving to ASK_ABOUT_ESTIMATE with probable cause: {probable_cause}")
                mission = ("You have gathered enough diagnostic information. You MUST complete ALL THREE steps: "
                        f"1. State a probable cause: 'Based on what you've told me, the most likely cause is {probable_cause}.' "
                        "2. Explain inspection needed: 'However, a physical inspection is needed to be certain.' "
                        "3. ASK THE ESTIMATE QUESTION: 'Would you like to get a cost estimate for that inspection and repair?' "
                        "You must complete all three steps in your response.")
            elif session.diagnostic_turn_count >= max_diagnostic_turns and not has_sufficient_info:
                # We've asked enough questions but still don't have enough info
                next_state = ConversationState.PROPOSE_SCHEDULING
                session.services_to_book.append("Diagnostic Inspection")
                logger.info("Insufficient diagnostic info after max turns - moving to scheduling")
                mission = ("You have asked several diagnostic questions but still need more information to determine the issue. "
                        "Your mission is to: "
                        "1. Acknowledge that you need more information to properly diagnose the problem. "
                        "2. Explain that a physical inspection by our technicians would be the best way to identify the issue. "
                        "3. Ask if they would like to schedule an appointment for a diagnostic inspection.")
            else:
                # Continue with diagnostic questioning
                next_state = ConversationState.DIAGNOSTIC_QUESTIONING
                # Track CEL status if explicitly mentioned
                text_low = user_input.lower()
                if 'check engine' in text_low or 'cel' in text_low:
                    if any(tok in text_low for tok in ['not on', "isn't on", 'is not on', 'off', 'no']):
                        session.temp_data['cel_on'] = False
                    elif any(tok in text_low for tok in ['on', 'lit', 'light is on']):
                        session.temp_data['cel_on'] = True
                next_question = self._get_next_diagnostic_question(session, user_input)
                mission = (f"You are an expert mechanic diagnosing a problem over the phone. "
                        f"Your goal is to narrow down the issue. Ask this specific question: '{next_question}' "
                        "Use concise, professional phrasing. Avoid speculative language.")

        elif state == ConversationState.ASK_ABOUT_ESTIMATE:
            user_affirmed = any(word in user_input.lower() for word in ['yes', 'yeah', 'yep', 'correct', 'okay', 'sure'])
            logger.info(f"ASK_ABOUT_ESTIMATE: user_affirmed={user_affirmed}, customer_profile={session.customer_profile is not None}")
            logger.info(f"ASK_ABOUT_ESTIMATE: user_input='{user_input}', customer_profile exists: {session.customer_profile is not None}")
            
            if user_affirmed:
                if not session.customer_profile:
                    next_state = ConversationState.REQUEST_LICENSE_PLATE
                    logger.info("NEW customer wants estimate - moving to REQUEST_LICENSE_PLATE")
                    mission = "The user wants an estimate. Proceed to ask for their license plate."
                else:
                    # For returning customers, first ask if they want a rough range now or just schedule the diagnostic
                    next_state = ConversationState.OFFER_ESTIMATE
                    logger.info("RETURNING customer wants estimate - moving to OFFER_ESTIMATE")
                    mission = ("The user is a returning customer who wants an estimate. Provide a concise rough range only if relevant."
                               " Do not say it's scheduled yet. Then ask if they want to go ahead and schedule the visit.")
            else:
                # Log estimate declined for analytics and track pricing frequency
                try:
                    log_event(
                        "estimate_declined",
                        session.session_id,
                        {
                            "probable_cause": session.temp_data.get('probable_cause'),
                            "mileage": session.temp_data.get('new_vehicle_mileage'),
                            "zip": config.shop_zip_code,
                            "user_type": "returning" if session.customer_profile else "new",
                        },
                    )
                    # also log schedule proposed from decline path
                    log_event(
                        "schedule_proposed",
                        session.session_id,
                        {"context": "estimate_declined"}
                    )
                    if self.pricing_manager:
                        vi = session.vehicle_info or VehicleInfo(year=0, make="", model="")
                        self.pricing_manager.track_price_request(
                            vehicle_info=vi,
                            repair_description=session.temp_data.get('probable_cause', 'diagnostic'),
                            zip_code=config.shop_zip_code,
                            price=None,
                            source="declined",
                        )
                except Exception as e:
                    logger.warning(f"Analytics logging (estimate_declined/schedule_proposed) failed: {e}")
                
                session.services_to_book.append("Diagnostic Inspection")
                next_state = ConversationState.PROPOSE_SCHEDULING
                session.temp_data['came_from_offer_estimate'] = False
                logger.info("User declined estimate - moving to PROPOSE_SCHEDULING")
                mission = ("The user does not want an estimate right now. Acknowledge this by saying 'Okay, no problem.' "
                        "Then, ask if they'd like to schedule an appointment for a physical inspection to confirm the issue.")

        elif state == ConversationState.REQUEST_LICENSE_PLATE:
            # Check if user provided license plate info
            license_plate_pattern = r'[A-Z0-9]{1,8}'  # Basic pattern for license plates
            has_plate_info = bool(re.search(license_plate_pattern, user_input.upper().replace(' ', '')))
            
            if has_plate_info or 'no' in user_input.lower() or 'skip' in user_input.lower():
                # User provided plate or declined, move to estimate
                next_state = ConversationState.OFFER_ESTIMATE
                logger.info("REQUEST_LICENSE_PLATE: License plate provided or declined, moving to OFFER_ESTIMATE")
                if has_plate_info:
                    # Store the license plate for later VIN lookup
                    plate_match = re.search(license_plate_pattern, user_input.upper().replace(' ', ''))
                    if plate_match:
                        session.temp_data['license_plate'] = plate_match.group()
                        logger.info(f"Stored license plate: {session.temp_data['license_plate']}")
                mission = f"Thanks. For the {session.temp_data.get('probable_cause', 'issue')}, the estimate is {session.temp_data.get('repair_estimate_display', '$200-400')}. Would you like to schedule?"
            else:
                # Still waiting for license plate, stay in same state
                next_state = ConversationState.REQUEST_LICENSE_PLATE
                logger.info("REQUEST_LICENSE_PLATE: Still waiting for license plate")
                mission = ("Say this, or something very close to: 'Okay, great. To give you the most accurate estimate possible, "
                        "I can use your license plate number to pull up the exact manufacturer specs for your specific vehicle. "
                        "It's completely optional, but it really helps make the pricing precise. Would you be able to provide that for me?'")

            # Optionally: trigger a VIN-based recall lookup when VIN becomes available later
            # We will store plate/VIN in session.temp_data when user provides it; recall check happens in OFFER_ESTIMATE

        elif state == ConversationState.OFFER_ESTIMATE:
            next_state = ConversationState.PROPOSE_SCHEDULING
            logger.info("OFFER_ESTIMATE: Processing estimate with upsell logic")
            logger.info(f"OFFER_ESTIMATE: User input was '{user_input}'")
        
            acknowledgement = "Great, thanks for that information. "
            if any(word in user_input.lower() for word in ["no", "don't have it", "not right now"]):
                acknowledgement = "No problem at all. "

            probable_cause = session.temp_data.get('probable_cause', 'Brake Pad Replacement')
            zip_code = config.shop_zip_code

            # Attempt real pricing in PROD; mock in DEV
            price_low, price_high, price_total, price_source, cache_hit = (0.0, 0.0, 0.0, "mock", False)
            try:
                if self.vehicle_api_client and config.environment.upper() == "PROD" and session.vehicle_info:
                    estimate = await self.vehicle_api_client.get_repair_estimate(
                        vehicle=session.vehicle_info,
                        repair_description=probable_cause,
                        zip_code=zip_code,
                    )
                    if estimate:
                        price_low = estimate.low_estimate
                        price_high = estimate.high_estimate
                        price_total = estimate.total_estimate
                        price_source = "api_or_cache"
                else:
                    price_low, price_high, price_total, price_source = (250.0, 400.0, 325.0, "mock")
            except Exception as e:
                logger.warning(f"Pricing fetch failed, using mock: {e}")
                price_low, price_high, price_total, price_source = (250.0, 400.0, 325.0, "mock")

            repair_estimate_display = f"${price_low:.0f} - ${price_high:.0f}" if price_low and price_high else "$250 - $400"
            session.services_to_book.append(probable_cause)

            # Log estimate_shown and pricing analytics
            try:
                log_event(
                    "estimate_shown",
                    session.session_id,
                    {
                        "probable_cause": probable_cause,
                        "zip": zip_code,
                        "mileage": session.temp_data.get('new_vehicle_mileage'),
                        "user_type": "returning" if session.customer_profile else "new",
                        "price_low": price_low,
                        "price_high": price_high,
                        "price_total": price_total,
                        "price_source": price_source,
                    },
                )
                # schedule proposed now that estimate shown
                log_event(
                    "schedule_proposed",
                    session.session_id,
                    {"context": "offer_estimate", "probable_cause": probable_cause}
                )
                if self.pricing_manager:
                    vi = session.vehicle_info or VehicleInfo(year=0, make="", model="")
                    self.pricing_manager.track_price_request(
                        vehicle_info=vi,
                        repair_description=probable_cause,
                        zip_code=zip_code,
                        price=price_total or None,
                        source=price_source,
                    )
            except Exception as e:
                logger.warning(f"Analytics logging (estimate_shown/schedule_proposed) failed: {e}")

            # If we have VIN in temp_data (after plate→VIN resolution), attempt recall lookup (non-blocking)
            try:
                vin = session.temp_data.get('vin')
                if vin and self.recall_service:
                    # fire-and-forget style: do not block the conversation
                    async def _recall_task():
                        async with self.recall_service as svc:
                            summary = await svc.get_recalls_by_vin(vin)
                            if summary:
                                # Store JSON-serializable summary subset
                                from dataclasses import asdict as _asdict
                                s_dict = _asdict(summary)
                                # Keep only lightweight fields
                                slim = {
                                    'vin_tail': vin[-4:],
                                    'vehicle_year': s_dict.get('vehicle_year'),
                                    'vehicle_make': s_dict.get('vehicle_make'),
                                    'vehicle_model': s_dict.get('vehicle_model'),
                                    'total_recalls': s_dict.get('total_recalls', 0),
                                    'critical_recalls': s_dict.get('critical_recalls', 0),
                                }
                                session.temp_data['recall_summary'] = slim
                                log_event(
                                    "recall_checked",
                                    session.session_id,
                                    {"vin": f"...{vin[-4:]}", "total_recalls": slim['total_recalls'], "critical": slim['critical_recalls']},
                                )
                    # schedule but don't await
                    import asyncio as _asyncio
                    _asyncio.create_task(_recall_task())
            except Exception as e:
                logger.warning(f"Recall lookup skipped: {e}")

            upsell_mission = self._compute_upsell_mission(session)

            # Build concise recall line if critical recalls found and not yet surfaced
            recall_line = self._get_recall_concise_line(session)

            # mark that we came from estimate path
            session.temp_data['came_from_offer_estimate'] = True

            mission = (
                f"{acknowledgement} For a {probable_cause}, you're looking at about {repair_estimate_display}. "
                f"{upsell_mission} {recall_line} Would you like to schedule this?"
            )

        # --- CHAPTER 4: SCHEDULING & CONFIRMATION ---
        elif state == ConversationState.PROPOSE_SCHEDULING:
            # Enhanced affirmation detection - include time-based confirmations
            user_affirmed = any(word in user_input.lower() for word in ['yes', 'yeah', 'yep', 'correct', 'okay', 'schedule', 'tomorrow', 'today', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
            # Also detect question-confirmations like "Tomorrow, right?"
            if 'right' in user_input.lower() and any(time_word in user_input.lower() for time_word in ['tomorrow', 'today', 'monday', 'tuesday', 'am', 'pm']):
                user_affirmed = True
            
            # Check if user mentioned additional diagnostic symptoms during scheduling
            diagnostic_keywords = ['smell', 'noise', 'sound', 'leak', 'smoke', 'grinding', 'squealing', 'knocking', 'vibration', 'shaking', 'temperature', 'hot', 'overheating', 'sweet', 'burning', 'spot', 'puddle', 'mailing', 'smelling']
            has_new_symptoms = any(keyword in user_input.lower() for keyword in diagnostic_keywords)
            
            if has_new_symptoms and not user_affirmed:
                # User mentioned additional symptoms - transition to diagnostic mode
                logger.info(f"PROPOSE_SCHEDULING: New symptoms detected: '{user_input}' - transitioning to diagnostic")
                session.services_to_book.append("Diagnostic Inspection")
                next_state = ConversationState.DIAGNOSTIC_QUESTIONING
                session.diagnostic_turn_count = 0  # Reset diagnostic count
                mission = f"The user mentioned additional symptoms: '{user_input}'. Acknowledge this concern and ask a targeted diagnostic question to gather more details about this new issue."
                
            else:
                # Normal scheduling flow
                # Check if user already provided time/date info in their scheduling affirmation
                time_words = ['am', 'pm', 'morning', 'afternoon', 'evening', 'tomorrow', 'today', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'august', 'september', 'october', 'november', 'december', 'january', 'february', 'march', 'april', 'may', 'june', 'july']
                has_time_info = any(char.isdigit() for char in user_input) and any(w in user_input.lower() for w in time_words)
            
                if user_affirmed:
                    # If this scheduling comes right after an estimate offer, mark estimate_accepted
                    try:
                        if session.temp_data.get('came_from_offer_estimate'):
                            log_event(
                                "estimate_accepted",
                                session.session_id,
                                {
                                    "probable_cause": session.temp_data.get('probable_cause'),
                                    "mileage": session.temp_data.get('new_vehicle_mileage'),
                                    "zip": config.shop_zip_code,
                                },
                            )
                            session.temp_data['came_from_offer_estimate'] = False
                    except Exception as e:
                        logger.warning(f"Analytics logging (estimate_accepted) failed: {e}")

                    if has_time_info:
                        # User provided time in their affirmation, go straight to confirmation
                        next_state = ConversationState.CONFIRM_APPOINTMENT
                        logger.info(f"PROPOSE_SCHEDULING: User provided time info in affirmation: '{user_input}'")
                        mission = (f"Perfect. You're all set for {user_input}. We'll see you then.")
                    else:
                        # User affirmed but didn't provide time, ask for it
                        next_state = ConversationState.AWAITING_TIMESLOT
                        # Include upsell suggestion here too (even if estimate was skipped)
                        upsell_mission = self._compute_upsell_mission(session)
                        recall_line = self._get_recall_concise_line(session)
                        if upsell_mission:
                            mission = (
                                f"{upsell_mission} {recall_line} If you'd like, we can take care of that during the same visit. "
                                "What day and time works best for you?"
                            )
                        else:
                            extra = f"{recall_line} " if recall_line else ""
                            mission = extra + "What day and time works best for you?"
                else:
                    # Only treat as decline if explicitly negative
                    explicit_decline = any(word in user_input.lower() for word in ['no', 'not', 'don\'t', 'won\'t', 'can\'t', 'cannot'])
                    if explicit_decline:
                        next_state = ConversationState.CONVERSATION_COMPLETE
                        try:
                            log_event(
                                "call_ended",
                                session.session_id,
                                {
                                    "outcome": "declined_scheduling",
                                    "services": session.services_to_book,
                                    "duration_ms": self._compute_call_duration_ms(session),
                                },
                            )
                        except Exception as e:
                            logger.warning(f"Analytics logging (call_ended declined) failed: {e}")
                        mission = (
                            "No problem. Thanks for calling, and feel free to reach out if you change your mind."
                        )
                    else:
                        # Unclear response - ask for clarification
                        next_state = ConversationState.PROPOSE_SCHEDULING
                        mission = "Would you like to schedule an appointment? Just let me know what day and time works best."

        elif state == ConversationState.AWAITING_TIMESLOT:
            user_provided_time = user_input
            # Simple heuristic: detect digits or common time words
            time_words = ['am', 'pm', 'morning', 'afternoon', 'evening', 'tomorrow', 'today', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            has_time_words = any(w in user_provided_time.lower() for w in time_words)
            if any(char.isdigit() for char in user_provided_time) or has_time_words:
                # Extract clean time from potentially garbled input
                clean_time = self._extract_clean_time(user_provided_time)
                next_state = ConversationState.CONFIRM_APPOINTMENT
                mission = (f"Perfect. You're all set for {clean_time}. We'll see you then.")
            else:
                next_state = ConversationState.AWAITING_TIMESLOT
                mission = "The user did not provide a date or time. Politely re-ask the question: 'Sorry, what day and time would you like to book for?'"

        elif state == ConversationState.CONFIRM_APPOINTMENT:
            next_state = ConversationState.CONVERSATION_COMPLETE
            # Log schedule_confirmed
            try:
                log_event(
                    "schedule_confirmed",
                    session.session_id,
                    {
                        "services": session.services_to_book,
                        "upsell": session.upsell_service_description or "",
                    },
                )
                # Log call end with duration
                log_event(
                    "call_ended",
                    session.session_id,
                    {
                        "outcome": "scheduled",
                        "services": session.services_to_book,
                        "duration_ms": self._compute_call_duration_ms(session),
                    },
                )
            except Exception as e:
                logger.warning(f"Analytics logging (schedule_confirmed/call_ended) failed: {e}")
            mission = ("The conversation is over. Provide a simple, final closing statement. "
                        "Say 'Alright, take care.' or 'Have a good one.' "
                        "Do NOT say 'you're welcome' unless the user has just said 'thank you'.")
        
        elif state == ConversationState.CONVERSATION_COMPLETE:
            # Conversation is already finished, provide brief acknowledgment only
            if 'thank you' in user_input.lower():
                mission = "You're welcome. Take care."
            elif any(greeting in user_input.lower() for greeting in ['hi', 'hello', 'hey']):
                mission = "Hi again. If you need anything else, feel free to call back."
            else:
                mission = "Thanks for calling My-Lex Complete Auto Care."
            next_state = ConversationState.CONVERSATION_COMPLETE
        
        # Safety fallback - ensure we always have a mission
        if not mission:
            logger.warning(f"No mission defined for state {state}, using fallback")
            mission = "I'm here to help you with your automotive needs. What can I assist you with today?"
        
        logger.info(f"PREPARE_LLM_TURN: State transition {state} -> {next_state}")
        logger.info(f"PREPARE_LLM_TURN: Mission: {mission[:100]}...")
        
        dynamic_prompt = f"{base_prompt}\n\nYour specific mission for this turn is: {mission}"
        return dynamic_prompt, next_state

    def _determine_probable_cause(self, session: JAIMESSession) -> str:
        """Determine the most likely cause based on comprehensive diagnostic information."""
        conversation_text = ' '.join([msg.get('content', '') for msg in session.conversation_history])
        conversation_text = conversation_text.lower()
        
        # First, try cheat sheet-based diagnosis
        cheat_sheet_diagnosis = self._get_cheat_sheet_diagnosis(conversation_text)
        if cheat_sheet_diagnosis:
            logger.info(f"Cheat sheet diagnosis: {cheat_sheet_diagnosis}")
            return cheat_sheet_diagnosis
        
        # Fallback to traditional diagnostic analysis
        diagnostic_analysis = self._analyze_diagnostic_symptoms(conversation_text)
        
        # Use the analysis to determine the most likely cause
        probable_cause = self._determine_cause_from_analysis(diagnostic_analysis)

        # Heuristic guardrails:
        # - Only bias toward brake issues if user explicitly mentions brake context AND location is brakes
        # - Don't override serpentine belt symptoms (under hood + start/cold + squealing)
        cel_on_flag = session.temp_data.get('cel_on')
        brake_explicit = any(phrase in conversation_text for phrase in ['brake', 'brakes', 'from the brake', 'brake noise'])
        serpentine_context = any(phrase in conversation_text for phrase in ['under the hood', 'hood', 'start', 'starting', 'cold'])
        squeal_flag = 'squealing' in diagnostic_analysis.get('specific_keywords', [])
        
        # Only bias to brakes if explicitly mentioned AND no serpentine belt context
        if brake_explicit and squeal_flag and not serpentine_context and (cel_on_flag is False or cel_on_flag is None):
            probable_cause = 'worn brake pads'

        logger.info(f"Diagnostic analysis: {diagnostic_analysis}")
        logger.info(f"Determined probable cause: {probable_cause}")
        
        return probable_cause

    def _analyze_diagnostic_symptoms(self, conversation_text: str) -> dict:
        """Analyze conversation for comprehensive diagnostic symptoms."""
        analysis = {
            'symptoms': [],
            'conditions': [],
            'locations': [],
            'severity': [],
            'timing': [],
            'specific_keywords': []
        }
        
        # Symptom detection
        symptoms = {
            'noises': ['noise', 'sound', 'humming', 'grinding', 'squealing', 'knocking', 'whining', 'clunking', 'rattling', 'buzzing', 'roaring', 'whistling'],
            'vibrations': ['vibration', 'shaking', 'trembling', 'pulsing', 'wobbling'],
            'performance': ['hesitation', 'stalling', 'rough idle', 'poor acceleration', 'loss of power', 'misfire'],
            'handling': ['pulling', 'drifting', 'wandering', 'loose steering', 'hard steering'],
            'leaks': ['leak', 'drip', 'puddle', 'fluid', 'oil', 'coolant', 'transmission fluid'],
            'smells': ['smell', 'odor', 'burning', 'gas', 'sweet', 'rotten egg'],
            'lights': ['check engine', 'warning light', 'service light', 'abs light', 'traction control'],
            'temperature': ['overheating', 'hot', 'cold', 'temperature'],
            'starting': ['won\'t start', 'hard start', 'cranking', 'clicking'],
            'shifting': ['hard shift', 'slipping', 'jerking', 'delayed shift']
        }
        
        for category, keywords in symptoms.items():
            for keyword in keywords:
                if keyword in conversation_text:
                    analysis['symptoms'].append(category)
                    analysis['specific_keywords'].append(keyword)
        
        # Condition detection
        conditions = {
            'speed_related': ['faster', 'speed', 'accelerate', 'decelerate', 'brake'],
            'temperature_related': ['cold', 'warm', 'hot', 'after driving', 'when starting'],
            'load_related': ['uphill', 'downhill', 'turning', 'straight', 'parking'],
            'time_related': ['constant', 'intermittent', 'comes and goes', 'getting worse', 'getting better']
        }
        
        for category, keywords in conditions.items():
            for keyword in keywords:
                if keyword in conversation_text:
                    analysis['conditions'].append(category)
                    analysis['specific_keywords'].append(keyword)
        
        # Location detection
        locations = {
            'front': ['front', 'forward', 'hood', 'engine bay'],
            'rear': ['back', 'rear', 'trunk', 'tail'],
            'left': ['left', 'driver side'],
            'right': ['right', 'passenger side'],
            'under': ['under', 'beneath', 'below'],
            'inside': ['inside', 'interior', 'cabin'],
            'engine': ['engine', 'motor'],
            'transmission': ['transmission', 'gearbox'],
            'wheels': ['wheel', 'tire', 'rim'],
            'brakes': ['brake', 'rotor', 'caliper']
        }
        
        for category, keywords in locations.items():
            for keyword in keywords:
                if keyword in conversation_text:
                    analysis['locations'].append(category)
                    analysis['specific_keywords'].append(keyword)
        
        return analysis

    def _compute_diagnostic_confidence(self, session: JAIMESSession, analysis: dict) -> float:
        """Compute a conservative confidence score (0.0–1.0) for the current diagnostic hypothesis.
        Factors:
        - Coverage: proportion of key categories answered (symptoms/conditions/locations/severity)
        - Consistency: absence of contradictory signals (e.g., CEL off but engine/misfire focus)
        - Pattern match: known strong patterns (e.g., front + squeal + braking → pads)
        - Turn count: at least two turns before fast-path
        """
        coverage = 0.0
        covered = 0
        categories = 4
        if analysis.get('symptoms'): covered += 1
        if analysis.get('conditions'): covered += 1
        if analysis.get('locations'): covered += 1
        if analysis.get('severity'): covered += 1
        coverage = covered / categories

        # Contradictions: penalize if CEL focus while cel_on is False
        cel_flag = session.temp_data.get('cel_on')
        specific = set(analysis.get('specific_keywords', []))
        contradiction = 0.0
        if cel_flag is False and any(k in specific for k in ['misfire', 'check engine', 'rough idle']):
            contradiction = 0.3

        # Pattern bonuses
        pattern = 0.0
        brake_context = ('brake' in specific or 'brakes' in specific) or ('brakes' in analysis.get('locations', []))
        squeal = 'squealing' in specific
        braking_condition = any(k in analysis.get('conditions', []) for k in ['speed_related']) or 'brake' in specific
        if brake_context and squeal and braking_condition and (cel_flag is False or cel_flag is None):
            pattern = 0.4  # strong brake-pad signature

        # Additional conservative patterns (engine belts, CV axle, suspension, exhaust, cooling, charging, starter, transmission)
        text_all = ' '.join([m.get('content', '') for m in session.conversation_history]).lower()
        # Serpentine/belt drive (cold start squeal; changes with AC/steering/RPM)
        if ('squeal' in text_all or 'squealing' in text_all) and any(k in text_all for k in ['start', 'cold', 'under the hood', 'hood']):
            pattern = max(pattern, 0.25)
        if ('squeal' in text_all or 'squealing' in text_all) and any(k in text_all for k in ['ac', 'air conditioning', 'steering', 'turning the wheel', 'rpm']):
            pattern = max(pattern, 0.25)
        # CV axle clicking when turning
        if 'click' in text_all and any(k in text_all for k in ['turn', 'turning']) and any(k in text_all for k in ['front', 'wheel']):
            pattern = max(pattern, 0.35)
        # Suspension clunk over bumps
        if any(k in text_all for k in ['clunk', 'rattle']) and any(k in text_all for k in ['bump', 'rough road', 'pothole']):
            pattern = max(pattern, 0.25)
        # Exhaust heat shield / catalytic rattle
        if 'rattle' in text_all and any(k in text_all for k in ['under the car', 'metallic', 'certain rpm', 'rpm']):
            pattern = max(pattern, 0.2)
        # Cooling sweet smell/overheat
        if any(k in text_all for k in ['sweet smell', 'maple syrup', 'coolant']) or ('overheat' in text_all and 'coolant' in text_all):
            pattern = max(pattern, 0.3)
        # Charging/alternator
        if any(k in text_all for k in ['battery light', 'alternator']) or ('whine' in text_all and 'rpm' in text_all):
            pattern = max(pattern, 0.3)
        # Starter no-crank clicking
        if any(k in text_all for k in ['click', 'clicking', 'just clicks', 'single click', 'rapid click']) and any(s in text_all for s in ['won\'t start', 'wont start', 'not start', 'no start']):
            pattern = max(pattern, 0.4)  # Higher confidence for starter issues
        # Transmission slipping/delayed shift
        if any(k in text_all for k in ['slip', 'slipping', 'delayed shift', 'harsh shift', 'rpm flare']):
            pattern = max(pattern, 0.35)

        # Enhanced cheat sheet matching - now the primary diagnostic engine
        try:
            if self.diagnostic_cheat_sheet:
                text = ' '.join([m.get('content', '') for m in session.conversation_history]).lower()
                cheat_sheet_boost = self._analyze_cheat_sheet_patterns(text)
                pattern += cheat_sheet_boost
                logger.info(f"Cheat sheet boost: {cheat_sheet_boost:.2f}")
        except Exception as e:
            logger.debug(f"Cheat sheet boost skipped: {e}")

        # Base score from coverage and patterns
        score = 0.5 * coverage + pattern
        score = max(0.0, score - contradiction)
        # Cap to [0,1]
        return min(1.0, score)

    def _analyze_cheat_sheet_patterns(self, conversation_text: str) -> float:
        """Analyze conversation against diagnostic cheat sheet for intelligent pattern matching."""
        if not self.diagnostic_cheat_sheet:
            return 0.0
        
        best_match_score = 0.0
        best_match_info = None
        
        for category in self.diagnostic_cheat_sheet.get('categories', []):
            for item in category.get('items', []):
                for symptom_example in item.get('symptom_examples', []):
                    match_score = self._calculate_symptom_match_score(conversation_text, symptom_example)
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_info = {
                            'category': category.get('category'),
                            'symptom': symptom_example,
                            'problems': item.get('potential_problems', []),
                            'repairs': item.get('common_repairs', [])
                        }
        
        if best_match_info and best_match_score > 0.3:
            logger.info(f"Cheat sheet match: {best_match_info['symptom']} (score: {best_match_score:.2f})")
            logger.info(f"Potential problems: {best_match_info['problems'][:2]}")  # Log top 2
            return min(0.4, best_match_score)  # Cap the boost to prevent overconfidence
        
        return 0.0
    
    def _calculate_symptom_match_score(self, conversation_text: str, symptom_example: str) -> float:
        """Calculate how well a symptom example matches the conversation."""
        conv_words = set(conversation_text.lower().split())
        symptom_words = set(symptom_example.lower().split())
        
        # Remove common words that don't add diagnostic value
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'i', 'my', 'is', 'it', 'when', 'from', 'under', 'car', 'vehicle'}
        conv_words -= stop_words
        symptom_words -= stop_words
        
        if not symptom_words:
            return 0.0
        
        # Calculate word overlap
        overlap = len(conv_words & symptom_words)
        total_symptom_words = len(symptom_words)
        
        # Base score from word overlap
        base_score = overlap / total_symptom_words
        
        # CRITICAL: Prioritize cooling system symptoms
        cooling_system_phrases = ['sweet smell', 'overheating', 'coolant', 'green fluid', 'maple syrup']
        if any(phrase in conversation_text.lower() for phrase in cooling_system_phrases) and any(phrase in symptom_example.lower() for phrase in cooling_system_phrases):
            base_score += 0.6  # Strong boost for cooling system matches
        
        # Bonus for key diagnostic keywords
        diagnostic_keywords = {
            'squealing', 'clicking', 'grinding', 'humming', 'knocking', 'clunking',
            'won\'t start', 'hard start', 'slow crank', 'just clicks',
            'overheating', 'leaking', 'vibration', 'shaking', 'rattling'
        }
        
        # Check for exact phrase matches
        for keyword in diagnostic_keywords:
            if keyword in conversation_text and keyword in symptom_example.lower():
                base_score += 0.3  # Significant bonus for exact diagnostic phrase matches
        
        # Penalty for mismatched categories (prevent false positives)
        if 'rattling' in symptom_example.lower() and ('overheating' in conversation_text.lower() or 'sweet' in conversation_text.lower()):
            base_score -= 0.5  # Strong penalty for cooling issues matched to noise issues
        
        # Check for semantic similarity (basic version)
        if 'start' in symptom_example.lower() and any(w in conversation_text for w in ['start', 'starting', 'won\'t start', 'wont start']):
            base_score += 0.2
        if 'click' in symptom_example.lower() and any(w in conversation_text for w in ['click', 'clicking', 'clicks']):
            base_score += 0.2
        if 'squeal' in symptom_example.lower() and any(w in conversation_text for w in ['squeal', 'squealing', 'squeak']):
            base_score += 0.2
        
        return min(1.0, max(0.0, base_score))

    def _get_cheat_sheet_diagnosis(self, conversation_text: str) -> Optional[str]:
        """Get the most likely diagnosis from the cheat sheet based on conversation."""
        if not self.diagnostic_cheat_sheet:
            return None
        
        best_match_score = 0.0
        best_diagnosis = None
        
        for category in self.diagnostic_cheat_sheet.get('categories', []):
            for item in category.get('items', []):
                for symptom_example in item.get('symptom_examples', []):
                    match_score = self._calculate_symptom_match_score(conversation_text, symptom_example)
                    if match_score > best_match_score:
                        best_match_score = match_score
                        # Use the first (most likely) potential problem as diagnosis
                        potential_problems = item.get('potential_problems', [])
                        if potential_problems:
                            best_diagnosis = potential_problems[0]
        
        # Only return diagnosis if we have high confidence
        if best_match_score > 0.5:
            logger.info(f"High confidence cheat sheet diagnosis: {best_diagnosis} (score: {best_match_score:.2f})")
            return best_diagnosis
        
        return None

    def _cleanup_caches(self):
        """Clean up performance caches to prevent memory leaks"""
        try:
            # Keep only the 100 most recent cache entries for each cache
            if len(self._accent_cache) > 100:
                # Keep most recent 50 entries
                keys_to_remove = list(self._accent_cache.keys())[:-50]
                for key in keys_to_remove:
                    del self._accent_cache[key]
                logger.debug(f"Cleaned accent cache, removed {len(keys_to_remove)} entries")
            
            if len(self._intelligence_cache) > 100:
                # Keep most recent 50 entries
                keys_to_remove = list(self._intelligence_cache.keys())[:-50]
                for key in keys_to_remove:
                    del self._intelligence_cache[key]
                logger.debug(f"Cleaned intelligence cache, removed {len(keys_to_remove)} entries")
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")

    def _standard_vehicle_confirmation_logic(self, session: JAIMESSession, user_input: str) -> str:
        """Standard vehicle confirmation logic fallback"""
        if session.customer_profile and session.customer_profile.vehicles:
            vehicles = [f"{v.year} {v.make} {v.model}" for v in session.customer_profile.vehicles]
            joined = ' or '.join(vehicles[:2]) if len(vehicles) <= 2 else ', '.join(vehicles[:-1]) + f", or {vehicles[-1]}"
            return ("The user confirmed who they are. Confirm the vehicle rather than changing it. "
                   f"Say something like: 'I have {joined} on file. Which one are we working with today?' Then, once they pick, ask what's going on with that vehicle.")
        else:
            return "The user confirmed who they are. Move to service intake and ask what brings them in today."

    def _get_cheat_sheet_guided_questions(self, conversation_text: str) -> List[str]:
        """Generate diagnostic questions based on cheat sheet patterns."""
        if not self.diagnostic_cheat_sheet:
            return []
        
        # Find the best matching symptom category
        best_match_score = 0.0
        best_category_info = None
        
        for category in self.diagnostic_cheat_sheet.get('categories', []):
            for item in category.get('items', []):
                for symptom_example in item.get('symptom_examples', []):
                    match_score = self._calculate_symptom_match_score(conversation_text, symptom_example)
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_category_info = {
                            'category': category.get('category'),
                            'symptom': symptom_example,
                            'problems': item.get('potential_problems', []),
                            'repairs': item.get('common_repairs', [])
                        }
        
        if not best_category_info or best_match_score < 0.3:
            return []
        
        # Generate targeted questions based on the matched category
        questions = []
        category_name = best_category_info['category']
        
        if category_name == 'noises':
            if 'start' in best_category_info['symptom'].lower():
                questions = [
                    "Does this squealing happen only when you first start the car, or while driving too?",
                    "Does the noise change when you turn on the air conditioning?",
                    "Is it more noticeable when the engine is cold?"
                ]
            elif 'brake' in best_category_info['symptom'].lower():
                questions = [
                    "Does the squealing happen only when you're braking, or while driving too?",
                    "Where do you hear it coming from - front, back, left, or right?",
                    "How long has this been happening?"
                ]
            elif 'click' in best_category_info['symptom'].lower():
                questions = [
                    "Is it a single click or rapid clicking?",
                    "Does it happen every time you turn the key?",
                    "Do any dashboard lights come on when you try to start?"
                ]
        
        elif category_name == 'performance':
            if 'start' in best_category_info['symptom'].lower():
                questions = [
                    "When you turn the key, do you hear clicking, slow cranking, or nothing at all?",
                    "How old is your battery, if you know?",
                    "Have you tried jump-starting it?"
                ]
        
        elif category_name == 'feel_handling':
            questions = [
                "Does this happen at all speeds or only at certain speeds?",
                "Do you feel it in the steering wheel, seat, or throughout the car?",
                "Is it worse during acceleration, braking, or constant speed?"
            ]
        
        return questions[:2]  # Return top 2 most relevant questions

    def _determine_fast_path_reason(self, session: JAIMESSession, analysis: dict) -> Optional[str]:
        """Return a short reason string for why we think fast-path is justified."""
        specific = set(analysis.get('specific_keywords', []))
        locations = set(analysis.get('locations', []))
        text_all = ' '.join([m.get('content', '') for m in session.conversation_history]).lower()
        cel_flag = session.temp_data.get('cel_on')
        
        # Belt (check first - higher priority for under hood + start context)
        if ('squeal' in text_all or 'squealing' in text_all) and any(k in text_all for k in ['start', 'cold', 'under the hood', 'hood', 'ac', 'air conditioning', 'steering']):
            return 'serpentine_belt_signature'
        
        # Brakes (only if explicitly mentioned brake context AND no belt context)
        brake_explicit = any(phrase in text_all for phrase in ['brake', 'brakes', 'from the brake', 'brake noise'])
        if ('squealing' in specific or 'squeal' in text_all) and brake_explicit:
            if cel_flag is False or cel_flag is None:
                return 'brake_squeal_signature'
        # CV axle
        if 'click' in text_all and 'turn' in text_all:
            return 'cv_axle_turn_click_signature'
        # Cooling
        if any(k in text_all for k in ['sweet smell', 'maple syrup', 'coolant']) or 'overheat' in text_all:
            return 'cooling_system_signature'
        # Charging
        if 'battery light' in text_all or ('whine' in text_all and 'rpm' in text_all):
            return 'alternator_charging_signature'
        # Starter (broad pattern for no-start + clicking)
        if any(s in text_all for s in ['won\'t start', 'wont start', 'not start', 'no start']) and any(c in text_all for c in ['click', 'clicking']):
            return 'starter_no_crank_signature'
        # Transmission
        if any(k in text_all for k in ['slip', 'slipping', 'delayed shift', 'harsh shift', 'rpm flare']):
            return 'transmission_slip_signature'
        return None

    def _determine_cause_from_analysis(self, analysis: dict) -> str:
        """Determine the most likely cause based on comprehensive symptom analysis."""
        symptoms = analysis['symptoms']
        conditions = analysis['conditions']
        locations = analysis['locations']
        keywords = analysis['specific_keywords']
        
        # Comprehensive diagnostic decision tree
        if 'noises' in symptoms:
            if 'humming' in keywords:
                if 'speed_related' in conditions and 'front' in locations:
                    return 'front wheel bearing issue'
                elif 'speed_related' in conditions and 'rear' in locations:
                    return 'rear wheel bearing issue'
                elif 'speed_related' in conditions:
                    return 'wheel bearing issue'
                elif 'engine' in locations:
                    return 'engine accessory drive issue (alternator, water pump, or power steering pump)'
                else:
                    return 'wheel bearing or tire issue'
            
            elif 'squealing' in keywords:
                # Prioritize brake context over engine context for squealing
                if 'brakes' in locations or 'brake' in keywords:
                    return 'worn brake pads'
                elif 'engine' in locations or 'front' in locations:
                    if 'temperature_related' in conditions:
                        return 'serpentine belt or belt tensioner issue'
                    else:
                        return 'serpentine belt issue'
                else:
                    return 'belt or brake system issue'
            
            elif 'grinding' in keywords:
                if 'brakes' in locations or 'brake' in keywords:
                    return 'worn brake pads or rotors'
                elif 'speed_related' in conditions:
                    return 'wheel bearing or brake issue'
                else:
                    return 'mechanical grinding issue requiring inspection'
            
            elif 'knocking' in keywords:
                if 'engine' in locations:
                    return 'engine mechanical issue (rod knock, piston slap, or valve train)'
                elif 'speed_related' in conditions:
                    return 'wheel bearing or suspension issue'
                else:
                    return 'mechanical knocking issue'
            
            elif 'whining' in keywords:
                if 'engine' in locations:
                    return 'power steering pump or alternator issue'
                elif 'speed_related' in conditions:
                    return 'wheel bearing or differential issue'
                else:
                    return 'bearing or pump issue'
            
            elif 'clunking' in keywords:
                if 'speed_related' in conditions:
                    return 'suspension or steering component issue'
                elif 'turning' in keywords:
                    return 'CV joint or steering component issue'
                else:
                    return 'suspension or steering issue'
        
        # Vibration analysis
        elif 'vibrations' in symptoms:
            if 'speed_related' in conditions:
                if 'steering wheel' in keywords or 'front' in locations:
                    return 'wheel balance or alignment issue'
                elif 'seat' in keywords or 'rear' in locations:
                    return 'wheel balance or driveshaft issue'
                else:
                    return 'wheel balance or tire issue'
            else:
                return 'engine mount or suspension issue'
        
        # Performance issues
        elif 'performance' in symptoms:
            if 'hesitation' in keywords or 'misfire' in keywords:
                return 'ignition system or fuel system issue'
            elif 'stalling' in keywords:
                return 'fuel system or electrical issue'
            elif 'rough idle' in keywords:
                return 'engine mechanical or fuel system issue'
            else:
                return 'engine performance issue requiring diagnostic'
        
        # Handling issues
        elif 'handling' in symptoms:
            if 'pulling' in keywords:
                return 'alignment or brake issue'
            elif 'wandering' in keywords or 'loose steering' in keywords:
                return 'steering or suspension component issue'
            else:
                return 'steering or suspension issue'
        
        # Leak analysis
        elif 'leaks' in symptoms:
            if 'oil' in keywords:
                return 'engine oil leak'
            elif 'coolant' in keywords or 'sweet' in keywords:
                return 'cooling system leak'
            elif 'transmission' in keywords:
                return 'transmission fluid leak'
            else:
                return 'fluid leak requiring inspection'
        
        # Starting issues
        elif 'starting' in symptoms:
            if any(k in keywords for k in ['won\'t start', 'wont start', 'not start']) and 'clicking' in keywords:
                return 'starter motor'  # More specific for won't start + clicking
            elif any(k in keywords for k in ['won\'t start', 'wont start', 'not start']):
                return 'battery, starter, or electrical issue'
            elif 'hard start' in keywords:
                return 'fuel system or ignition issue'
            elif 'clicking' in keywords:
                return 'battery or starter issue'
            else:
                return 'starting system issue'
        
        # Transmission issues
        elif 'shifting' in symptoms:
            if 'hard shift' in keywords:
                return 'transmission mechanical issue'
            elif 'slipping' in keywords:
                return 'transmission clutch or band issue'
            else:
                return 'transmission issue requiring diagnostic'
        
        # Temperature issues
        elif 'temperature' in symptoms:
            if 'overheating' in keywords:
                return 'cooling system issue'
            else:
                return 'temperature regulation issue'
        
        # Check engine light
        elif 'lights' in symptoms:
            return 'engine diagnostic issue requiring scan tool'
        
        # If we have location but unclear symptoms
        elif locations:
            if 'front' in locations:
                return 'front suspension or steering issue'
            elif 'rear' in locations:
                return 'rear suspension or brake issue'
            elif 'engine' in locations:
                return 'engine mechanical issue'
            else:
                return 'mechanical issue requiring inspection'
        
        # Default fallback
        else:
            return 'mechanical issue requiring diagnostic inspection'

    def _has_sufficient_diagnostic_info(self, session: JAIMESSession) -> bool:
        """Determine if we have enough diagnostic information for a confident diagnosis."""
        conversation_text = ' '.join([msg.get('content', '') for msg in session.conversation_history])
        conversation_text = conversation_text.lower()
        
        # Key diagnostic indicators we need to identify a problem
        diagnostic_indicators = {
            'symptoms': ['noise', 'sound', 'vibration', 'shaking', 'leak', 'smoke', 'smell', 'light', 'warning'],
            'conditions': ['driving', 'idling', 'starting', 'stopping', 'turning', 'accelerating', 'braking'],
            'locations': ['engine', 'transmission', 'brakes', 'wheels', 'front', 'back', 'side', 'under'],
            'severity': ['loud', 'quiet', 'constant', 'intermittent', 'getting worse', 'getting better']
        }
        
        # Count how many categories we have information for
        categories_with_info = 0
        for category, keywords in diagnostic_indicators.items():
            if any(keyword in conversation_text for keyword in keywords):
                categories_with_info += 1
        
        # We need at least 3 out of 4 categories to have sufficient info
        return categories_with_info >= 3

    def _get_next_diagnostic_question(self, session: JAIMESSession, user_input: str) -> str:
        """Generate the next most appropriate diagnostic question based on conversation history.
        Enhanced with cheat sheet-guided questioning for better diagnostic accuracy.
        """
        conversation_text = ' '.join([msg.get('content', '') for msg in session.conversation_history])
        conversation_text = (conversation_text + " " + user_input).lower()

        # First, try to get cheat sheet-guided questions
        cheat_sheet_questions = self._get_cheat_sheet_guided_questions(conversation_text)
        if cheat_sheet_questions:
            # Return the most relevant cheat sheet question
            return cheat_sheet_questions[0]

        analysis = self._analyze_diagnostic_symptoms(conversation_text)
        keywords = set(analysis.get('specific_keywords', []))
        locations = set(analysis.get('locations', []))

        # Context signals - make them mutually exclusive and more specific
        starting_ctx = any(k in keywords for k in ['won\'t start', 'wont start', 'not start', 'no start', 'hard start', 'clicking'])
        brake_ctx = ('brake' in keywords or 'brakes' in keywords or 'brakes' in locations) and any(k in keywords for k in ['squealing', 'grinding', 'noise']) and not starting_ctx
        leak_smell_ctx = any(k in keywords for k in ['leak', 'puddle', 'smell', 'odor', 'sweet', 'burning', 'coolant']) and not starting_ctx
        cel_engine_ctx = (any(k in keywords for k in ['check engine', 'misfire', 'hesitation', 'rough idle', 'loss of power']) or session.temp_data.get('cel_on') is True) and not starting_ctx
        vibration_ctx = (any(k in keywords for k in ['vibration', 'wobbling']) or any(k in analysis.get('conditions', []) for k in ['speed_related'])) and not starting_ctx
        transmission_ctx = any(k in keywords for k in ['hard shift', 'slipping', 'delayed shift']) and not starting_ctx
        temp_ctx = any(k in keywords for k in ['overheating', 'hot', 'temperature']) and not starting_ctx

        # Build a relevant question list based on context
        candidate_questions: list[str] = []

        if brake_ctx:
            candidate_questions += [
                "Where exactly do you hear the brake noise — front, back, left, or right?",
                "Does the noise happen mostly when you're braking, or do you hear it while driving too?",
                "Is the noise constant or does it come and go?",
                "On a scale of 1 to 10, how severe is the noise?",
                "How long has this been happening, and is it getting worse?",
                "Do you feel any vibration in the steering wheel when braking?",
                "Have you had any recent brake work or tire rotations?",
            ]

        if leak_smell_ctx:
            candidate_questions += [
                "Have you noticed any fluid under the car — and if so, what color was it?",
                "Do you smell anything like burning, gas, or a sweet odor when this happens?",
                "Does the temperature gauge ever run hotter than normal?",
            ]

        if cel_engine_ctx:
            # Only ask CEL if not already known false
            if session.temp_data.get('cel_on') is None:
                candidate_questions.append("Is your Check Engine Light on right now, or has it come on recently?")
            candidate_questions += [
                "Do you notice any hesitation or loss of power when accelerating?",
                "Does the engine idle smoothly, or does it feel rough?",
            ]

        if vibration_ctx:
            candidate_questions += [
                "Do you feel the vibration more in the steering wheel or the seat?",
                "Does the vibration change with speed — better or worse on the highway?",
            ]

        if transmission_ctx:
            candidate_questions += [
                "Does the transmission shift smoothly, or do you feel any slipping or delays?",
                "Do you hear any noises when shifting gears?",
            ]

        if starting_ctx:
            candidate_questions += [
                "When you turn the key, does it make a clicking sound, crank slowly, or nothing at all?",
                "Is it a rapid clicking or just one click?",
                "When did this problem start - was it gradual or sudden?",
                "Have you tried jump-starting the battery?",
                "Do any lights come on when you turn the key?",
                "How old is the battery, if you happen to know?",
            ]

        if temp_ctx:
            candidate_questions += [
                "Have you seen the temperature gauge go higher than normal?",
                "Have you noticed the heater or AC acting differently?",
            ]

        # If we didn't detect a strong context, fall back to a minimal, sensible core
        if not candidate_questions:
            candidate_questions = [
                "Does this happen while driving, idling, or starting the car?",
                "Where exactly do you notice it — front, back, left, or right?",
                "Is it constant or does it come and go?",
                "How long has this been happening?",
            ]

        # Build answered set by simple keyword match
        answered = set()
        for q in candidate_questions:
            if any(k in conversation_text for k in self._extract_keywords_from_question(q)):
                answered.add(q)

        # Skip CEL-oriented questions if we already know cel_on is False
        if session.temp_data.get('cel_on') is False:
            candidate_questions = [q for q in candidate_questions if 'check engine' not in q.lower()]

        # Return the first unanswered relevant question
        for q in candidate_questions:
            if q not in answered:
                return q

        # If all relevant are answered, ask for additional detail
        return "Can you tell me more about when this first started and whether it's getting better or worse?"

    def _extract_keywords_from_question(self, question: str) -> list:
        """Extract key diagnostic keywords from a question to check if it's been answered."""
        question_lower = question.lower()
        keywords = []
        
        if 'check engine light' in question_lower:
            keywords.extend(['check engine', 'light on', 'warning light'])
        elif 'driving' in question_lower and 'idling' in question_lower:
            keywords.extend(['driving', 'idling', 'starting'])
        elif 'noises' in question_lower:
            keywords.extend(['noise', 'sound', 'grinding', 'squealing', 'knocking', 'humming'])
        elif 'smell' in question_lower:
            keywords.extend(['smell', 'odor', 'burning', 'gas'])
        elif 'leaks' in question_lower:
            keywords.extend(['leak', 'puddle', 'fluid'])
        elif 'where' in question_lower:
            keywords.extend(['front', 'back', 'left', 'right', 'side'])
        elif 'accelerate' in question_lower:
            keywords.extend(['accelerate', 'brake', 'speed'])
        elif 'steering' in question_lower:
            keywords.extend(['steering', 'turn', 'wheel'])
        elif 'constant' in question_lower:
            keywords.extend(['constant', 'intermittent', 'comes and goes'])
        elif 'long' in question_lower:
            keywords.extend(['how long', 'when', 'started'])
        elif 'worse' in question_lower:
            keywords.extend(['worse', 'better', 'improved'])
        elif 'cold' in question_lower:
            keywords.extend(['cold', 'warm', 'temperature'])
        elif 'handles' in question_lower:
            keywords.extend(['handles', 'drives', 'behavior'])
        elif 'hesitate' in question_lower:
            keywords.extend(['hesitate', 'stumble', 'acceleration'])
        elif 'fuel economy' in question_lower:
            keywords.extend(['fuel', 'economy', 'mileage'])
        elif 'idle' in question_lower:
            keywords.extend(['idle', 'rough', 'smooth'])
        elif 'starting' in question_lower:
            keywords.extend(['start', 'cranking', 'clicking'])
        elif 'pull' in question_lower:
            keywords.extend(['pull', 'side', 'drift'])
        elif 'vibration' in question_lower:
            keywords.extend(['vibration', 'steering wheel', 'seat'])
        elif 'transmission' in question_lower:
            keywords.extend(['transmission', 'shift', 'gear'])
        elif 'slipping' in question_lower:
            keywords.extend(['slipping', 'losing power'])
        elif 'overheating' in question_lower:
            keywords.extend(['overheating', 'hot', 'temperature'])
        elif 'air conditioning' in question_lower:
            keywords.extend(['air conditioning', 'heating', 'ac'])
        elif 'recent work' in question_lower:
            keywords.extend(['recent work', 'maintenance', 'service'])
        elif 'changed' in question_lower:
            keywords.extend(['changed', 'tires', 'oil', 'parts'])
        elif 'severe' in question_lower:
            keywords.extend(['severe', 'scale', '1 to 10'])
        elif 'safely' in question_lower:
            keywords.extend(['safely', 'safety', 'dangerous'])
        elif 'urgently' in question_lower:
            keywords.extend(['urgently', 'urgent', 'quickly'])
        
        return keywords

    def _mileage_to_words(self, mileage: int) -> str:
        """Convert mileage numbers to words for speech (e.g., 60000 -> 'sixty thousand')."""
        try:
            if mileage == 30000:
                return "thirty thousand"
            elif mileage == 60000:
                return "sixty thousand" 
            elif mileage == 90000:
                return "ninety thousand"
            else:
                # For other numbers, use num2words and clean up
                words = num2words(mileage)
                return words.replace('-', ' ')
        except:
            return str(mileage)
    
    def _extract_clean_time(self, user_input: str) -> str:
        """Extract clean time from potentially garbled user input."""
        # Common patterns to extract meaningful time information
        time_patterns = [
            r'(\w+day)\s+at\s+(\d{1,2})\s*(am|pm)',  # "Wednesday at 8 AM"
            r'(\w+day)\s+(\d{1,2})\s*(am|pm)',       # "Wednesday 8 AM"
            r'(\d{1,2})\s*(am|pm)\s+(\w+day)',       # "8 AM Wednesday"
            r'(\w+day)',                              # Just day
            r'(\d{1,2})\s*(am|pm)',                   # Just time
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                groups = match.groups()
                if len(groups) == 3:  # Day + time + am/pm
                    day, time, period = groups
                    return f"{day.capitalize()} at {time} {period.upper()}"
                elif len(groups) == 2:  # Time + am/pm
                    time, period = groups
                    return f"{time} {period.upper()}"
                elif len(groups) == 1:  # Just day or time
                    return groups[0].capitalize()
        
        # Fallback: look for day names
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            if day in user_input.lower():
                # Try to find time with this day
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', user_input.lower())
                if time_match:
                    time, period = time_match.groups()
                    return f"{day.capitalize()} at {time} {period.upper()}"
                return day.capitalize()
        
        # Last resort: return something reasonable
        return user_input.strip()

    def _compute_upsell_mission(self, session: JAIMESSession) -> str:
        """Compute upsell message for 30k/60k/90k services based on mileage in session."""
        try:
            mileage_str = session.temp_data.get('new_vehicle_mileage', '0')
            logger.info(f"Raw mileage string (for upsell): '{mileage_str}'")
            
            # Handle common transcription errors and patterns
            mileage_lower = str(mileage_str).lower()
            current_mileage = 0
            
            # Look for explicit thousand/k patterns first
            if 'thousand' in mileage_lower or 'k' in mileage_lower:
                # Extract the first number and multiply by 1000
                numbers = re.findall(r'\d+', mileage_lower)
                if numbers:
                    current_mileage = int(numbers[0]) * 1000
            else:
                # Extract all numbers and try to determine correct mileage
                numbers = re.findall(r'\d+', mileage_str)
                if numbers:
                    # If we have multiple numbers, take the largest reasonable one
                    # Most cars have mileage between 10k-200k
                    candidates = [int(n) for n in numbers if 10000 <= int(n) <= 250000]
                    if candidates:
                        current_mileage = max(candidates)  # Take the highest reasonable mileage
                    else:
                        # If no reasonable candidates, try concatenating
                        all_digits = ''.join(numbers)
                        if len(all_digits) >= 4:
                            current_mileage = int(all_digits[:6])  # Take first 6 digits max
                        else:
                            current_mileage = int(all_digits) if all_digits else 0
        except Exception as e:
            logger.warning(f"Mileage parse failed for upsell: '{session.temp_data.get('new_vehicle_mileage')}', error: {e}")
            current_mileage = 0

        upsell_mission = ""
        if 25000 <= current_mileage < 30000:
            upsell_mission = "Also, just a heads-up, I see you're getting close to your thirty-thousand-mile service."
        elif 30000 <= current_mileage <= 35000:
            upsell_mission = "Also, just a heads-up, I see your vehicle is in the range for its thirty-thousand-mile service. Have you had that done recently?"
        elif 55000 <= current_mileage < 60000:
            upsell_mission = "Also, I see you're getting close to your sixty-thousand-mile service. We could take care of that during the same visit if you'd like."
        elif 60000 <= current_mileage <= 65000:
            upsell_mission = "Also, I see your vehicle is in the range for its sixty-thousand-mile service. Have you had that done recently?"
        elif 85000 <= current_mileage < 90000:
            upsell_mission = "Also, I see you're getting close to your ninety-thousand-mile service. We could take care of that during the same visit if you'd like."
        elif 90000 <= current_mileage <= 95000:
            upsell_mission = "Also, I see your vehicle is in the range for its ninety-thousand-mile service. Have you had that done recently?"

        logger.info(f"Computed upsell_mission: '{upsell_mission}' for mileage: {current_mileage}")
        session.upsell_service_description = upsell_mission
        return upsell_mission

    @groq_circuit_breaker()
    @groq_retry()
    async def _call_llm_and_stream(
        self, system_prompt: str, session: JAIMESSession
    ) -> AsyncGenerator[str, None]:
        llm_messages = [
            {"role": "system", "content": system_prompt}
        ] + session.conversation_history
        full_response_for_history = ""
        try:
            logger.info(f"Making LLM call for session {session.session_id}")
            chat_completion_stream = await self.groq_client.chat.completions.create(
                messages=llm_messages, model=self.groq_model, stream=True
            )
            async for chunk in chat_completion_stream:
                content = chunk.choices[0].delta.content
                if content:
                    processed_content = content.replace("!", ".")
                    full_response_for_history += processed_content
                    yield processed_content
            logger.info(f"LLM Mission Response: '{full_response_for_history}'")
        except Exception as e:
            logger.error(
                f"Error during LLM call for session {session.session_id}: {e}",
                exc_info=True,
            )
            # Enhanced error handling with circuit breaker awareness
            if "CircuitBreakerError" in str(type(e)):
                error_message = "Our AI is experiencing high demand. Please try again in a moment."
            else:
                error_message = "I'm having a temporary technical issue. Please give me a moment."
            yield error_message

    @groq_circuit_breaker()
    @groq_retry()
    async def _call_llm_and_stream_enhanced(
        self, system_prompt: str, session: JAIMESSession, streaming_mode: StreamingMode, session_id: str
    ) -> AsyncGenerator[str, None]:
        """Enhanced LLM streaming with intelligent pacing"""
        llm_messages = [
            {"role": "system", "content": system_prompt}
        ] + session.conversation_history
        full_response_for_history = ""
        
        try:
            # Get streaming configuration for the mode
            config = self.streaming_manager.configs.get(streaming_mode, self.streaming_manager.configs[StreamingMode.INFORMATION])
            
            chat_completion_stream = await self.groq_client.chat.completions.create(
                messages=llm_messages, model=self.groq_model, stream=True
            )
            
            word_buffer = ""
            async for chunk in chat_completion_stream:
                content = chunk.choices[0].delta.content
                if content:
                    processed_content = content.replace("!", ".")
                    full_response_for_history += processed_content
                    word_buffer += processed_content
                    
                    # Process word-by-word with enhanced timing
                    words = word_buffer.split()
                    if len(words) > 1:
                        # Yield all complete words except the last (might be incomplete)
                        for word in words[:-1]:
                            yield word + " "
                            # Apply intelligent delay based on streaming mode
                            delay = config.base_delay
                            if word.lower() in self.streaming_manager.emphasis_words:
                                delay += config.emphasis_delay
                            if word.endswith(('.', '!', '?')):
                                delay += config.sentence_end_delay
                            elif word.endswith((',', ';', ':')):
                                delay += config.punctuation_delay
                            
                            if delay > 0:
                                await asyncio.sleep(delay)
                        
                        # Keep the last incomplete word in buffer
                        word_buffer = words[-1]
            
            # Yield any remaining content
            if word_buffer.strip():
                yield word_buffer
                
            logger.info(f"Enhanced LLM Response for {session_id} in {streaming_mode.value} mode: '{full_response_for_history}'")
            
        except Exception as e:
            logger.error(f"Error during enhanced LLM streaming for session {session_id}: {e}", exc_info=True)
            # Enhanced error handling with circuit breaker awareness
            if "CircuitBreakerError" in str(type(e)):
                yield "Our AI is experiencing high demand. Please try again in a moment."
            else:
                yield "I'm having a temporary technical issue. Please give me a moment."
            full_response_for_history = error_message

        # Safely append to conversation history
        try:
            session.conversation_history.append(
                ChatMessage(
                    role="assistant", content=full_response_for_history
                ).model_dump()
            )
            self.save_session(session.session_id, session)
        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {e}", exc_info=True)

    async def process_conversation(
        self, user_input: str, session_id: str
    ) -> AsyncGenerator[str, None]:
        # Validate and sanitize input first
        try:
            validated_input = UserInputValidator(content=user_input, session_id=session_id)
            user_input = validated_input.content  # Use sanitized input
            session_id = validated_input.session_id  # Use validated session ID
            
            # Decode HTML entities
            user_input = html.unescape(user_input)
        except ValueError as e:
            logger.warning(f"Input validation failed: {e}")
            yield "I'm sorry, but I couldn't process that input. Please try rephrasing your message."
            return
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            yield "I'm experiencing a technical issue. Please try again."
            return

        # Enhance user input with cached accent handler
        processed_input = user_input
        if self.accent_handler:
            try:
                # Check cache first for performance
                cache_key = f"accent_{hash(user_input)}"
                if cache_key in self._accent_cache:
                    processed_input = self._accent_cache[cache_key]
                    logger.debug(f"Using cached accent processing for: '{user_input}'")
                else:
                    # Only process if not in cache
                    processed_input = self.accent_handler.normalize_speech(user_input)
                    self._accent_cache[cache_key] = processed_input
                    if processed_input != user_input:
                        logger.info(f"Accent processing: '{user_input}' -> '{processed_input}'")
            except Exception as e:
                logger.warning(f"Accent processing failed: {e}")
                processed_input = user_input

        logger.info(
            f"Processing turn for session {session_id} with input: '{processed_input}'"
        )
        
        # Enhanced error handling for session retrieval
        try:
            current_session = self.get_session(session_id)
            if not current_session:
                logger.error(f"Session {session_id} not found")
                yield "I seem to have lost our connection, please call back."
                return
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}", exc_info=True)
            yield "I'm experiencing a technical issue. Please try calling back."
            return
            
        # Analyze conversation intelligence with caching and optimization
        conversation_context = None
        if self.conversation_intelligence and processed_input != "<BEGIN_CONVERSATION>":
            try:
                # Create cache key based on input and recent conversation
                recent_history = str(current_session.conversation_history[-3:]) if len(current_session.conversation_history) > 3 else str(current_session.conversation_history)
                intelligence_cache_key = f"intel_{hash(processed_input + recent_history + str(current_session.conversation_state))}"
                
                if intelligence_cache_key in self._intelligence_cache:
                    conversation_context = self._intelligence_cache[intelligence_cache_key]
                    logger.debug(f"Using cached conversation intelligence")
                else:
                    # Run conversation intelligence analysis
                    # Build minimal context and generate contextual response to infer emotion/intents
                    from enhanced_conversation_intelligence import ConversationContext
                    conv_ctx = ConversationContext(conversation_stage=str(current_session.conversation_state.value))
                    _contextual = self.conversation_intelligence.create_contextual_response(
                        user_input=processed_input,
                        context=conv_ctx,
                        base_response=""
                    )
                    conversation_context = conv_ctx
                    self._intelligence_cache[intelligence_cache_key] = conversation_context
                    
                if conversation_context:
                    emotional_state = conversation_context.emotional_context.current_state.value if conversation_context.emotional_context else "neutral"
                    logger.info(f"Detected emotional state: {emotional_state}")
                    logger.info(f"Detected intents: {[i.type.value for i in conversation_context.detected_intents]}")
            except Exception as e:
                logger.warning(f"Conversation intelligence failed: {e}")

        # Safely add user input to conversation history
        try:
            if processed_input != "<BEGIN_CONVERSATION>":  # Use processed_input
                current_session.conversation_history.append(
                    ChatMessage(role="user", content=processed_input).model_dump()  # Store processed input
                )
                
                # Periodic cache cleanup to prevent memory leaks
                if len(current_session.conversation_history) % 10 == 0:  # Every 10 messages
                    self._cleanup_caches()
                    
        except Exception as e:
            logger.error(f"Error adding user input to session {session_id}: {e}", exc_info=True)
        
        # Enhanced error handling for LLM turn preparation
        try:
            dynamic_prompt, next_state = await self._prepare_llm_turn(
                processed_input, current_session  # Use processed input
            )
            current_session.conversation_state = next_state
        except Exception as e:
            logger.error(f"Error preparing LLM turn for session {session_id}: {e}", exc_info=True)
            yield "I'm having trouble processing your request. Let me try to help you with something else."
            return
            
        # Stream the response with optimized enhanced streaming and error handling
        try:
            # Determine streaming mode based on conversation context (do this once)
            streaming_mode = StreamingMode.INFORMATION  # Default
            if conversation_context:
                current_emotion = conversation_context.emotional_context.current_state if conversation_context.emotional_context else None
                if current_emotion in [EmotionalState.FRUSTRATED, EmotionalState.ANGRY]:
                    streaming_mode = StreamingMode.EMPATHY
                elif conversation_context.emotional_context and conversation_context.emotional_context.current_state in [EmotionalState.EXCITED, EmotionalState.SATISFIED]:
                    streaming_mode = StreamingMode.EXCITEMENT
                elif current_session.conversation_state in [ConversationState.CUSTOMER_VERIFICATION, ConversationState.PRIOR_SERVICE_CONFIRMATION]:
                    streaming_mode = StreamingMode.GREETING

            # Use enhanced streaming if available - stream directly without double processing
            if self.streaming_manager:
                # Stream with enhanced pacing directly from LLM
                async for chunk in self._call_llm_and_stream_enhanced(
                    dynamic_prompt, current_session, streaming_mode, session_id
                ):
                    yield chunk
            else:
                # Fallback to regular streaming
                async for chunk in self._call_llm_and_stream(dynamic_prompt, current_session):
                    yield chunk
        except Exception as e:
            logger.error(f"Error during response streaming for session {session_id}: {e}", exc_info=True)
            yield "I'm experiencing a technical issue. Please try again or call back."

    def _compute_call_duration_ms(self, session: JAIMESSession) -> int:
        try:
            started = session.temp_data.get("call_started_at")
            if not started:
                return 0
            start_dt = datetime.fromisoformat(started)
            delta = datetime.utcnow() - start_dt
            return int(delta.total_seconds() * 1000)
        except Exception:
            return 0

    def _get_recall_concise_line(self, session: JAIMESSession) -> str:
        """Return a single-line recall note if critical recalls were found for the VIN."""
        try:
            rs = session.temp_data.get('recall_summary')
            if not rs:
                return ""
            critical = int(rs.get('critical_recalls', 0))
            total = int(rs.get('total_recalls', 0))
            year = rs.get('vehicle_year')
            make = rs.get('vehicle_make')
            model = rs.get('vehicle_model')
            if critical > 0:
                return (
                    f"Also, I checked your {year} {make} {model} and found {critical} critical safety recall"
                    f"{'s' if critical != 1 else ''}. We can address that during the same visit. "
                )
            return ""
        except Exception:
            return ""
