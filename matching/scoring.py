"""Configurable match scoring engine for MatchKit.

Scoring dimensions and weights are loaded from a YAML config file
(default: config/scoring.yml). This allows white-label deployments
to define their own domain taxonomy without changing code.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from models.entities import Organization, Match
from matching.similarity import cosine_similarity, jaccard_similarity
from config.settings import settings

logger = logging.getLogger(__name__)


def _load_scoring_config(config_path: str) -> Dict[str, Any]:
    """Load scoring configuration from a YAML file."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Scoring config not found at {path}, using defaults")
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


class MatchScorer:
    """Score potential matches between organizations.

    All scoring parameters are loaded from a YAML config file,
    making the engine fully configurable for any domain.
    """

    def __init__(self, config_path: Optional[str] = None):
        config = _load_scoring_config(config_path or settings.scoring_config_path)

        # Weights
        weights = config.get("weights", {})
        self.weights: Dict[str, float] = {
            "embedding": weights.get("embedding", 0.30),
            "interest": weights.get("interest", 0.25),
            "geographic": weights.get("geographic", 0.20),
            "size": weights.get("size", 0.15),
            "preference": weights.get("preference", 0.10),
        }

        # Interest pair scores — build a lookup dict from the YAML list
        self.interest_pairs: Dict[Tuple[str, str], float] = {}
        for entry in config.get("interest_pairs", []):
            pair = entry.get("pair", [])
            if len(pair) == 2:
                self.interest_pairs[(pair[0], pair[1])] = entry["score"]

        self.same_interest_score: float = config.get("same_interest_score", 0.5)
        self.unknown_interest_pair_score: float = config.get("unknown_interest_pair_score", 0.3)
        self.empty_interest_score: float = config.get("empty_interest_score", 0.3)

        # Size compatibility — build a lookup dict
        self.size_compat: Dict[Tuple[str, str], float] = {}
        for entry in config.get("size_compatibility", []):
            pair = entry.get("pair", [])
            if len(pair) == 2:
                self.size_compat[(pair[0], pair[1])] = entry["score"]

        self.unknown_size_score: float = config.get("unknown_size_score", 0.5)

        logger.info(
            f"MatchScorer initialized: {len(self.interest_pairs)} interest pairs, "
            f"{len(self.size_compat)} size combos, weights={self.weights}"
        )

    def score_pair(self, org_a: Organization, org_b: Organization) -> Match:
        """Score a potential match between two organizations."""
        # Embedding similarity
        embedding_sim = cosine_similarity(org_a.embedding, org_b.embedding)

        # Interest/domain complementarity
        interests_a = org_a.interests or []
        interests_b = org_b.interests or []
        interest_score = self._score_interests(interests_a, interests_b)

        # Geographic overlap
        regions_a = set(org_a.regions or [])
        regions_b = set(org_b.regions or [])
        geo_score = jaccard_similarity(regions_a, regions_b)

        # Size compatibility
        size_a = org_a.organization_size or "Medium"
        size_b = org_b.organization_size or "Medium"
        size_score = self._score_size(size_a, size_b)

        # Preference alignment
        prefs_a = set(org_a.preferences or [])
        prefs_b = set(org_b.preferences or [])
        pref_score = jaccard_similarity(prefs_a, prefs_b)

        # Weighted overall score
        overall = (
            self.weights["embedding"] * embedding_sim
            + self.weights["interest"] * interest_score
            + self.weights["geographic"] * geo_score
            + self.weights["size"] * size_score
            + self.weights["preference"] * pref_score
        )

        return Match(
            source_org_id=org_a.id,
            target_org_id=org_b.id,
            overall_score=round(overall, 4),
            embedding_similarity=round(embedding_sim, 4),
            interest_score=round(interest_score, 4),
            geographic_score=round(geo_score, 4),
            size_score=round(size_score, 4),
            preference_score=round(pref_score, 4),
        )

    def _score_interests(self, interests_a: List[str], interests_b: List[str]) -> float:
        """Score interest/domain complementarity."""
        if not interests_a or not interests_b:
            return self.empty_interest_score

        max_score = 0.0
        for a in interests_a:
            for b in interests_b:
                if a == b:
                    score = self.same_interest_score
                else:
                    score = (
                        self.interest_pairs.get((a, b))
                        or self.interest_pairs.get((b, a))
                        or self.unknown_interest_pair_score
                    )
                max_score = max(max_score, score)
        return max_score

    def _score_size(self, size_a: str, size_b: str) -> float:
        """Score size compatibility."""
        return (
            self.size_compat.get((size_a, size_b))
            or self.size_compat.get((size_b, size_a))
            or self.unknown_size_score
        )

    def find_top_matches(
        self,
        target: Organization,
        candidates: List[Organization],
        top_k: int = 5,
        min_score: float = 0.4,
    ) -> List[Match]:
        """Find top matches for an organization from a list of candidates."""
        matches = []
        for candidate in candidates:
            if candidate.id == target.id:
                continue
            try:
                match = self.score_pair(target, candidate)
                if match.overall_score >= min_score:
                    matches.append(match)
            except Exception as e:
                logger.warning(f"Error scoring {target.name} vs {candidate.name}: {e}")
                continue

        matches.sort(key=lambda m: m.overall_score, reverse=True)
        return matches[:top_k]


# Singleton instance
match_scorer = MatchScorer()
