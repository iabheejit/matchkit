"""SQLAlchemy domain models for MatchKit.

These models are generic and can represent any type of organization or member.
Field names like `interests`, `regions`, and `preferences` are intentionally
domain-agnostic — configure their meaning via scoring.yml and your data import.
"""
import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


# ==================== Enums ====================

class MatchStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    VIEWED = "viewed"
    CONTACTED = "contacted"
    ACTIVE = "active"
    DECLINED = "declined"


class EmailDigestStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# ==================== Models ====================

class Organization(Base):
    """An organization, group, or entity to be matched."""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Location
    city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regions: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Classification — generic tag lists
    interests: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    preferences: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    organization_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    activities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contact
    contact_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_people: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Social
    linkedin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    twitter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    facebook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    metadata_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year_established: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    org_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    # Embedding (stored as JSON array — pgvector can be used for ANN search)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Timestamps
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    members: Mapped[List["Member"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    source_matches: Mapped[List["Match"]] = relationship(
        foreign_keys="Match.source_org_id",
        back_populates="source_org",
        cascade="all, delete-orphan",
    )
    target_matches: Mapped[List["Match"]] = relationship(
        foreign_keys="Match.target_org_id",
        back_populates="target_org",
        cascade="all, delete-orphan",
    )

    def to_profile_text(self) -> str:
        """Convert to text for embedding generation.

        Override or extend this method to customize what text is embedded.
        """
        parts = [self.name]
        if self.description:
            parts.append(self.description)
        if self.interests:
            parts.append(f"Interests: {', '.join(self.interests)}")
        if self.regions:
            parts.append(f"Regions: {', '.join(self.regions)}")
        if self.preferences:
            parts.append(f"Preferences: {', '.join(self.preferences)}")
        if self.activities:
            parts.append(f"Activities: {self.activities}")
        return " | ".join(parts)

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}')>"


class Member(Base):
    """A member or contact person within an organization."""
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def __repr__(self) -> str:
        return f"<Member(id={self.id}, name='{self.full_name}', org_id={self.organization_id})>"


class Match(Base):
    """A scored match between two organizations."""
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("source_org_id", "target_org_id", name="uq_match_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    target_org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Scores
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    embedding_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    interest_score: Mapped[float] = mapped_column(Float, default=0.0)
    geographic_score: Mapped[float] = mapped_column(Float, default=0.0)
    size_score: Mapped[float] = mapped_column(Float, default=0.0)
    preference_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Details
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    match_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=MatchStatus.SUGGESTED.value, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    source_org: Mapped["Organization"] = relationship(
        foreign_keys=[source_org_id], back_populates="source_matches"
    )
    target_org: Mapped["Organization"] = relationship(
        foreign_keys=[target_org_id], back_populates="target_matches"
    )

    def __repr__(self) -> str:
        return f"<Match(src={self.source_org_id}, tgt={self.target_org_id}, score={self.overall_score:.2f})>"


class EmailDigest(Base):
    """Record of email digests sent."""
    __tablename__ = "email_digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    recipient_email: Mapped[str] = mapped_column(String(300), nullable=False)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default=EmailDigestStatus.PENDING.value
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
