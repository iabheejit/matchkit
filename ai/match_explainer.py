"""AI-powered match explanations — generate human-readable rationales."""
import logging
from typing import Optional

from ai.llm_client import llm_client

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = """You are a match explanation assistant for a cofounder matching platform.
Given two profiles and their match scores, write a concise, warm, and specific explanation
of why these two people/organizations are a good match.

Guidelines:
- Be specific about complementary skills, shared interests, or geographic overlap
- Keep it to 2-3 sentences max
- Use a friendly, encouraging tone
- Highlight the most compelling reason to connect
- Don't mention raw scores or numbers"""


class MatchExplainer:
    """Generate natural-language explanations for why two profiles match."""

    def explain(
        self,
        source_profile: str,
        target_profile: str,
        scores: dict,
    ) -> Optional[str]:
        """Generate a match explanation given two profiles and their scores."""
        if not llm_client.is_configured:
            return self._fallback_explanation(scores)

        score_summary = (
            f"Overall: {scores.get('overall', 0):.0%}, "
            f"Interest complementarity: {scores.get('interest', 0):.0%}, "
            f"Semantic similarity: {scores.get('embedding', 0):.0%}, "
            f"Geographic overlap: {scores.get('geographic', 0):.0%}"
        )

        result = llm_client.chat(
            messages=[
                {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Profile A:\n{source_profile}\n\n"
                        f"Profile B:\n{target_profile}\n\n"
                        f"Match scores: {score_summary}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=200,
        )
        return result

    def explain_match_object(self, match, source_org, target_org) -> Optional[str]:
        """Generate explanation from Match and Organization model objects."""
        scores = {
            "overall": match.overall_score,
            "embedding": match.embedding_similarity,
            "interest": match.interest_score,
            "geographic": match.geographic_score,
            "size": match.size_score,
            "preference": match.preference_score,
        }
        return self.explain(
            source_profile=source_org.to_profile_text(),
            target_profile=target_org.to_profile_text(),
            scores=scores,
        )

    def _fallback_explanation(self, scores: dict) -> str:
        """Generate a basic explanation without LLM."""
        parts = []
        if scores.get("interest", 0) > 0.7:
            parts.append("strong interest complementarity")
        if scores.get("embedding", 0) > 0.7:
            parts.append("highly similar profiles")
        if scores.get("geographic", 0) > 0.7:
            parts.append("geographic proximity")
        if scores.get("preference", 0) > 0.5:
            parts.append("aligned preferences")

        if parts:
            return f"This match shows {', '.join(parts)}."
        return "This match was identified based on multiple compatibility factors."


# Singleton
match_explainer = MatchExplainer()
