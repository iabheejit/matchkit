"""Recommendation engine — orchestrates embeddings + scoring + persistence."""
import logging
from typing import Dict, List

from models.entities import Organization, Match
from matching.embeddings import embedding_generator
from matching.scoring import match_scorer
from config.settings import settings

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Generate match recommendations for organizations."""

    def __init__(self):
        self.embedding_gen = embedding_generator
        self.scorer = match_scorer

    def generate_for_org(
        self,
        org: Organization,
        all_orgs: List[Organization],
        top_n: int = 10,
    ) -> List[Match]:
        """Generate top-N match recommendations for a single organization."""
        if org.embedding is None:
            logger.info(f"Generating embedding for {org.name}")
            org.embedding = self.embedding_gen.generate_for_organization(org)

        matches = self.scorer.find_top_matches(
            target=org,
            candidates=all_orgs,
            top_k=top_n,
            min_score=settings.min_match_score,
        )

        logger.info(f"Generated {len(matches)} matches for {org.name}")
        return matches

    def generate_all(
        self,
        orgs: List[Organization],
        top_n: int = 10,
    ) -> Dict[int, List[Match]]:
        """Generate match recommendations for all organizations.

        First generates embeddings for any orgs missing them (in batch),
        then scores all pairs.
        """
        # Step 1: Generate missing embeddings in batch
        orgs_needing_embeddings = [o for o in orgs if o.embedding is None]
        if orgs_needing_embeddings:
            logger.info(f"Generating embeddings for {len(orgs_needing_embeddings)} organizations")
            texts = [o.to_profile_text() for o in orgs_needing_embeddings]
            embeddings = self.embedding_gen.generate_batch(texts)
            for org, emb in zip(orgs_needing_embeddings, embeddings):
                org.embedding = emb

        # Step 2: Score all pairs
        all_matches: Dict[int, List[Match]] = {}
        for org in orgs:
            if org.id is None:
                continue
            matches = self.scorer.find_top_matches(
                target=org,
                candidates=orgs,
                top_k=top_n,
                min_score=settings.min_match_score,
            )
            all_matches[org.id] = matches

        total = sum(len(m) for m in all_matches.values())
        logger.info(f"Generated {total} total matches for {len(orgs)} organizations")
        return all_matches


# Singleton instance
recommendation_engine = RecommendationEngine()
