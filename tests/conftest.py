"""Shared test fixtures for MatchKit."""
import pytest
from models.entities import Organization


@pytest.fixture
def sample_org_a() -> Organization:
    """A sample technology-focused organization."""
    org = Organization(
        name="TechBridge Foundation",
        description="Building technology solutions for community development",
        city="San Francisco",
        state="California",
        regions=["California", "Oregon", "Washington"],
        interests=["Technology", "Education"],
        preferences=["Youth", "Underserved Communities"],
        organization_size="Large",
        contact_email="contact@techbridge.org",
        website="https://techbridge.org",
    )
    org.id = 1
    return org


@pytest.fixture
def sample_org_b() -> Organization:
    """A sample education-focused organization."""
    org = Organization(
        name="LearnForward Alliance",
        description="Providing quality education and mentorship programs",
        city="New York",
        state="New York",
        regions=["New York", "Washington", "Massachusetts"],
        interests=["Education", "Youth Development"],
        preferences=["Youth", "Students"],
        organization_size="Medium",
        contact_email="info@learnforward.org",
        website="https://learnforward.org",
    )
    org.id = 2
    return org


@pytest.fixture
def sample_org_c() -> Organization:
    """A sample community-focused organization."""
    org = Organization(
        name="Community Builders Network",
        description="Empowering local communities through grassroots programs",
        city="Austin",
        state="Texas",
        regions=["Texas", "New Mexico"],
        interests=["Social Impact", "Community Development", "Finance"],
        preferences=["Families", "Local Communities"],
        organization_size="Small",
    )
    org.id = 3
    return org


@pytest.fixture
def sample_embedding():
    """A sample embedding (simplified to 10-dim for tests)."""
    import numpy as np
    rng = np.random.default_rng(42)
    return rng.random(10).tolist()
