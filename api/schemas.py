"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class MatchStatusEnum(str, Enum):
    SUGGESTED = "suggested"
    VIEWED = "viewed"
    CONTACTED = "contacted"
    ACTIVE = "active"
    DECLINED = "declined"


class JobName(str, Enum):
    WEEKLY_EMAILS = "weekly_emails"
    MATCH_REFRESH = "match_refresh"


# ==================== Organization Schemas ====================

class OrganizationBase(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    organization_size: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    contact_email: Optional[EmailStr] = None
    regions: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)


class OrganizationResponse(OrganizationBase):
    id: int
    regions: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    key_people: Optional[str] = None
    contact_email: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    last_synced: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationDetail(OrganizationResponse):
    activities: Optional[str] = None
    year_established: Optional[int] = None
    org_type: Optional[str] = None
    phone: Optional[str] = None
    facebook: Optional[str] = None
    metadata_text: Optional[str] = None
    external_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Match Schemas ====================

class MatchScoresResponse(BaseModel):
    embedding_similarity: float
    interest_score: float
    geographic_score: float
    size_score: float
    preference_score: float


class MatchResponse(BaseModel):
    id: int
    target_organization: OrganizationResponse
    overall_score: float
    scores: MatchScoresResponse
    rationale: Optional[str] = None
    match_type: Optional[str] = None
    status: MatchStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True


class MatchListResponse(BaseModel):
    organization_id: int
    organization_name: str
    matches: List[MatchResponse]
    total_count: int


class MatchStatusUpdate(BaseModel):
    status: MatchStatusEnum


# ==================== Job Schemas ====================

class JobTriggerRequest(BaseModel):
    job_name: JobName


class JobResultResponse(BaseModel):
    job_name: str
    success: bool
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    records_processed: int
    errors: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None


class SchedulerStatusResponse(BaseModel):
    is_running: bool
    jobs: List[Dict[str, Any]]
    last_results: Dict[str, Dict[str, Any]]


# ==================== Email Schemas ====================

class SendEmailRequest(BaseModel):
    organization_id: int
    recipient_email: EmailStr


class EmailResultResponse(BaseModel):
    success: bool
    recipient: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: Optional[datetime] = None


class BulkEmailResultResponse(BaseModel):
    total_sent: int
    total_failed: int
    results: List[EmailResultResponse]


# ==================== Health Check ====================

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database_connected: bool
    scheduler_running: bool
    email_configured: bool
    version: str = "1.0.0"


# ==================== Pagination ====================

class PaginationParams(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)
