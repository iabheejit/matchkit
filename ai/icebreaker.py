"""AI-powered icebreaker generation for chat rooms."""
import logging
from typing import Optional

from ai.llm_client import llm_client

logger = logging.getLogger(__name__)

ICEBREAKER_SYSTEM_PROMPT = """You are a conversation starter assistant for a cofounder matching platform.
Given two matched profiles, generate a warm, specific icebreaker message that:

- References something specific from both profiles
- Suggests a concrete topic or question to discuss
- Feels natural and not robotic
- Is 2-3 sentences max
- Encourages both parties to share more about their goals

Write the icebreaker as if it's a system message introducing both parties."""


class IcebreakerGenerator:
    """Generate AI-powered icebreaker messages for new chat rooms."""

    def generate(
        self,
        profile_a: str,
        profile_b: str,
        match_explanation: Optional[str] = None,
    ) -> str:
        """Generate an icebreaker message for two matched profiles."""
        if not llm_client.is_configured:
            return self._fallback_icebreaker()

        context = (
            f"Profile A:\n{profile_a}\n\n"
            f"Profile B:\n{profile_b}"
        )
        if match_explanation:
            context += f"\n\nWhy they matched: {match_explanation}"

        result = llm_client.chat(
            messages=[
                {"role": "system", "content": ICEBREAKER_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.8,
            max_tokens=200,
        )
        return result or self._fallback_icebreaker()

    def generate_for_match(self, match, source_org, target_org) -> str:
        """Generate icebreaker from Match and Organization model objects."""
        return self.generate(
            profile_a=source_org.to_profile_text(),
            profile_b=target_org.to_profile_text(),
            match_explanation=match.rationale,
        )

    def _fallback_icebreaker(self) -> str:
        return (
            "👋 You've been matched! You both have complementary skills and interests. "
            "Why not start by sharing what you're currently working on and what kind of "
            "cofounder or collaborator you're looking for?"
        )


# Singleton
icebreaker_generator = IcebreakerGenerator()
