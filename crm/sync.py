"""CRM ↔ Database sync logic.

Bridges the CRM API client with the local PostgreSQL database:
  - pull_organizations(): CRM Accounts → DB Organizations
  - pull_members(): CRM Contacts → DB Members
  - push_matches(): DB Matches → CRM custom object
"""
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crm.client import crm_client
from models.entities import Organization, Member
from db.repositories import OrganizationRepository, MemberRepository, MatchRepository

logger = logging.getLogger(__name__)


def _parse_semicolon_list(value: Optional[str]) -> List[str]:
    """Parse semicolon-separated multi-select picklist values."""
    if not value:
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def _infer_size(num_employees: Optional[int]) -> str:
    """Convert employee count to size category."""
    if not num_employees:
        return "Medium"
    if num_employees < 20:
        return "Small"
    elif num_employees < 100:
        return "Medium"
    return "Large"


def account_to_organization(account: dict) -> Organization:
    """Convert a CRM Account record to an Organization model."""
    return Organization(
        name=account.get("Name", "Unknown"),
        description=account.get("Description"),
        website=account.get("Website"),
        city=account.get("BillingCity"),
        state=account.get("BillingState"),
        organization_size=_infer_size(account.get("NumberOfEmployees")),
        phone=account.get("Phone"),
        external_id=account.get("Id"),
    )


def contact_to_member(contact: dict, org_id: int) -> Member:
    """Convert a CRM Contact record to a Member model."""
    return Member(
        organization_id=org_id,
        first_name=contact.get("FirstName", ""),
        last_name=contact.get("LastName"),
        email=contact.get("Email", ""),
        role=contact.get("Title"),
        is_primary=True,
    )


class CRMSync:
    """Orchestrates sync between CRM and the local database."""

    def __init__(self):
        self.client = crm_client

    @property
    def is_available(self) -> bool:
        return self.client.is_configured

    async def pull_organizations(self, session: AsyncSession) -> int:
        """Pull Account records from CRM and upsert into DB."""
        if not self.is_available:
            logger.warning("CRM not configured — skipping org pull")
            return 0

        accounts = self.client.pull_accounts()
        if not accounts:
            logger.warning("No accounts returned from CRM")
            return 0

        org_repo = OrganizationRepository(session)
        synced = 0

        for account in accounts:
            try:
                org = account_to_organization(account)
                await org_repo.upsert_by_name(org)
                synced += 1
            except Exception as e:
                logger.error(f"Failed to sync account {account.get('Name')}: {e}")

        await session.flush()
        logger.info(f"CRM sync: {synced}/{len(accounts)} organizations pulled")
        return synced

    async def pull_members(self, session: AsyncSession) -> int:
        """Pull Contact records from CRM and link to DB organizations."""
        if not self.is_available:
            return 0

        contacts = self.client.pull_all_contacts()
        if not contacts:
            return 0

        member_repo = MemberRepository(session)
        synced = 0

        by_account: dict = {}
        for contact in contacts:
            acct_id = contact.get("AccountId")
            if acct_id:
                by_account.setdefault(acct_id, []).append(contact)

        for acct_id, acct_contacts in by_account.items():
            from sqlalchemy import select
            result = await session.execute(
                select(Organization).where(Organization.external_id == acct_id)
            )
            org = result.scalar_one_or_none()
            if not org:
                continue

            for i, contact in enumerate(acct_contacts):
                try:
                    member = contact_to_member(contact, org.id)
                    member.is_primary = (i == 0)
                    await member_repo.create(member)
                    synced += 1
                except Exception as e:
                    logger.error(f"Failed to sync contact {contact.get('Email')}: {e}")

        await session.flush()
        logger.info(f"CRM sync: {synced} members pulled")
        return synced

    async def push_matches(self, session: AsyncSession) -> int:
        """Push match results from DB to CRM."""
        if not self.is_available:
            logger.warning("CRM not configured — skipping match push")
            return 0

        org_repo = OrganizationRepository(session)
        match_repo = MatchRepository(session)

        orgs = await org_repo.list_all(limit=10000)
        total_pushed = 0

        for org in orgs:
            if not org.external_id:
                continue

            matches = await match_repo.get_matches_for_org(org.id, limit=10)
            if not matches:
                continue

            for m in matches:
                target = await org_repo.get_by_id(m.target_org_id)
                if not target or not target.external_id:
                    continue

                match_data = {
                    "Source_Organization__c": org.external_id,
                    "Target_Organization__c": target.external_id,
                    "Overall_Score__c": m.overall_score,
                    "Interest_Score__c": m.interest_score,
                    "Geographic_Score__c": m.geographic_score,
                    "Size_Score__c": m.size_score,
                    "Preference_Score__c": m.preference_score,
                    "Embedding_Score__c": m.embedding_similarity,
                    "Rationale__c": m.rationale,
                    "Status__c": "Suggested",
                }
                if self.client.push_match("Match__c", match_data):
                    total_pushed += 1

        logger.info(f"CRM sync: {total_pushed} matches pushed")
        return total_pushed


# Singleton instance
crm_sync = CRMSync()
