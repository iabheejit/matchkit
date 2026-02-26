"""AI-powered profile enrichment — extract structured data from free text."""
import logging
from typing import Dict, List, Optional

from ai.llm_client import llm_client

logger = logging.getLogger(__name__)

ENRICHMENT_SYSTEM_PROMPT = """You are a profile analysis assistant for a cofounder matching platform.
Given a person or organization's profile text, extract structured information.

Return a JSON object with these fields:
{
  "interests": ["list of interest areas/domains"],
  "skills": ["list of specific skills"],
  "goals": ["what they're looking for in a cofounder/partner"],
  "experience_level": "early|mid|senior|expert",
  "industries": ["relevant industries"],
  "looking_for": ["roles/skills they want in a match"],
  "summary": "A concise 1-2 sentence summary of who they are and what they want"
}

Only include fields you can confidently extract. Be specific and actionable."""


class ProfileEnricher:
    """Extract structured profile data from free-text descriptions using LLMs."""

    def enrich_from_text(self, profile_text: str) -> Optional[Dict]:
        """Extract structured profile data from free-text input."""
        if not llm_client.is_configured:
            return self._fallback_enrichment(profile_text)

        result = llm_client.chat_json(
            messages=[
                {"role": "system", "content": ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Profile text:\n\n{profile_text}"},
            ],
            temperature=0.2,
        )
        return result

    def enrich_organization(self, org) -> Optional[Dict]:
        """Enrich an Organization model with AI-extracted data."""
        text = org.to_profile_text()
        return self.enrich_from_text(text)

    def extract_interests_from_conversation(
        self, conversation: List[Dict[str, str]]
    ) -> Optional[Dict]:
        """Extract structured profile data from an onboarding conversation."""
        if not llm_client.is_configured:
            return None

        conv_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in conversation
        )

        result = llm_client.chat_json(
            messages=[
                {"role": "system", "content": ENRICHMENT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Extract profile information from this onboarding conversation:\n\n"
                        f"{conv_text}"
                    ),
                },
            ],
            temperature=0.2,
        )
        return result

    def _fallback_enrichment(self, text: str) -> Dict:
        """Basic keyword extraction when LLM is unavailable."""
        words = text.lower().split()
        # Simple keyword matching for common domains
        domain_keywords = {
            "Engineering": ["engineer", "software", "developer", "code", "technical", "backend", "frontend"],
            "Product": ["product", "pm", "roadmap", "feature", "user"],
            "Design": ["design", "ux", "ui", "creative", "visual"],
            "AI/ML": ["ai", "ml", "machine", "learning", "data", "model"],
            "Growth": ["growth", "marketing", "acquisition", "seo", "content"],
            "Sales": ["sales", "revenue", "deals", "pipeline", "b2b"],
            "Finance": ["finance", "fundraising", "investor", "capital", "accounting"],
            "Operations": ["operations", "ops", "logistics", "process", "supply"],
        }
        found_interests = []
        for domain, keywords in domain_keywords.items():
            if any(kw in words for kw in keywords):
                found_interests.append(domain)

        return {
            "interests": found_interests or ["General"],
            "summary": text[:200] if len(text) > 200 else text,
        }


# Singleton
profile_enricher = ProfileEnricher()
