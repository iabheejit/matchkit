"""Tests for matching/scoring.py."""
import pytest
from matching.scoring import MatchScorer


class TestMatchScorer:
    def setup_method(self):
        self.scorer = MatchScorer()

    def test_score_pair_returns_match(self, sample_org_a, sample_org_b):
        match = self.scorer.score_pair(sample_org_a, sample_org_b)
        assert match.source_org_id == sample_org_a.id
        assert match.target_org_id == sample_org_b.id
        assert 0.0 <= match.overall_score <= 1.0

    def test_score_pair_sub_scores_bounded(self, sample_org_a, sample_org_b):
        match = self.scorer.score_pair(sample_org_a, sample_org_b)
        assert 0.0 <= match.embedding_similarity <= 1.0
        assert 0.0 <= match.interest_score <= 1.0
        assert 0.0 <= match.geographic_score <= 1.0
        assert 0.0 <= match.size_score <= 1.0
        assert 0.0 <= match.preference_score <= 1.0

    def test_identical_org_scores_high(self, sample_org_a):
        """An org matched against itself should score high on non-embedding factors."""
        import copy
        org_copy = copy.deepcopy(sample_org_a)
        org_copy.id = 999
        match = self.scorer.score_pair(sample_org_a, org_copy)
        assert match.geographic_score == pytest.approx(1.0)
        assert match.preference_score == pytest.approx(1.0)

    def test_find_top_matches(self, sample_org_a, sample_org_b, sample_org_c):
        candidates = [sample_org_a, sample_org_b, sample_org_c]
        matches = self.scorer.find_top_matches(sample_org_a, candidates, top_k=5, min_score=0.0)
        assert all(m.target_org_id != sample_org_a.id for m in matches)
        scores = [m.overall_score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_find_top_matches_respects_min_score(self, sample_org_a, sample_org_b, sample_org_c):
        candidates = [sample_org_a, sample_org_b, sample_org_c]
        matches = self.scorer.find_top_matches(sample_org_a, candidates, top_k=5, min_score=0.99)
        assert len(matches) == 0

    def test_find_top_matches_respects_top_k(self, sample_org_a, sample_org_b, sample_org_c):
        candidates = [sample_org_a, sample_org_b, sample_org_c]
        matches = self.scorer.find_top_matches(sample_org_a, candidates, top_k=1, min_score=0.0)
        assert len(matches) <= 1


class TestInterestScoring:
    def setup_method(self):
        self.scorer = MatchScorer()

    def test_complementary_interests_score_high(self):
        score = self.scorer._score_interests(["Technology"], ["Education"])
        assert score >= 0.9

    def test_same_interest_scores_moderate(self):
        score = self.scorer._score_interests(["Education"], ["Education"])
        assert score == pytest.approx(0.5)

    def test_empty_interests_score_low(self):
        assert self.scorer._score_interests([], ["Technology"]) == pytest.approx(0.3)
        assert self.scorer._score_interests(["Technology"], []) == pytest.approx(0.3)

    def test_unknown_pair_scores_baseline(self):
        score = self.scorer._score_interests(["Unknown1"], ["Unknown2"])
        assert score == pytest.approx(0.3)


class TestSizeScoring:
    def setup_method(self):
        self.scorer = MatchScorer()

    def test_large_small_scores_high(self):
        assert self.scorer._score_size("Large", "Small") == 0.9

    def test_unknown_size_returns_default(self):
        assert self.scorer._score_size("Tiny", "Huge") == 0.5
