"""Matching engine package for MatchKit."""
from matching.embeddings import EmbeddingGenerator, embedding_generator
from matching.scoring import MatchScorer, match_scorer
from matching.recommendations import RecommendationEngine, recommendation_engine

__all__ = [
    "EmbeddingGenerator",
    "embedding_generator",
    "MatchScorer",
    "match_scorer",
    "RecommendationEngine",
    "recommendation_engine",
]
