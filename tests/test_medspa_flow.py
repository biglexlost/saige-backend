import pytest
from models import JAIMESSession, ConversationState, ChatMessage, CustomerProfile
from complete_saige import CompleteSAIGESystem
from medspa_service_catalog import match_service


@pytest.mark.asyncio
async def test_new_customer_intro_and_timeslot(monkeypatch):
    system = CompleteSAIGESystem(groq_api_key="test", redis_url="redis://localhost:6379")
    session = JAIMESSession(
        session_id="s1",
        caller_phone="1234567890",
        conversation_state=ConversationState.PRIOR_SERVICE_CONFIRMATION,
        conversation_history=[],
        customer_profile=None,
    )
    system.in_memory_sessions[session.session_id] = session

    # Patch LLM streaming to not call external
    async def fake_stream(prompt, sess, *args, **kwargs):
        yield "ok"

    system._call_llm_and_stream = fake_stream  # type: ignore
    system._call_llm_and_stream_enhanced = fake_stream  # type: ignore

    # Begin conversation (new customer path)
    gen = system.process_conversation("<BEGIN_CONVERSATION>", session.session_id)
    _ = [chunk async for chunk in gen]
    updated = system.get_session("s1")
    assert updated is not None
    # May remain in ask-if-visited state waiting for user response
    assert updated.conversation_state in [
        ConversationState.PRIOR_SERVICE_CONFIRMATION,
        ConversationState.SERVICE_SELECTION,
        ConversationState.PHONE_NUMBER_CLARIFICATION,
    ]

    # Now simulate service selection
    updated.conversation_state = ConversationState.SERVICE_SELECTION
    system.in_memory_sessions[updated.session_id] = updated
    gen2 = system.process_conversation("I want a hydrafacial", updated.session_id)
    _ = [chunk async for chunk in gen2]
    updated2 = system.get_session("s1")
    assert updated2.conversation_state in [ConversationState.INTAKE_QA, ConversationState.PROPOSE_SCHEDULING]


@pytest.mark.asyncio
async def test_returning_customer_phone_lookup(monkeypatch):
    system = CompleteSAIGESystem(groq_api_key="test", redis_url="redis://localhost:6379")
    session = JAIMESSession(
        session_id="s2",
        caller_phone="1234567890",
        conversation_state=ConversationState.PRIOR_SERVICE_CONFIRMATION,
        conversation_history=[],
        customer_profile=None,
    )
    system.in_memory_sessions[session.session_id] = session

    # Mock customer engine lookup
    class FakeCE:
        async def find_customer_by_phone(self, phone):
            return CustomerProfile(customer_id="1", name="Alex", phone=phone, vehicles=[], service_history=[])

    system.customer_engine = FakeCE()

    async def fake_stream(prompt, sess, *args, **kwargs):
        yield "ok"

    system._call_llm_and_stream = fake_stream  # type: ignore
    system._call_llm_and_stream_enhanced = fake_stream  # type: ignore

    # User says yes (returning)
    gen = system.process_conversation("yes", session.session_id)
    _ = [chunk async for chunk in gen]
    # Provide phone
    gen2 = system.process_conversation("(123) 456-7890", session.session_id)
    _ = [chunk async for chunk in gen2]

    updated = system.get_session("s2")
    assert updated is not None
    assert updated.customer_profile is not None
    assert updated.conversation_state in [ConversationState.SERVICE_SELECTION, ConversationState.PHONE_NUMBER_CLARIFICATION]


