"""Tests for email_service/builder.py."""
from email_service.builder import EmailBuilder


def _sample_match(**overrides):
    """Build a sample match dict for testing."""
    base = {
        "org": {
            "name": "Partner Org",
            "description": "A great partner",
            "interests": ["Technology", "Education"],
            "regions": ["California", "Oregon"],
            "website": "https://partner.org",
        },
        "score": 0.85,
        "embedding_sim": 0.9,
        "interest_score": 0.8,
        "geo_score": 0.7,
        "rationale": "Strong interest alignment",
        "profile_url": "https://example.com/members/partner-org/",
    }
    base.update(overrides)
    return base


class TestEmailBuilder:
    def setup_method(self):
        self.builder = EmailBuilder()

    def test_build_digest_returns_all_keys(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Alice", "org_name": "Test Org"},
            matches=[_sample_match()],
        )
        assert "html" in result
        assert "text" in result
        assert "subject" in result

    def test_html_contains_member_and_org_name(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Alice", "org_name": "My Org"},
            matches=[_sample_match(
                org={"name": "Match Org", "description": None,
                     "interests": ["Tech"], "regions": ["CA"], "website": None}
            )],
        )
        assert "Alice" in result["html"]
        assert "My Org" in result["html"]
        assert "Match Org" in result["html"]

    def test_text_contains_member_and_org_name(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Alice", "org_name": "My Org"},
            matches=[_sample_match(
                org={"name": "Match Org", "description": None,
                     "interests": [], "regions": [], "website": None}
            )],
        )
        assert "Alice" in result["text"]
        assert "My Org" in result["text"]
        assert "Match Org" in result["text"]

    def test_subject_contains_app_name(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Test", "org_name": "Test Org"},
            matches=[],
        )
        assert "MatchKit" in result["subject"]

    def test_empty_matches_renders(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Test", "org_name": "Test Org"},
            matches=[],
        )
        assert "0 recommended matches" in result["html"]

    def test_html_escapes_special_chars(self):
        result = self.builder.build_digest(
            recipient_org={
                "first_name": '<script>alert("xss")</script>',
                "org_name": "Safe Org",
            },
            matches=[],
        )
        assert "<script>" not in result["html"]
        assert "&lt;script&gt;" in result["html"]

    def test_profile_url_in_html(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Test", "org_name": "Test Org"},
            matches=[_sample_match()],
        )
        assert "example.com/members/partner-org/" in result["html"]
        assert "View Profile" in result["html"]

    def test_profile_url_in_text(self):
        result = self.builder.build_digest(
            recipient_org={"first_name": "Test", "org_name": "Test Org"},
            matches=[_sample_match()],
        )
        assert "example.com/members/partner-org/" in result["text"]
