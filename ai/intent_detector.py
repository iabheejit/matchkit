"""AI-powered intent detection — understand what users are looking for."""
import logging
from typing import Dict, List, Optional

from ai.llm_client import llm_client

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are an intent detection assistant for a cofounder matching platform.
Given a user's message or profile text, detect their primary intent and preferences.

Return a JSON object:
{
  "primary_intent": "find_technical_cofounder|find_business_cofounder|find_domain_expert|explore_ideas|networking|other",
  "urgency": "exploring|active|urgent",
  "stage": "idea|mvp|early_revenue|scaling|established",
  "looking_for_roles": ["list of roles they want"],
  "offering_skills": ["list of skills they bring"],
  "industries": ["relevant industries"],
  "deal_breakers": ["any stated requirements or constraints"],
  "confidence": 0.0-1.0
}

Only include fields you can confidently detect."""


class IntentDetector:
    """Detect user intent and preferences from text using LLMs."""

    def detect(self, text: str) -> Optional[Dict]:
        """Detect intent from free-text input."""
        if not llm_client.is_configured:
            return self._fallback_detection(text)

        return llm_client.chat_json(
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )

    def detect_from_conversation(
        self, conversation: List[Dict[str, str]]
    ) -> Optional[Dict]:
        """Detect intent from an ongoing conversation."""
        if not llm_client.is_configured:
            # Combine user messages for fallback
            user_text = " ".join(
                msg["content"] for msg in conversation if msg["role"] == "user"
            )
            return self._fallback_detection(user_text)

        conv_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in conversation
        )
        return llm_client.chat_json(
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Detect intent from this conversation:\n\n{conv_text}",
                },
            ],
            temperature=0.2,
        )

    def _fallback_detection(self, text: str) -> Dict:
        """Basic intent detection without LLM."""
        text_lower = text.lower()
        intent = "other"
        if any(w in text_lower for w in ["technical", "engineer", "developer", "cto"]):
            intent = "find_technical_cofounder"
        elif any(w in text_lower for w in ["business", "sales", "marketing", "ceo", "coo"]):
            intent = "find_business_cofounder"
        elif any(w in text_lower for w in ["expert", "advisor", "mentor", "domain"]):
            intent = "find_domain_expert"
        elif any(w in text_lower for w in ["idea", "explore", "brainstorm"]):
            intent = "explore_ideas"

        return {
            "primary_intent": intent,
            "urgency": "exploring",
            "confidence": 0.3,
        }


# Singleton
intent_detector = IntentDetector()
