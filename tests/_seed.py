"""Seed test data for local testing."""
import asyncio
from db.session import async_session_factory, engine
from db.base import Base
from models.entities import Organization, Member


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Update existing profiles with real data
        from sqlalchemy import select, update

        # Profile 1: Alex — technical cofounder
        await session.execute(
            update(Organization).where(Organization.id == 1).values(
                name="Alex Chen",
                description="Full-stack engineer with 8 years in fintech. Building an AI-powered education platform.",
                interests=["Engineering", "AI/ML", "EdTech"],
                preferences=["business cofounder", "sales", "fundraising"],
                city="San Francisco",
                regions=["Bay Area", "US West"],
                organization_size="Solo",
                activities="Python, React, cloud infrastructure, data pipelines, product design",
                contact_email="alex@example.com",
            )
        )

        # Profile 2: Jordan — business cofounder
        await session.execute(
            update(Organization).where(Organization.id == 2).values(
                name="Jordan Rivera",
                description="EdTech sales leader with 10 years in education partnerships. Looking for a technical cofounder.",
                interests=["Sales", "EdTech", "Partnerships"],
                preferences=["technical cofounder", "engineer", "AI/ML"],
                city="San Francisco",
                regions=["Bay Area", "US West"],
                organization_size="Solo",
                activities="Sales, fundraising, education industry connections, B2B partnerships",
                contact_email="jordan@example.com",
            )
        )

        # Add 3 more profiles for richer matching
        profiles = [
            Organization(
                name="Sam Patel",
                description="ML researcher turned entrepreneur. Building computer vision tools for healthcare.",
                interests=["AI/ML", "HealthTech", "Engineering"],
                preferences=["business cofounder", "domain expert"],
                city="New York",
                regions=["US East", "Remote"],
                organization_size="Early Team",
                activities="Machine learning, computer vision, research, Python, PyTorch",
                contact_email="sam@example.com",
            ),
            Organization(
                name="Morgan Lee",
                description="Growth marketer and community builder. Passionate about climate tech and sustainability.",
                interests=["Growth", "Climate", "Community"],
                preferences=["technical cofounder", "engineer"],
                city="Austin",
                regions=["US South", "Remote"],
                organization_size="Solo",
                activities="Growth marketing, community building, content strategy, SEO",
                contact_email="morgan@example.com",
            ),
            Organization(
                name="Riley Kim",
                description="Product designer with startup experience. Interested in AI tools for creative professionals.",
                interests=["Design", "AI/ML", "Product"],
                preferences=["engineer", "technical cofounder"],
                city="San Francisco",
                regions=["Bay Area", "Remote"],
                organization_size="Solo",
                activities="UX/UI design, product strategy, user research, Figma, prototyping",
                contact_email="riley@example.com",
            ),
        ]
        session.add_all(profiles)

        # Add members for email testing
        members = [
            Member(organization_id=1, first_name="Alex", last_name="Chen", email="alex@example.com", is_primary=True),
            Member(organization_id=2, first_name="Jordan", last_name="Rivera", email="jordan@example.com", is_primary=True),
        ]
        session.add_all(members)

        await session.commit()
        print("✅ Seed data created: 5 profiles, 2 members")


asyncio.run(seed())
