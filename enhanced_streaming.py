#!/usr/bin/env python3
"""
Enhanced Real-Time Streaming Response System for JAIMES
Provides word-by-word streaming with natural pacing and emotional intelligence
"""

import json
import time
import asyncio
import uuid
import re
import logging
from typing import AsyncGenerator, Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StreamingMode(Enum):
    """Different streaming modes for various conversation contexts"""

    GREETING = "greeting"  # Warm, welcoming pace
    INFORMATION = "information"  # Clear, informative pace
    EMPATHY = "empathy"  # Slower, more caring pace
    EXCITEMENT = "excitement"  # Faster, energetic pace
    TECHNICAL = "technical"  # Measured, precise pace
    URGENT = "urgent"  # Quick but clear pace


@dataclass
class StreamingConfig:
    """Configuration for streaming behavior"""

    base_delay: float = 0.08  # Base delay between words (seconds)
    punctuation_delay: float = 0.3  # Extra delay after punctuation
    emphasis_delay: float = 0.15  # Extra delay for emphasized words
    sentence_end_delay: float = 0.5  # Extra delay at sentence end
    paragraph_delay: float = 0.8  # Extra delay between paragraphs
    max_chunk_size: int = 10  # Maximum words per chunk
    adaptive_pacing: bool = True  # Adjust pacing based on content


class EnhancedStreamer:
    """Enhanced streaming response system with emotional intelligence"""

    def __init__(self):
        self.configs = {
            StreamingMode.GREETING: StreamingConfig(
                base_delay=0.12, punctuation_delay=0.4, sentence_end_delay=0.6
            ),
            StreamingMode.INFORMATION: StreamingConfig(
                base_delay=0.08, punctuation_delay=0.3, sentence_end_delay=0.5
            ),
            StreamingMode.EMPATHY: StreamingConfig(
                base_delay=0.15, punctuation_delay=0.5, sentence_end_delay=0.8
            ),
            StreamingMode.EXCITEMENT: StreamingConfig(
                base_delay=0.06, punctuation_delay=0.2, sentence_end_delay=0.3
            ),
            StreamingMode.TECHNICAL: StreamingConfig(
                base_delay=0.10, punctuation_delay=0.4, sentence_end_delay=0.6
            ),
            StreamingMode.URGENT: StreamingConfig(
                base_delay=0.05, punctuation_delay=0.2, sentence_end_delay=0.3
            ),
        }

        # Words that should have emphasis or special pacing
        self.emphasis_words = {
            "important",
            "urgent",
            "critical",
            "emergency",
            "immediately",
            "please",
            "thank",
            "sorry",
            "apologize",
            "appreciate",
            "excellent",
            "perfect",
            "wonderful",
            "fantastic",
            "amazing",
        }

        # Words that indicate emotional context
        self.emotion_indicators = {
            "frustrated": StreamingMode.EMPATHY,
            "angry": StreamingMode.EMPATHY,
            "upset": StreamingMode.EMPATHY,
            "worried": StreamingMode.EMPATHY,
            "concerned": StreamingMode.EMPATHY,
            "excited": StreamingMode.EXCITEMENT,
            "happy": StreamingMode.EXCITEMENT,
            "thrilled": StreamingMode.EXCITEMENT,
            "urgent": StreamingMode.URGENT,
            "emergency": StreamingMode.URGENT,
            "immediately": StreamingMode.URGENT,
            "technical": StreamingMode.TECHNICAL,
            "diagnosis": StreamingMode.TECHNICAL,
            "repair": StreamingMode.TECHNICAL,
        }

    def process_response(self, response_text: str) -> Dict[str, Any]:
        # Example: wrap plain text in basic SSML
        ssml_output = f"<speak>{response_text}</speak>"

        return {
            "streaming": {"ssml": ssml_output, "voice": "jaimes-mechanic-v1"},
            "metadata": {
                "emotion": "neutral",
                "generated_at": datetime.utcnow().isoformat(),
            },
        }

    def detect_streaming_mode(
        self, content: str, context: Dict = None
    ) -> StreamingMode:
        """Detect appropriate streaming mode based on content and context"""
        content_lower = content.lower()

        # Check for emotional indicators
        for indicator, mode in self.emotion_indicators.items():
            if indicator in content_lower:
                return mode

        # Check context clues
        if context:
            stage = context.get("stage", "")
            if stage in ["greeting", "awaiting_name"]:
                return StreamingMode.GREETING
            elif "diagnosis" in stage or "technical" in stage:
                return StreamingMode.TECHNICAL

        # Check content patterns
        if any(
            word in content_lower
            for word in ["hello", "hi", "welcome", "great to meet"]
        ):
            return StreamingMode.GREETING
        elif any(
            word in content_lower
            for word in ["sorry", "apologize", "understand", "frustrating"]
        ):
            return StreamingMode.EMPATHY
        elif any(
            word in content_lower
            for word in ["excellent", "perfect", "wonderful", "fantastic"]
        ):
            return StreamingMode.EXCITEMENT
        elif any(
            word in content_lower
            for word in ["urgent", "emergency", "immediately", "asap"]
        ):
            return StreamingMode.URGENT
        elif any(
            word in content_lower
            for word in ["diagnosis", "repair", "technical", "engine", "transmission"]
        ):
            return StreamingMode.TECHNICAL

        return StreamingMode.INFORMATION  # Default mode

    def prepare_content_for_streaming(self, content: str) -> List[Dict]:
        """Prepare content for streaming with metadata for each segment"""
        # Remove SSML tags for processing (we'll add them back later)
        clean_content = re.sub(r"<[^>]+>", "", content)

        segments = []
        sentences = re.split(r"([.!?]+)", clean_content)

        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""

                if sentence:
                    words = sentence.split()
                    for j, word in enumerate(words):
                        is_emphasis = word.lower() in self.emphasis_words
                        is_last_in_sentence = j == len(words) - 1

                        segments.append(
                            {
                                "word": word,
                                "punctuation": (
                                    punctuation if is_last_in_sentence else ""
                                ),
                                "is_emphasis": is_emphasis,
                                "is_sentence_end": is_last_in_sentence,
                                "is_paragraph_end": False,  # Could be enhanced to detect paragraphs
                            }
                        )

        return segments

    async def stream_response_enhanced(
        self,
        content: str,
        request_id: str = None,
        context: Dict = None,
        mode: Optional[StreamingMode] = None,
    ) -> AsyncGenerator[str, None]:
        """Enhanced streaming response with adaptive pacing and emotional intelligence"""

        if request_id:
            logger.info(f"[{request_id}] Starting enhanced stream response")

        # Generate unique chat ID
        chat_id = f"chatcmpl-jaimes-{uuid.uuid4().hex[:8]}"

        # Detect streaming mode if not provided
        if mode is None:
            mode = self.detect_streaming_mode(content, context)

        config = self.configs[mode]
        logger.info(f"[{request_id}] Using streaming mode: {mode.value}")

        # Initial chunk with role
        initial_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "jaimes-mechanic-specialist",
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
        yield f"data: {json.dumps(initial_chunk)}\n\n"

        # Prepare content segments
        segments = self.prepare_content_for_streaming(content)

        # Stream word by word with intelligent pacing
        for i, segment in enumerate(segments):
            word = segment["word"]
            punctuation = segment["punctuation"]
            is_emphasis = segment["is_emphasis"]
            is_sentence_end = segment["is_sentence_end"]

            # Calculate delay for this word
            delay = config.base_delay

            if is_emphasis and config.adaptive_pacing:
                delay += config.emphasis_delay

            if is_sentence_end:
                delay += config.sentence_end_delay
            elif punctuation:
                delay += config.punctuation_delay

            # Add space before word (except first word)
            word_with_space = f" {word}" if i > 0 else word
            full_content = word_with_space + punctuation

            # Create streaming chunk
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "jaimes-mechanic-specialist",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": full_content},
                        "finish_reason": None,
                    }
                ],
            }

            yield f"data: {json.dumps(chunk)}\n\n"

            # Apply delay
            if delay > 0:
                await asyncio.sleep(delay)

        # Final chunk
        final_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "jaimes-mechanic-specialist",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

        if request_id:
            logger.info(f"[{request_id}] Enhanced stream response completed")

    async def stream_with_ssml_support(
        self,
        content: str,
        request_id: str = None,
        context: Dict = None,
        preserve_ssml: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Stream response while preserving SSML tags for voice synthesis"""

        if preserve_ssml and "<speak>" in content:
            # For SSML content, we need to be more careful about streaming
            # to preserve the voice markup structure

            # Extract SSML structure
            ssml_pattern = r"<speak>(.*?)</speak>"
            ssml_match = re.search(ssml_pattern, content, re.DOTALL)

            if ssml_match:
                inner_content = ssml_match.group(1)

                # Remove prosody and other tags for word extraction
                clean_for_words = re.sub(r"<[^>]+>", "", inner_content)

                # Stream the clean content but preserve original SSML structure
                async for chunk in self.stream_response_enhanced(
                    clean_for_words, request_id, context
                ):
                    yield chunk
            else:
                # No valid SSML, stream normally
                async for chunk in self.stream_response_enhanced(
                    content, request_id, context
                ):
                    yield chunk
        else:
            # Regular streaming
            async for chunk in self.stream_response_enhanced(
                content, request_id, context
            ):
                yield chunk

    def create_typing_indicator(self, chat_id: str) -> str:
        """Create a typing indicator chunk"""
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "jaimes-mechanic-specialist",
            "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": None}],
        }
        return f"data: {json.dumps(chunk)}\n\n"

    async def stream_with_typing_indicator(
        self,
        content: str,
        request_id: str = None,
        context: Dict = None,
        typing_duration: float = 1.0,
    ) -> AsyncGenerator[str, None]:
        """Stream response with initial typing indicator"""

        chat_id = f"chatcmpl-jaimes-{uuid.uuid4().hex[:8]}"

        # Show typing indicator
        yield self.create_typing_indicator(chat_id)
        await asyncio.sleep(typing_duration)

        # Stream actual response
        async for chunk in self.stream_response_enhanced(content, request_id, context):
            yield chunk


# Integration helper for FastAPI
class StreamingResponseHelper:
    """Helper class for integrating enhanced streaming with FastAPI"""

    def __init__(self):
        self.streamer = EnhancedStreamer()

    async def create_streaming_response(
        self,
        content: str,
        request_id: str = None,
        context: Dict = None,
        mode: Optional[StreamingMode] = None,
        headers: Dict = None,
    ):
        """Create a FastAPI StreamingResponse with enhanced streaming"""
        from fastapi.responses import StreamingResponse

        default_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
        }

        if headers:
            default_headers.update(headers)

        if request_id:
            default_headers["X-Request-ID"] = request_id

        return StreamingResponse(
            self.streamer.stream_response_enhanced(content, request_id, context, mode),
            media_type="text/event-stream",
            headers=default_headers,
        )


# Example usage and testing
async def test_streaming():
    """Test the enhanced streaming system"""
    streamer = EnhancedStreamer()

    test_cases = [
        {
            "content": "Hey there! I'm James, your AI service advisor. What brings you in today?",
            "context": {"stage": "greeting"},
            "expected_mode": StreamingMode.GREETING,
        },
        {
            "content": "I understand this is frustrating. Let me help you figure out what's wrong with your vehicle.",
            "context": {"stage": "diagnosis"},
            "expected_mode": StreamingMode.EMPATHY,
        },
        {
            "content": "Based on your 2018 Honda Civic, that sounds like worn brake pads. This is typically $150-400 per axle.",
            "context": {"stage": "technical_diagnosis"},
            "expected_mode": StreamingMode.TECHNICAL,
        },
        {
            "content": "Perfect! I can get you scheduled right away. What time works best for you?",
            "context": {"stage": "scheduling"},
            "expected_mode": StreamingMode.EXCITEMENT,
        },
    ]

    print("Testing Enhanced Streaming System:")
    print("=" * 50)

    for i, test_case in enumerate(test_cases):
        print(f"\nTest Case {i + 1}:")
        print(f"Content: {test_case['content']}")
        print(f"Expected Mode: {test_case['expected_mode'].value}")

        detected_mode = streamer.detect_streaming_mode(
            test_case["content"], test_case["context"]
        )
        print(f"Detected Mode: {detected_mode.value}")
        print(
            f"Mode Match: {'✓' if detected_mode == test_case['expected_mode'] else '✗'}"
        )

        # Test content preparation
        segments = streamer.prepare_content_for_streaming(test_case["content"])
        print(f"Word Segments: {len(segments)}")
        print(f"First few words: {[s['word'] for s in segments[:5]]}")

        print("-" * 30)


if __name__ == "__main__":
    asyncio.run(test_streaming())
