"""AI-powered engagement nudge generation."""
import logging
from typing import Dict, Optional

from ai.llm_client import llm_client

logger = logging.getLogger(__name__)

NUDGE_SYSTEM_PROMPT = """You are an engagement assistant for a cofounder matching platform.
Generate a short, personalized nudge message to re-engage a user.

Guidelines:
- Keep it to 1-2 sentences
- Be warm and encouraging, not pushy
- Reference something specific about their profile or activity
- Include a clear call to action
- Vary your tone — don't be repetitive"""

NUDGE_TEMPLATES = {
    "match_reminder": (
        "You have {count} new matches waiting! Your top match shares your interest in "
        "{interest}. Check them out and start a conversation."
    ),
    "chat_followup": (
        "Your conversation with {match_name} has been quiet for a few days. "
        "Why not follow up and see how things are going?"
    ),
    "profile_incomplete": (
        "Complete your profile to get better matches! Adding your skills and goals "
        "helps our AI find the perfect cofounder for you."
    ),
    "re_engagement": (
        "We miss you! There are {count} new people on the platform who match your "
        "interests. Come back and explore your latest matches."
    ),
}


class NudgeGenerator:
    """Generate personalized engagement nudges using AI."""

    def generate(
        self,
        nudge_type: str,
        profile_text: str,
        context: Optional[Dict] = None,
    ) -> str:
        """Generate a personalized nudge message."""
        context = context or {}

        if not llm_client.is_configured:
            return self._fallback_nudge(nudge_type, context)

        result = llm_client.chat(
            messages=[
                {"role": "system", "content": NUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Nudge type: {nudge_type}\n"
                        f"User profile: {profile_text}\n"
                        f"Context: {context}"
                    ),
                },
            ],
            temperature=0.8,
            max_tokens=150,
        )
        return result or self._fallback_nudge(nudge_type, context)

    def _fallback_nudge(self, nudge_type: str, context: Dict) -> str:
        """Use template-based nudges when LLM is unavailable."""
        template = NUDGE_TEMPLATES.get(nudge_type, NUDGE_TEMPLATES["re_engagement"])
        try:
            return template.format(**context)
        except KeyError:
            # Fill missing keys with defaults
            defaults = {"count": "several", "interest": "your field", "match_name": "your match"}
            merged = {**defaults, **context}
            return template.format(**merged)


# Singleton
nudge_generator = NudgeGenerator()
