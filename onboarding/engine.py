"""Conversational onboarding engine — AI-driven profile creation.

Replaces static forms with a dynamic conversation that extracts
structured profile data through natural dialogue.
"""
import logging
import secrets
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import OnboardingSession, OnboardingStatus, Organization
from ai.llm_client import llm_client
from ai.profile_enrichment import profile_enricher
from ai.intent_detector import intent_detector

logger = logging.getLogger(__name__)

ONBOARDING_SYSTEM_PROMPT = """You are a friendly onboarding assistant for a cofounder matching platform
inspired by the YC Co-Founder Matching system.

Your job is to have a natural conversation to learn about the user so we can find them
great cofounder matches. You need to gather:

1. **Who they are** — name, background, current role/company
2. **What they're building or want to build** — idea, stage, industry
3. **What skills they bring** — technical, business, domain expertise
4. **What they're looking for** — cofounder role, skills, personality traits
5. **Preferences** — location, commitment level, deal-breakers

Guidelines:
- Ask ONE question at a time
- Be conversational and warm, not like a form
- Adapt based on their answers — skip questions they've already answered
- After gathering enough info (usually 4-6 exchanges), summarize what you've learned
  and ask if anything is missing
- When they confirm, respond with exactly: [ONBOARDING_COMPLETE]

Keep responses concise (2-3 sentences max per turn)."""

ONBOARDING_STEPS = [
    "introduction",
    "background",
    "project_idea",
    "skills",
    "looking_for",
    "preferences",
    "confirmation",
]


class OnboardingEngine:
    """Drive conversational onboarding sessions."""

    async def start_session(self, session: AsyncSession) -> OnboardingSession:
        """Create a new onboarding session with a welcome message."""
        token = secrets.token_urlsafe(32)

        welcome = self._get_welcome_message()

        onboarding = OnboardingSession(
            session_token=token,
            conversation=[{"role": "assistant", "content": welcome}],
            current_step=0,
        )
        session.add(onboarding)
        await session.flush()

        logger.info(f"Started onboarding session {onboarding.id}")
        return onboarding

    async def process_message(
        self,
        session: AsyncSession,
        onboarding: OnboardingSession,
        user_message: str,
    ) -> Tuple[str, bool]:
        """Process a user message and return (ai_response, is_complete).

        Returns the AI's next response and whether onboarding is complete.
        """
        # Add user message to conversation
        conversation = list(onboarding.conversation or [])
        conversation.append({"role": "user", "content": user_message})

        # Generate AI response
        ai_response = self._generate_response(conversation)
        is_complete = "[ONBOARDING_COMPLETE]" in ai_response

        # Clean the completion marker from the response
        clean_response = ai_response.replace("[ONBOARDING_COMPLETE]", "").strip()
        conversation.append({"role": "assistant", "content": clean_response})

        # Update session
        onboarding.conversation = conversation
        onboarding.current_step = min(
            onboarding.current_step + 1, len(ONBOARDING_STEPS) - 1
        )

        if is_complete:
            onboarding.status = OnboardingStatus.COMPLETED.value
            # Extract structured profile from the conversation
            extracted = profile_enricher.extract_interests_from_conversation(conversation)
            intent = intent_detector.detect_from_conversation(conversation)
            if extracted:
                if intent:
                    extracted["intent"] = intent
                onboarding.extracted_profile = extracted

        await session.flush()
        return clean_response, is_complete

    async def create_profile_from_session(
        self,
        db_session: AsyncSession,
        onboarding: OnboardingSession,
    ) -> Optional[Organization]:
        """Create an Organization profile from a completed onboarding session."""
        if onboarding.status != OnboardingStatus.COMPLETED.value:
            return None

        profile = onboarding.extracted_profile or {}

        org = Organization(
            name=profile.get("name", f"User-{onboarding.id}"),
            description=profile.get("summary", ""),
            interests=profile.get("interests", []),
            preferences=profile.get("looking_for", []),
            activities=profile.get("skills", []) if isinstance(profile.get("skills"), str)
                else ", ".join(profile.get("skills", [])),
            city=profile.get("location", ""),
            organization_size=profile.get("stage", "Solo"),
        )

        db_session.add(org)
        await db_session.flush()

        # Link onboarding session to the new org
        onboarding.organization_id = org.id
        await db_session.flush()

        logger.info(f"Created profile {org.id} from onboarding session {onboarding.id}")
        return org

    async def get_session_by_token(
        self, db_session: AsyncSession, token: str
    ) -> Optional[OnboardingSession]:
        """Look up an onboarding session by its token."""
        result = await db_session.execute(
            select(OnboardingSession).where(OnboardingSession.session_token == token)
        )
        return result.scalar_one_or_none()

    def _generate_response(self, conversation: List[Dict]) -> str:
        """Generate the next AI response in the onboarding conversation."""
        if not llm_client.is_configured:
            return self._fallback_response(conversation)

        messages = [{"role": "system", "content": ONBOARDING_SYSTEM_PROMPT}]
        messages.extend(conversation)

        result = llm_client.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=300,
        )
        return result or self._fallback_response(conversation)

    def _fallback_response(self, conversation: List[Dict]) -> str:
        """Provide guided prompts when LLM is unavailable."""
        user_messages = [m for m in conversation if m["role"] == "user"]
        step = len(user_messages)

        prompts = [
            "Great to have you here! What's your name and what are you currently working on?",
            "Interesting! What skills and experience do you bring to the table?",
            "What kind of cofounder or collaborator are you looking for?",
            "Any preferences on location, commitment level, or industry focus?",
            (
                "Thanks for sharing all that! I've got a good picture of what you're looking for. "
                "Shall I create your profile so we can start finding matches? [ONBOARDING_COMPLETE]"
            ),
        ]
        return prompts[min(step, len(prompts) - 1)]

    def _get_welcome_message(self) -> str:
        return (
            "👋 Welcome to MatchKit! I'm here to help you find your perfect cofounder match. "
            "Instead of filling out a boring form, let's have a quick chat. "
            "I'll ask you a few questions to understand who you are and what you're looking for. "
            "Ready? Tell me a bit about yourself — what's your background and what are you working on?"
        )


# Singleton
onboarding_engine = OnboardingEngine()
