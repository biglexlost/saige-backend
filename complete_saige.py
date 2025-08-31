# complete_saige.py

import asyncio
import re
import html
from typing import AsyncGenerator, Dict, Optional

from pydantic import BaseModel, Field, validator
from enhanced_accent_handler import SouthernAccentHandler
from enhanced_conversation_intelligence import EnhancedConversationIntelligence as ConversationIntelligence, EmotionalState
from enhanced_streaming import EnhancedStreamer as StreamingResponseManager, StreamingMode
from medspa_service_catalog import match_service, MEDSPA_SERVICES, get_crm_tags_for_service, get_automation_phase_for_tags
from booking_adapter import BookingAdapter
from models import ConversationState, JAIMESSession, CustomerProfile, ChatMessage
from mock_db import MockCustomerEngine
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import config
from groq import AsyncGroq
import redis
from analytics import init_analytics_db
import structlog

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


class CompleteSAIGESystem:
    def __init__(self, groq_api_key: str, redis_url: str, **kwargs):
        logger.info(f"Initializing SAIGE in [{config.environment}] mode...")
        self.customer_engine = MockCustomerEngine()
        self.groq_client = AsyncGroq(api_key=groq_api_key)
        self.groq_model = config.groq_model
        self.redis_url = redis_url
        self.redis_client = None
        logger.info("Redis connection will be established on first use.")
        self.in_memory_sessions: Dict[str, JAIMESSession] = {}

        # Initialize analytics DB and leads table (HIPAA-safe metadata only)
        init_analytics_db()
        try:
            ensure_leads_table()
        except Exception:
            logger.warning("Leads table initialization skipped")
        # Initialize enhanced modules with performance optimizations
        try:
            self.accent_handler = SouthernAccentHandler()
            self.conversation_intelligence = ConversationIntelligence()
            self.streaming_manager = StreamingResponseManager()
            self.booking = BookingAdapter()
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

    def _ensure_redis_connection(self):
        """Ensures Redis connection is established, creating it if needed."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Successfully connected to Redis server.")
            except Exception as e:
                logger.error(
                    f"Failed to connect to Redis: {e}. Relying on in-memory fallback."
                )
                self.redis_client = None

    @redis_circuit_breaker()
    @redis_retry()
    def get_session(self, session_id: str) -> Optional[JAIMESSession]:
        self._ensure_redis_connection()
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
        self._ensure_redis_connection()
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
        session.temp_data["call_started_at"] = datetime.now(timezone.utc).isoformat()
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
        
        base_prompt = f"""
You are {config.assistant_name}, the {config.assistant_title} for {config.shop_name}. You're a warm, concierge-style spa expert from {config.shop_location}. Keep responses brief and welcoming.

Tone and style:
- Calm and approachable; avoid corporate language
- Use plain words and contractions (I'm, we'll, that's) but no slang
- Short responses: usually 1–2 sentences before asking the next question
- No exclamation points
- Be concise: prefer 12–18 words per sentence; avoid filler and restating the user's answers

Conversation rules:
1. Ask one question at a time.
2. Don’t give medical advice; recommend consultation for clinical questions.
3. Avoid PHI. Never ask for DOB/medical history unless explicitly needed for booking.
4. No promises about availability or pricing unless provided by the mission.
5. Never say something is “scheduled” until the date/time are confirmed.
"""
        # --- CHAPTER 1: CUSTOMER IDENTIFICATION ---

        if state == ConversationState.CUSTOMER_VERIFICATION:
            customer_name = session.customer_profile.name if session.customer_profile else "our customer"
            user_affirmed = any(word in user_input.lower() for word in ['yes', 'yeah', 'yep', 'correct'])
            if user_input == "<BEGIN_CONVERSATION>":
                mission = f"Say this exactly: 'Hi, this is {config.assistant_name}, your {config.assistant_title} with {config.shop_name}. I see this number is for {customer_name}. Am I speaking with the right person?'"
            elif user_affirmed:
                next_state = ConversationState.VEHICLE_CONFIRMATION
                if session.customer_profile and session.customer_profile.service_history:
                    last_service = sorted(session.customer_profile.service_history, key=lambda s: s.service_date, reverse=True)[0]
                    mission = (f"Say this, or something very close to: 'Great, thanks for confirming. I see the last time you were in, you were in for {last_service.service_description} "
                            f"on your {last_service.vehicle_description}. How has that been for you?'")
                else:
                    mission = "Great, thanks for confirming. What can I help you with today?"
            else:
                next_state = ConversationState.PRIOR_SERVICE_CONFIRMATION
                mission = "The user said they are NOT the person associated with this phone number. Apologize for the mistake, and then ask if they have ever been here before."

        elif state == ConversationState.PRIOR_SERVICE_CONFIRMATION:
            if user_input == "<BEGIN_CONVERSATION>":
                mission = f"Say this exactly: 'Hi, this is {config.assistant_name}, your {config.assistant_title} with {config.shop_name}. To get things started, have you visited us here before?'"
            elif any(word in user_input.lower() for word in ['yes', 'yeah', 'yep']):
                next_state = ConversationState.PHONE_NUMBER_CLARIFICATION
                mission = "The user is a returning customer. Say this exactly: 'Okay, thanks for clarifying. What phone number might the account be under?'"
            else:
                next_state = ConversationState.COLLECT_NEW_CUSTOMER_NAME
                mission = "The user is a new customer. Welcome, may I have your first and last name to get a file started."

        elif state == ConversationState.PHONE_NUMBER_CLARIFICATION:
            if any(char.isdigit() for char in user_input):
                try:
                    normalized_alt_phone = normalize_phone_number(user_input.strip())
                    customer_profile = await self.customer_engine.find_customer_by_phone(normalized_alt_phone)
                    if customer_profile:
                        session.customer_profile = customer_profile
                        next_state = ConversationState.SERVICE_SELECTION
                        mission = f"Great, I found the account for {customer_profile.name}. What can I help you with today?"
                    else:
                        next_state = ConversationState.PHONE_NUMBER_CLARIFICATION
                        mission = "I couldn't find that number. Could you read it back for me?"
                except Exception:
                    next_state = ConversationState.PHONE_NUMBER_CLARIFICATION
                    mission = "Could you share the phone number the account might be under?"

        # --- CHAPTER 2: MED-SPA ONBOARDING ---

            acknowledgement = "Great, thanks for that information. "
            if any(word in user_input.lower() for word in ["no", "don't have it", "not right now"]):
                acknowledgement = "No problem at all. "

            probable_cause = session.temp_data.get('probable_cause', 'Brake Pad Replacement')
            zip_code = config.shop_zip_code

       # --- CHAPTER 4: SCHEDULING & CONFIRMATION ---
        elif state == ConversationState.SERVICE_SELECTION:
            # Try to match service from user input
            svc = match_service(user_input)
            if svc:
                session.temp_data["selected_service"] = svc
                # Apply CRM tags for this service
                crm_tags = get_crm_tags_for_service(svc)
                session.temp_data["crm_tags"] = crm_tags
                
                # Determine automation phase
                automation_phase = get_automation_phase_for_tags(crm_tags)
                session.temp_data["automation_phase"] = automation_phase
                
                next_state = ConversationState.INTAKE_QA
                q = MEDSPA_SERVICES[svc]["intake"][0] if MEDSPA_SERVICES[svc]["intake"] else "Any preferences I should note?"
                mission = f"Got it, {svc}. {q}"
            else:
                next_state = ConversationState.SERVICE_SELECTION
                mission = "What service are you interested in today? We offer consultations, facials, Botox, fillers, laser treatments, and massage."

        elif state == ConversationState.INTAKE_QA:
            svc = session.temp_data.get("selected_service")
            intake = MEDSPA_SERVICES.get(svc, {}).get("intake", []) if svc else []
            asked = session.temp_data.get("intake_index", 0)
            
            if asked < len(intake):
                # Record answer and ask next question
                session.temp_data.setdefault("intake_answers", []).append(user_input)
                next_index = asked + 1
                session.temp_data["intake_index"] = next_index
                
                if next_index < len(intake):
                    mission = intake[next_index]
                    next_state = ConversationState.INTAKE_QA
                else:
                    # All intake questions answered, move to scheduling
                    next_state = ConversationState.PROPOSE_SCHEDULING
                    service_info = MEDSPA_SERVICES.get(svc, {})
                    duration = service_info.get("duration_minutes", 60)
                    price = service_info.get("price_range", "$100-$300")
                    mission = f"Perfect! Your {svc} will take about {duration} minutes and costs {price}. Would you like to find a day and time that works for you?"
            else:
                # Start asking first question
                if intake:
                    session.temp_data["intake_index"] = 0
                    mission = intake[0]
                    next_state = ConversationState.INTAKE_QA
                else:
                    next_state = ConversationState.PROPOSE_SCHEDULING
                    mission = "Would you like to find a day and time that works for you?"

        elif state == ConversationState.PROPOSE_SCHEDULING:
            if user_input.lower() in ["yes", "sure", "okay", "ok", "yeah", "yep"]:
                # Find available slot
                service = session.temp_data.get("selected_service", "consultation")
                slot = await self.booking.find_slot(service)
                session.temp_data["proposed_slot"] = slot
                
                next_state = ConversationState.CONFIRM_APPOINTMENT
                mission = f"Great! I found {slot} available. Does that work for you?"
            else:
                next_state = ConversationState.PROPOSE_SCHEDULING
                mission = "No problem! When would you like to schedule your appointment?"

        elif state == ConversationState.CONFIRM_APPOINTMENT:
            if user_input.lower() in ["yes", "sure", "okay", "ok", "yeah", "yep", "perfect", "great"]:
                # Confirm appointment and trigger CRM automation
                service = session.temp_data.get("selected_service", "consultation")
                slot = session.temp_data.get("proposed_slot", "TBD")
                
                # Apply booking confirmation tags
                session.temp_data["crm_tags"].extend(["booking-confirmed", "slot-claimed"])
                
                # Log successful booking
                log_event(
                    "appointment_confirmed",
                    session.session_id,
                    {
                        "service": service,
                        "slot": slot,
                        "crm_tags": session.temp_data.get("crm_tags", []),
                        "automation_phase": session.temp_data.get("automation_phase"),
                        "intake_answers": session.temp_data.get("intake_answers", [])
                    },
                )
                
                next_state = ConversationState.CONVERSATION_COMPLETE
                mission = f"Perfect! Your {service} is confirmed for {slot}. You'll receive a confirmation text shortly. Is there anything else I can help you with today?"
            else:
                # Offer alternative slot or reschedule
                next_state = ConversationState.PROPOSE_SCHEDULING
                mission = "No problem! Let me find another time that works better for you. What days work best for you?"

        elif state == ConversationState.CONVERSATION_COMPLETE:
            # Conversation is already finished, provide brief acknowledgment only
            if 'thank you' in user_input.lower():
                mission = "You're welcome. Take care."
            elif any(greeting in user_input.lower() for greeting in ['hi', 'hello', 'hey']):
                mission = "Hi again. If you need anything else, feel free to call back."
            else:
                mission = f"Thanks for calling {config.shop_name}."
            next_state = ConversationState.CONVERSATION_COMPLETE
        
            # Safety fallback - ensure we always have a mission
            if not mission:
                logger.warning(f"No mission defined for state {state}, using fallback")
                mission = "I'm here to help with spa services and bookings. What can I assist you with today?"
            
            logger.info(f"PREPARE_LLM_TURN: State transition {state} -> {next_state}")
            logger.info(f"PREPARE_LLM_TURN: Mission: {mission[:100]}...")
        
        dynamic_prompt = f"{base_prompt}\n\nYour specific mission for this turn is: {mission}"
        return dynamic_prompt, next_state

    def _extract_clean_time(self, text: str) -> str:
        """Very simple time extraction heuristic for demo/tests."""
        t = text.strip()
        # Normalize spacing
        t = re.sub(r"\s+", " ", t)
        return t

    def _determine_probable_cause(self, session: JAIMESSession) -> str:
        """Determine the most likely cause based on comprehensive diagnostic information."""
        conversation_text = ' '.join([msg.get('content', '') for msg in session.conversation_history])
        conversation_text = conversation_text.lower()
        


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

    # Removed automotive confirmation logic

    # Removed automotive cheat sheet logic

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
            full_response_for_history = ""

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
