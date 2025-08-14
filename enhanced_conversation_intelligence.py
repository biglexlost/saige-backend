# ./usr/bin/env python3
"""
Enhanced Conversation Intelligence and Personality System for JAIMES
Provides multi-intent detection, dynamic personality, and human-like empathy
"""

import re
import json
import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)


class EmotionalState(Enum):
    """Customer emotional states that JAIMES can detect and respond to"""

    FRUSTRATED = "frustrated"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    CONFUSED = "confused"
    SATISFIED = "satisfied"
    EXCITED = "excited"
    GRATEFUL = "grateful"
    IMPATIENT = "impatient"
    WORRIED = "worried"
    RELIEVED = "relieved"
    NEUTRAL = "neutral"


class IntentType(Enum):
    """Types of customer intents JAIMES can detect"""

    GREETING = "greeting"
    PROVIDE_NAME = "provide_name"
    VEHICLE_INFO = "vehicle_info"
    DESCRIBE_PROBLEM = "describe_problem"
    REQUEST_APPOINTMENT = "request_appointment"
    ASK_PRICE = "ask_price"
    ASK_TIME = "ask_time"
    EXPRESS_URGENCY = "express_urgency"
    REQUEST_CLARIFICATION = "request_clarification"
    SHOW_APPRECIATION = "show_appreciation"
    EXPRESS_CONCERN = "express_concern"


class PersonalityTrait(Enum):
    """JAIMES personality traits that can be emphasized"""

    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    EMPATHETIC = "empathetic"
    KNOWLEDGEABLE = "knowledgeable"
    PATIENT = "patient"
    ENTHUSIASTIC = "enthusiastic"
    REASSURING = "reassuring"
    SOUTHERN_CHARM = "southern_charm"


@dataclass
class Intent:
    """Detected customer intent with confidence and context"""

    type: IntentType
    confidence: float
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    context_clues: List[str] = field(default_factory=list)


@dataclass
class EmotionalContext:
    """Customer's emotional context and history"""

    current_state: EmotionalState
    confidence: float
    triggers: List[str] = field(default_factory=list)
    history: List[Tuple[EmotionalState, datetime]] = field(default_factory=list)


@dataclass
class ConversationContext:
    """Complete conversation context for intelligent responses"""

    customer_name: str = ""
    emotional_context: Optional[EmotionalContext] = None
    detected_intents: List[Intent] = field(default_factory=list)
    conversation_stage: str = "greeting"
    interaction_count: int = 0


class EnhancedConversationIntelligence:
    """Advanced conversation intelligence with multi-intent detection and personality"""

    def __init__(self):
        self.setup_intent_patterns()
        self.setup_emotional_indicators()
        self.setup_personality_responses()

    def setup_intent_patterns(self):
        """Setup patterns for intent detection"""
        self.intent_patterns = {
            IntentType.GREETING: [
                r"\b(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)\b"
            ],
            IntentType.PROVIDE_NAME: [
                r"\b(my\s+name\s+is|i\'m|this\s+is|call\s+me)\s+([a-zA-Z\s]+)",
                r"^([a-zA-Z]+)$",
            ],
            IntentType.VEHICLE_INFO: [
                r"\b(\d{4})\s+([a-zA-Z]+)\s+([a-zA-Z]+)",
                r"\b(drive|driving)\s+a\s+([a-zA-Z0-9\s]+)",
            ],
            IntentType.DESCRIBE_PROBLEM: [
                r"\b(problem|issue|trouble|wrong|broken|noise|leaking|won\'t\s+start)\b"
            ],
            IntentType.REQUEST_APPOINTMENT: [
                r"\b(schedule|book|make|set\s+up)\s+(an?\s+)?appointment\b"
            ],
            IntentType.ASK_PRICE: [r"\b(how\s+much|cost|price|expensive|charge)\b"],
            IntentType.ASK_TIME: [r"\b(how\s+long|take\s+long|time|duration)\b"],
            IntentType.EXPRESS_URGENCY: [
                r"\b(urgent|emergency|asap|right\s+away|immediately)\b"
            ],
            IntentType.REQUEST_CLARIFICATION: [
                r"\b(what\s+do\s+you\s+mean|don\'t\s+understand|confused)\b"
            ],
            IntentType.SHOW_APPRECIATION: [
                r"\b(thank\s+you|thanks|appreciate|grateful|bless\s+your\s+heart)\b"
            ],
            IntentType.EXPRESS_CONCERN: [r"\b(worried|concerned|scared|nervous)\b"],
        }

    def setup_emotional_indicators(self):
        """Setup emotional state detection patterns"""
        self.emotional_indicators = {
            EmotionalState.FRUSTRATED: [
                "frustrated",
                "annoyed",
                "irritated",
                "fed up",
                "sick of",
                "ridiculous",
            ],
            EmotionalState.ANXIOUS: [
                "worried",
                "nervous",
                "anxious",
                "concerned",
                "stressed",
                "scared",
            ],
            EmotionalState.ANGRY: [
                "angry",
                "mad",
                "pissed",
                "furious",
                "livid",
                "outrageous",
            ],
            EmotionalState.CONFUSED: [
                "confused",
                "don't understand",
                "what do you mean",
                "huh",
                "what",
            ],
            EmotionalState.SATISFIED: [
                "satisfied",
                "happy",
                "pleased",
                "sounds good",
                "perfect",
                "excellent",
            ],
            EmotionalState.EXCITED: [
                "excited",
                "great",
                "awesome",
                "fantastic",
                "wonderful",
                "amazing",
            ],
            EmotionalState.GRATEFUL: [
                "thank you",
                "thanks",
                "appreciate",
                "grateful",
                "bless your heart",
            ],
            EmotionalState.IMPATIENT: [
                "hurry",
                "quickly",
                "asap",
                "right away",
                "immediately",
                "urgent",
            ],
            EmotionalState.WORRIED: [
                "worried",
                "concerned",
                "nervous",
                "scared",
                "hope it's not serious",
            ],
            EmotionalState.RELIEVED: [
                "relieved",
                "glad",
                "thankful",
                "phew",
                "that's good",
            ],
        }

    def setup_personality_responses(self):
        """Setup personality-driven response pools"""
        self.personality_responses = {
            PersonalityTrait.FRIENDLY: {
                "greeting": [
                    "Hey there. Great to meet you.",
                    "Hi. How are you doing today?",
                ],
                "empathy": [
                    "I totally understand how that feels.",
                    "That sounds really frustrating.",
                ],
                "reassurance": [
                    "Don't worry, we'll get this figured out.",
                    "You're in good hands with our team.",
                ],
            },
            PersonalityTrait.SOUTHERN_CHARM: {
                "greeting": [
                    "Well hey there. How y'all doing today?",
                    "Howdy. What can we do for you today?",
                ],
                "empathy": [
                    "Oh honey, I can just imagine how frustrating that is.",
                    "Bless your heart, that sounds like a real pain.",
                ],
                "reassurance": [
                    "Don't you worry none, we'll get you fixed right up.",
                    "Honey, our boys know exactly what they're doing.",
                ],
            },
            PersonalityTrait.PROFESSIONAL: {
                "greeting": [
                    f"Good morning. I'm {config.assistant_name}, your {config.assistant_title}.",
                    "Hello. Thank you for choosing My-Lex Complete Auto Care.",
                ],
                "empathy": [
                    "I understand your concern about this issue.",
                    "That's certainly a valid worry to have.",
                ],
                "reassurance": [
                    "Our certified technicians will thoroughly diagnose the issue.",
                    "We have extensive experience with this type of problem.",
                ],
            },
        }

    def detect_intents(self, text: str, context: ConversationContext) -> List[Intent]:
        """Detect multiple intents in customer input with confidence scoring"""
        text_lower = text.lower()
        detected_intents = []
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                    confidence = self._calculate_intent_confidence(
                        intent_type, match, text_lower, context
                    )
                    if confidence > 0.3:
                        extracted_data = self._extract_intent_data(
                            intent_type, match, text
                        )
                        intent = Intent(
                            type=intent_type,
                            confidence=confidence,
                            extracted_data=extracted_data,
                            context_clues=[match.group(0)],
                        )
                        detected_intents.append(intent)
        detected_intents.sort(key=lambda x: x.confidence, reverse=True)
        return self._deduplicate_intents(detected_intents)

    def detect_emotional_state(
        self, text: str, context: ConversationContext
    ) -> EmotionalContext:
        """Detect customer's emotional state with confidence scoring"""
        text_lower = text.lower()
        emotion_scores = {}
        triggers = []
        for emotion, indicators in self.emotional_indicators.items():
            score = sum(1 for indicator in indicators if indicator in text_lower)
            if score > 0:
                triggers.extend(
                    [indicator for indicator in indicators if indicator in text_lower]
                )
                normalized_score = min(score / len(text.split()) * 10, 1.0)
                emotion_scores[emotion] = normalized_score
        if emotion_scores:
            dominant_emotion, confidence = max(
                emotion_scores.items(), key=lambda x: x[1]
            )
            history = (
                context.emotional_context.history if context.emotional_context else []
            )
            history.append((dominant_emotion, datetime.now()))
            return EmotionalContext(
                current_state=dominant_emotion,
                confidence=confidence,
                triggers=list(set(triggers)),  # Ensure triggers are unique
                history=history[-10:],
            )
        return EmotionalContext(
            current_state=EmotionalState.NEUTRAL,
            confidence=0.5,
            triggers=[],
            history=[],
        )

    def generate_personality_response(
        self, context: ConversationContext, response_type: str = "general"
    ) -> str:
        """Generate a personality-driven response based on context"""
        active_traits = self._get_active_traits(context)
        response_pool = []
        for trait in active_traits:
            if (
                trait in self.personality_responses
                and response_type in self.personality_responses[trait]
            ):
                response_pool.extend(self.personality_responses[trait][response_type])
        return (
            random.choice(response_pool)
            if response_pool
            else "I'm here to help you with whatever you need."
        )

    def create_contextual_response(
        self, user_input: str, context: ConversationContext, base_response: str = ""
    ) -> Dict[str, Any]:
        """Create a contextually aware response with personality and empathy"""
        intents = self.detect_intents(user_input, context)
        emotional_context = self.detect_emotional_state(user_input, context)
        context.detected_intents = intents
        context.emotional_context = emotional_context
        context.interaction_count += 1

        response_parts = []
        if emotional_context.current_state not in [
            EmotionalState.NEUTRAL,
            EmotionalState.SATISFIED,
        ]:
            empathy_response = self._generate_empathy_response(emotional_context)
            if empathy_response:
                response_parts.append(empathy_response)

        if base_response:
            response_parts.append(base_response)
        elif intents:
            response_parts.append(self._generate_intent_response(intents[0], context))
        else:
            response_parts.append("I understand. How can I assist you further?")

        final_response = " ".join(response_parts)
        ssml_response = self._enhance_with_ssml(final_response, emotional_context)

        return {
            "response": final_response,
            "ssml_response": ssml_response,
            "detected_intents": [
                {"type": i.type.value, "confidence": i.confidence} for i in intents
            ],
            "emotional_state": emotional_context.current_state.value,
            "emotional_confidence": emotional_context.confidence,
            "personality_traits_used": [
                trait.value for trait in self._get_active_traits(context)
            ],
        }

    def _calculate_intent_confidence(
        self,
        intent_type: IntentType,
        match: re.Match,
        text: str,
        context: ConversationContext,
    ) -> float:
        """Calculate confidence score for detected intent"""
        base_confidence = 0.7
        if (
            intent_type == IntentType.PROVIDE_NAME
            and context.conversation_stage == "awaiting_name"
        ):
            base_confidence += 0.2
        if len(match.group(0)) / len(text) > 0.5:
            base_confidence += 0.1
        return min(base_confidence, 1.0)

    def _extract_intent_data(
        self, intent_type: IntentType, match: re.Match, text: str
    ) -> Dict[str, Any]:
        """Extract relevant data from intent matches"""
        if intent_type == IntentType.PROVIDE_NAME and len(match.groups()) > 1:
            return {"name": match.group(2).strip().title()}
        if intent_type == IntentType.VEHICLE_INFO and len(match.groups()) >= 3:
            return {
                "year": match.group(1),
                "make": match.group(2).title(),
                "model": match.group(3).title(),
            }
        return {}

    def _deduplicate_intents(self, intents: List[Intent]) -> List[Intent]:
        """Remove duplicate intents, keeping highest confidence"""
        seen_types = set()
        deduplicated = []
        for intent in intents:
            if intent.type not in seen_types:
                deduplicated.append(intent)
                seen_types.add(intent.type)
        return deduplicated

    def _generate_empathy_response(
        self, emotional_context: EmotionalContext
    ) -> Optional[str]:
        """Generate empathetic response based on emotional state"""
        empathy_responses = {
            EmotionalState.FRUSTRATED: [
                "I can hear the frustration in your voice, and I completely understand."
            ],
            EmotionalState.ANXIOUS: [
                "I understand this is concerning, and I want to put your mind at ease."
            ],
            EmotionalState.ANGRY: [
                "I can tell you're upset, and I want to help resolve this for you."
            ],
            EmotionalState.WORRIED: [
                "I can tell you're concerned, and that's completely understandable."
            ],
        }
        return (
            random.choice(empathy_responses.get(emotional_context.current_state, []))
            or None
        )

    def _generate_intent_response(
        self, intent: Intent, context: ConversationContext
    ) -> str:
        """Generate response based on detected intent"""
        intent_responses = {
            IntentType.GREETING: self.generate_personality_response(
                context, "greeting"
            ),
            IntentType.SHOW_APPRECIATION: "You're very welcome. I'm happy to help.",
            IntentType.REQUEST_CLARIFICATION: "Of course. Let me explain that better for you.",
            IntentType.EXPRESS_URGENCY: "I understand this is urgent. Let me see what we can do to help you right away.",
        }
        return intent_responses.get(
            intent.type, "I understand. Let me help you with that."
        )

    def _enhance_with_ssml(self, text: str, emotional_context: EmotionalContext) -> str:
        """Enhance response with SSML based on emotional context"""
        emotion = emotional_context.current_state
        rate, pitch = "1.0", "0st"
        if emotion in [EmotionalState.ANXIOUS, EmotionalState.WORRIED]:
            rate, pitch = "0.9", "-2st"
        elif emotion == EmotionalState.EXCITED:
            rate, pitch = "1.1", "+1st"
        elif emotion in [EmotionalState.FRUSTRATED, EmotionalState.ANGRY]:
            rate, pitch = "0.95", "-1st"
        text = f"<prosody rate='{rate}' pitch='{pitch}'>{text}</prosody>"
        text = text.replace(". ", ". <break time='500ms'/> ")
        return f"<speak>{text}</speak>"

    def _get_active_traits(
        self, context: ConversationContext
    ) -> List[PersonalityTrait]:
        """Get personality traits that should be active for this context"""
        # Map emotions to the primary trait they should trigger
        emotion_trait_map = {
            EmotionalState.FRUSTRATED: PersonalityTrait.EMPATHETIC,
            EmotionalState.ANGRY: PersonalityTrait.EMPATHETIC,
            EmotionalState.ANXIOUS: PersonalityTrait.REASSURING,
            EmotionalState.WORRIED: PersonalityTrait.REASSURING,
            EmotionalState.EXCITED: PersonalityTrait.ENTHUSIASTIC,
            EmotionalState.SATISFIED: PersonalityTrait.ENTHUSIASTIC,
        }

        # Start with base traits
        active_traits = {PersonalityTrait.FRIENDLY, PersonalityTrait.SOUTHERN_CHARM}

        if context.emotional_context:
            triggered_trait = emotion_trait_map.get(
                context.emotional_context.current_state
            )
            if triggered_trait:
                active_traits.add(triggered_trait)

        return list(active_traits)


# Example usage and testing
if __name__ == "__main__":
    intelligence = EnhancedConversationIntelligence()
    context = ConversationContext(conversation_stage="greeting")
    test_inputs = [
        "Hi there, I'm really frustrated with my car",
        "My name is Billy Bob and I'm worried about my truck",
        "I've got a 2018 Honda Civic that's making weird noises",
        "Thank you so much for your help, bless your heart",
        "How much is this gonna cost me? I'm on a tight budget",
        "I need this fixed today, it's an emergency.",
    ]
    print("Testing Enhanced Conversation Intelligence:")
    print("=" * 60)
    for i, user_input in enumerate(test_inputs):
        print(f"\nTest {i + 1}: '{user_input}'")
        print("-" * 40)
        result = intelligence.create_contextual_response(user_input, context)
        print(f"Response: {result['response']}")
        print(
            f"Emotional State: {result['emotional_state']} (confidence: {result['emotional_confidence']:.2f})"
        )
        intents_str = [
            f"{i['type']} ({i['confidence']:.2f})" for i in result["detected_intents"]
        ]
        print(f"Detected Intents: {intents_str}")
        print(f"Personality Traits: {result['personality_traits_used']}")
        print(f"SSML: {result['ssml_response']}")
        context.interaction_count += 1
