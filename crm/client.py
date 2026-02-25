"""CRM API client using OAuth2 Client Credentials flow.

Provides two-way sync with a Salesforce-compatible CRM:
  - Pull: Read Account (org) and Contact (member) records
  - Push: Write match records back to the CRM

This is an optional integration — set CRM_ENABLED=true to activate.

For Salesforce, create a custom object (e.g., Match__c) with fields:
  - Source_Organization__c (Lookup → Account)
  - Target_Organization__c (Lookup → Account)
  - Overall_Score__c (Number)
  - Interest_Score__c (Number)
  - Geographic_Score__c (Number)
  - Size_Score__c (Number)
  - Preference_Score__c (Number)
  - Embedding_Score__c (Number)
  - Rationale__c (Long Text Area)
  - Status__c (Picklist)
  - Match_Type__c (Text)
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class CRMClient:
    """CRM REST API client with OAuth2 Client Credentials authentication."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._instance_url: str = settings.crm_instance_url
        self._api_version: str = settings.crm_api_version
        self._http = httpx.Client(timeout=30.0)

    @property
    def is_configured(self) -> bool:
        """Check if CRM credentials are set and integration is enabled."""
        return bool(
            settings.crm_enabled
            and settings.crm_instance_url
            and settings.crm_client_id
            and settings.crm_client_secret
        )

    # ==================== Authentication ====================

    def _authenticate(self) -> bool:
        """Obtain access token via OAuth2 Client Credentials flow."""
        if not self.is_configured:
            logger.warning("CRM credentials not configured")
            return False

        try:
            token_url = f"{self._instance_url}/services/oauth2/token"
            resp = self._http.post(token_url, data={
                "grant_type": "client_credentials",
                "client_id": settings.crm_client_id,
                "client_secret": settings.crm_client_secret,
            })
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._instance_url = data.get("instance_url", self._instance_url)
            logger.info("CRM: authenticated successfully")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"CRM auth HTTP error: {e.response.status_code} — {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"CRM auth failed: {e}")
            return False

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _api_url(self, path: str) -> str:
        return f"{self._instance_url}/services/data/{self._api_version}{path}"

    def _request(self, method: str, path: str, **kwargs) -> Optional[Any]:
        """Make an authenticated CRM API request."""
        if not self._access_token:
            if not self._authenticate():
                return None

        url = self._api_url(path)
        try:
            resp = self._http.request(method, url, headers=self._headers(), **kwargs)

            if resp.status_code == 401:
                logger.info("CRM: token expired, re-authenticating...")
                if self._authenticate():
                    resp = self._http.request(method, url, headers=self._headers(), **kwargs)

            resp.raise_for_status()
            return resp.json() if resp.content else {}

        except httpx.HTTPStatusError as e:
            logger.error(
                f"CRM API error ({method} {path}): "
                f"{e.response.status_code} — {e.response.text[:200]}"
            )
            return None
        except Exception as e:
            logger.error(f"CRM API error ({method} {path}): {e}")
            return None

    def _query(self, soql: str) -> List[Dict]:
        """Execute a SOQL query and return records."""
        import urllib.parse
        encoded = urllib.parse.quote(soql)
        result = self._request("GET", f"/query/?q={encoded}")
        return result.get("records", []) if result else []

    # ==================== Connection Test ====================

    def test_connection(self) -> bool:
        """Test CRM API connectivity."""
        if not self.is_configured:
            return False
        result = self._request("GET", "/sobjects/")
        return result is not None

    # ==================== Pull ====================

    def pull_accounts(self, limit: int = 2000) -> List[Dict]:
        """Pull Account (organization) records from the CRM."""
        soql = (
            "SELECT Id, Name, Description, Website, "
            "BillingCity, BillingState, "
            "Type, Industry, NumberOfEmployees, Phone "
            f"FROM Account LIMIT {limit}"
        )
        records = self._query(soql)
        logger.info(f"CRM: pulled {len(records)} accounts")
        return records

    def pull_contacts_for_account(self, account_id: str) -> List[Dict]:
        """Pull Contact (member) records for a specific Account."""
        soql = (
            "SELECT Id, FirstName, LastName, Email, Title "
            f"FROM Contact WHERE AccountId = '{account_id}'"
        )
        return self._query(soql)

    def pull_all_contacts(self, limit: int = 5000) -> List[Dict]:
        """Pull all Contact records with their Account IDs."""
        soql = (
            "SELECT Id, AccountId, FirstName, LastName, Email, Title "
            f"FROM Contact WHERE Email != null LIMIT {limit}"
        )
        records = self._query(soql)
        logger.info(f"CRM: pulled {len(records)} contacts")
        return records

    # ==================== Push ====================

    def push_match(self, match_object: str, match_data: Dict) -> Optional[str]:
        """Create a match record in the CRM.

        Args:
            match_object: CRM object API name (e.g., "Match__c").
            match_data: Dict with CRM field names as keys.

        Returns:
            CRM record ID if created, None on failure.
        """
        result = self._request("POST", f"/sobjects/{match_object}/", json=match_data)
        if result and "id" in result:
            logger.debug(f"CRM: created match {result['id']}")
            return result["id"]
        return None

    def update_match_status(
        self, match_object: str, record_id: str, status: str
    ) -> bool:
        """Update the status field on a match record."""
        result = self._request(
            "PATCH",
            f"/sobjects/{match_object}/{record_id}",
            json={"Status__c": status},
        )
        return result is not None


# Singleton instance
crm_client = CRMClient()
