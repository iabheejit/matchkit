"""Database repository classes for CRUD operations."""
import logging
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.entities import (
    Organization,
    Member,
    Match,
    EmailDigest,
    EmailDigestStatus,
)

logger = logging.getLogger(__name__)


class OrganizationRepository:
    """CRUD operations for organizations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, org_id: int) -> Optional[Organization]:
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Organization]:
        result = await self.session.execute(
            select(Organization).where(Organization.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self, offset: int = 0, limit: int = 100) -> Sequence[Organization]:
        result = await self.session.execute(
            select(Organization).offset(offset).limit(limit).order_by(Organization.name)
        )
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Organization.id)))
        return result.scalar_one()

    async def list_with_contacts(self) -> Sequence[Organization]:
        """Get all organizations that have a contact email."""
        result = await self.session.execute(
            select(Organization)
            .where(Organization.contact_email.isnot(None))
            .where(Organization.contact_email != "")
            .order_by(Organization.name)
        )
        return result.scalars().all()

    async def list_with_embeddings(self) -> Sequence[Organization]:
        """Get all organizations that have embeddings."""
        result = await self.session.execute(
            select(Organization).where(Organization.embedding.isnot(None))
        )
        return result.scalars().all()

    async def list_without_embeddings(self) -> Sequence[Organization]:
        """Get organizations missing embeddings."""
        result = await self.session.execute(
            select(Organization).where(Organization.embedding.is_(None))
        )
        return result.scalars().all()

    async def create(self, org: Organization) -> Organization:
        self.session.add(org)
        await self.session.flush()
        return org

    async def create_many(self, orgs: List[Organization]) -> List[Organization]:
        self.session.add_all(orgs)
        await self.session.flush()
        return orgs

    async def update(self, org: Organization) -> Organization:
        org.updated_at = datetime.utcnow()
        await self.session.flush()
        return org

    async def upsert_by_name(self, org: Organization) -> Organization:
        """Insert or update an organization by name."""
        existing = await self.get_by_name(org.name)
        if existing:
            for attr in [
                "description", "website", "city", "state", "regions",
                "interests", "preferences", "organization_size", "activities",
                "contact_email", "phone", "key_people", "linkedin", "twitter",
                "facebook", "metadata_text", "year_established", "org_type",
                "embedding",
            ]:
                new_val = getattr(org, attr, None)
                if new_val is not None:
                    setattr(existing, attr, new_val)
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        else:
            self.session.add(org)
            await self.session.flush()
            return org


class MatchRepository:
    """CRUD operations for matches."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, match_id: int) -> Optional[Match]:
        result = await self.session.execute(
            select(Match)
            .where(Match.id == match_id)
            .options(
                selectinload(Match.source_org),
                selectinload(Match.target_org),
            )
        )
        return result.scalar_one_or_none()

    async def get_matches_for_org(
        self,
        org_id: int,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[Match]:
        """Get matches where org is the source."""
        query = (
            select(Match)
            .where(Match.source_org_id == org_id)
            .options(selectinload(Match.target_org))
            .order_by(Match.overall_score.desc())
        )
        if status:
            query = query.where(Match.status == status)
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_for_org(self, org_id: int, status: Optional[str] = None) -> int:
        query = select(func.count(Match.id)).where(Match.source_org_id == org_id)
        if status:
            query = query.where(Match.status == status)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, match: Match) -> Match:
        self.session.add(match)
        await self.session.flush()
        return match

    async def create_many(self, matches: List[Match]) -> List[Match]:
        self.session.add_all(matches)
        await self.session.flush()
        return matches

    async def update_status(self, match_id: int, status: str) -> Optional[Match]:
        match = await self.get_by_id(match_id)
        if match:
            match.status = status
            match.updated_at = datetime.utcnow()
            await self.session.flush()
        return match

    async def delete_for_org(self, org_id: int) -> int:
        """Delete all matches where org is the source (for refresh)."""
        result = await self.session.execute(
            delete(Match).where(Match.source_org_id == org_id)
        )
        return result.rowcount

    async def delete_all(self) -> int:
        """Delete all matches (for full refresh)."""
        result = await self.session.execute(delete(Match))
        return result.rowcount


class MemberRepository:
    """CRUD operations for members."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_primary_for_org(self, org_id: int) -> Optional[Member]:
        result = await self.session.execute(
            select(Member)
            .where(Member.organization_id == org_id, Member.is_primary.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_for_org(self, org_id: int) -> Sequence[Member]:
        result = await self.session.execute(
            select(Member).where(Member.organization_id == org_id)
        )
        return result.scalars().all()

    async def create(self, member: Member) -> Member:
        self.session.add(member)
        await self.session.flush()
        return member


class EmailDigestRepository:
    """CRUD operations for email digest records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, digest: EmailDigest) -> EmailDigest:
        self.session.add(digest)
        await self.session.flush()
        return digest

    async def mark_sent(self, digest_id: int) -> Optional[EmailDigest]:
        result = await self.session.execute(
            select(EmailDigest).where(EmailDigest.id == digest_id)
        )
        digest = result.scalar_one_or_none()
        if digest:
            digest.status = EmailDigestStatus.SENT.value
            digest.sent_at = datetime.utcnow()
            await self.session.flush()
        return digest

    async def mark_failed(self, digest_id: int, error: str) -> Optional[EmailDigest]:
        result = await self.session.execute(
            select(EmailDigest).where(EmailDigest.id == digest_id)
        )
        digest = result.scalar_one_or_none()
        if digest:
            digest.status = EmailDigestStatus.FAILED.value
            digest.error_message = error
            await self.session.flush()
        return digest
