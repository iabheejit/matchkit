"""Scheduled jobs for MatchKit."""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from config.settings import settings
from db.session import async_session_factory
from db.repositories import (
    OrganizationRepository, MatchRepository, MemberRepository, EmailDigestRepository,
)
from matching.recommendations import recommendation_engine
from email_service.sender import email_sender
from models.entities import EmailDigest, EmailDigestStatus
from utils.urls import get_profile_url

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    """Result of a scheduled job."""
    job_name: str
    success: bool
    started_at: datetime
    completed_at: datetime
    records_processed: int = 0
    errors: Optional[List[str]] = None
    details: Optional[Dict] = None

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


class ScheduledJobs:
    """Collection of scheduled jobs."""

    def __init__(self):
        self.last_results: Dict[str, JobResult] = {}

    async def run_weekly_emails(self) -> JobResult:
        """Send match digest emails to all organizations with members."""
        started_at = datetime.utcnow()
        errors = []
        details = {"emails_sent": 0, "emails_failed": 0, "orgs_skipped": 0}

        try:
            async with async_session_factory() as session:
                org_repo = OrganizationRepository(session)
                match_repo = MatchRepository(session)
                member_repo = MemberRepository(session)
                digest_repo = EmailDigestRepository(session)

                all_orgs = await org_repo.list_all(limit=10000)
                logger.info(f"Checking {len(all_orgs)} organizations for members")

                for org in all_orgs:
                    try:
                        members = await member_repo.get_for_org(org.id)
                        if not members:
                            details["orgs_skipped"] += 1
                            continue

                        matches = await match_repo.get_matches_for_org(
                            org.id, limit=settings.max_matches_per_email
                        )
                        if not matches:
                            details["orgs_skipped"] += 1
                            continue

                        match_data = []
                        for m in matches:
                            match_data.append({
                                "org": {
                                    "name": m.target_org.name,
                                    "description": m.target_org.description,
                                    "interests": m.target_org.interests or [],
                                    "regions": m.target_org.regions or [],
                                    "website": m.target_org.website,
                                },
                                "score": m.overall_score,
                                "embedding_sim": m.embedding_similarity,
                                "interest_score": m.interest_score,
                                "geo_score": m.geographic_score,
                                "rationale": m.rationale,
                                "profile_url": get_profile_url(m.target_org.name),
                            })

                        for member in members:
                            if not member.email:
                                continue

                            recipient = {
                                "first_name": member.first_name,
                                "org_name": org.name,
                            }

                            result = email_sender.send_digest(
                                to_email=member.email,
                                recipient_org=recipient,
                                matches=match_data,
                            )

                            digest = EmailDigest(
                                organization_id=org.id,
                                recipient_email=member.email,
                                match_count=len(match_data),
                                status=(
                                    EmailDigestStatus.SENT.value
                                    if result.success
                                    else EmailDigestStatus.FAILED.value
                                ),
                                sent_at=result.sent_at,
                                error_message=result.error,
                            )
                            await digest_repo.create(digest)

                            if result.success:
                                details["emails_sent"] += 1
                            else:
                                details["emails_failed"] += 1
                                errors.append(f"Failed for {member.email}: {result.error}")

                    except Exception as e:
                        details["emails_failed"] += 1
                        errors.append(f"Error for {org.name}: {e}")
                        logger.error(f"Email job error for {org.name}: {e}")

                await session.commit()

            logger.info(
                f"Email digest: {details['emails_sent']} sent, "
                f"{details['emails_failed']} failed, {details['orgs_skipped']} skipped"
            )

            result = JobResult(
                job_name="weekly_emails",
                success=details["emails_failed"] == 0,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                records_processed=details["emails_sent"],
                errors=errors if errors else None,
                details=details,
            )

        except Exception as e:
            logger.error(f"Email digest job failed: {e}")
            result = JobResult(
                job_name="weekly_emails",
                success=False,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                errors=[str(e)],
            )

        self.last_results["weekly_emails"] = result
        return result

    async def run_match_refresh(self) -> JobResult:
        """Refresh match scores for all organizations."""
        started_at = datetime.utcnow()

        try:
            async with async_session_factory() as session:
                org_repo = OrganizationRepository(session)
                match_repo = MatchRepository(session)

                all_orgs = list(await org_repo.list_all(limit=10000))
                logger.info(f"Refreshing matches for {len(all_orgs)} organizations")

                all_matches = recommendation_engine.generate_all(all_orgs, top_n=10)

                deleted = await match_repo.delete_all()
                logger.info(f"Deleted {deleted} old matches")

                total_created = 0
                for matches in all_matches.values():
                    if matches:
                        await match_repo.create_many(matches)
                        total_created += len(matches)

                for org in all_orgs:
                    if org.embedding is not None:
                        await org_repo.update(org)

                await session.commit()

            logger.info(f"Match refresh complete: {total_created} matches created")

            result = JobResult(
                job_name="match_refresh",
                success=True,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                records_processed=total_created,
                details={
                    "organizations": len(all_orgs),
                    "matches_created": total_created,
                },
            )

        except Exception as e:
            logger.error(f"Match refresh failed: {e}")
            result = JobResult(
                job_name="match_refresh",
                success=False,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                errors=[str(e)],
            )

        self.last_results["match_refresh"] = result
        return result

    async def run_engagement_nudges(self) -> JobResult:
        """Generate and send AI-powered engagement nudges."""
        started_at = datetime.utcnow()
        errors = []
        details = {"nudges_sent": 0, "nudges_failed": 0}

        try:
            from ai.nudge_generator import nudge_generator
            from models.entities import EngagementNudge

            async with async_session_factory() as session:
                org_repo = OrganizationRepository(session)
                match_repo = MatchRepository(session)
                from db.repositories import NudgeRepository
                nudge_repo = NudgeRepository(session)

                all_orgs = await org_repo.list_all(limit=10000)

                for org in all_orgs:
                    try:
                        # Determine nudge type based on activity
                        matches = await match_repo.get_matches_for_org(org.id, limit=1)
                        if not matches:
                            nudge_type = "profile_incomplete"
                        else:
                            nudge_type = "match_reminder"

                        context = {
                            "count": await match_repo.count_for_org(org.id),
                            "interest": (org.interests[0] if org.interests else "your field"),
                        }

                        content = nudge_generator.generate(
                            nudge_type=nudge_type,
                            profile_text=org.to_profile_text(),
                            context=context,
                        )

                        nudge = EngagementNudge(
                            organization_id=org.id,
                            nudge_type=nudge_type,
                            channel="email",
                            content=content,
                        )
                        await nudge_repo.create(nudge)

                        # Send via email if org has contact
                        if org.contact_email and email_sender.is_configured:
                            result = email_sender.send(
                                to_email=org.contact_email,
                                subject=f"💡 {settings.app_name} — {content[:50]}...",
                                html_content=f"<p>{content}</p>",
                                text_content=content,
                            )
                            if result.success:
                                nudge.sent_at = datetime.utcnow()
                                details["nudges_sent"] += 1
                            else:
                                details["nudges_failed"] += 1
                                errors.append(f"Nudge failed for {org.name}: {result.error}")
                        else:
                            details["nudges_sent"] += 1  # Created but not emailed

                    except Exception as e:
                        details["nudges_failed"] += 1
                        errors.append(f"Nudge error for {org.name}: {e}")

                await session.commit()

            result = JobResult(
                job_name="engagement_nudges",
                success=details["nudges_failed"] == 0,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                records_processed=details["nudges_sent"],
                errors=errors if errors else None,
                details=details,
            )

        except Exception as e:
            logger.error(f"Engagement nudge job failed: {e}")
            result = JobResult(
                job_name="engagement_nudges",
                success=False,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                errors=[str(e)],
            )

        self.last_results["engagement_nudges"] = result
        return result


# Singleton instance
jobs = ScheduledJobs()
