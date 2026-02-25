"""CSV loader for importing organization profiles into the database.

Column mapping is configurable — override CSV_COLUMN_MAP or provide
a custom mapping via config/csv_mapping.yml.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from models.entities import Organization

logger = logging.getLogger(__name__)

# Default CSV column name → model field name mapping.
# Override this for your data format.
CSV_COLUMN_MAP: Dict[str, str] = {
    "organization_name": "name",
    "description": "description",
    "website": "website",
    "city": "city",
    "state": "state",
    "regions": "regions",
    "interests": "interests",
    "preferences": "preferences",
    "num_employees": "organization_size",
    "activities": "activities",
    "email": "contact_email",
    "phone": "phone",
    "key_people": "key_people",
    "linkedin": "linkedin",
    "twitter": "twitter",
    "facebook": "facebook",
    "metadata": "metadata_text",
    "year_established": "year_established",
    "org_type": "org_type",
    "external_id": "external_id",
}


def _parse_comma_list(value: Optional[str]) -> List[str]:
    """Parse a comma-separated string into a list of stripped strings."""
    if not value or pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _parse_size(value: Optional[str]) -> str:
    """Normalize employee count to size category."""
    if not value or pd.isna(value):
        return "Medium"
    try:
        count = int(str(value).strip())
        if count < 20:
            return "Small"
        elif count < 100:
            return "Medium"
        else:
            return "Large"
    except (ValueError, TypeError):
        val = str(value).strip().lower()
        if val in ("small", "medium", "large"):
            return val.capitalize()
        return "Medium"


def _parse_year(value: Optional[str]) -> Optional[int]:
    """Parse year from string."""
    if not value or pd.isna(value):
        return None
    try:
        return int(str(value).strip()[:4])
    except (ValueError, TypeError):
        return None


def _safe_str(value) -> Optional[str]:
    """Convert to string or None if NaN/empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s if s else None


def load_organizations_from_csv(
    csv_path: str | Path,
    column_map: Optional[Dict[str, str]] = None,
) -> List[Organization]:
    """Load organizations from a CSV file and return model instances.

    Args:
        csv_path: Path to the CSV file.
        column_map: Optional custom column mapping (CSV col → model field).
                    Falls back to CSV_COLUMN_MAP.

    Returns:
        List of Organization instances (not yet persisted to DB).
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    cmap = column_map or CSV_COLUMN_MAP
    # Build reverse map: model field → CSV column name
    reverse_map = {v: k for k, v in cmap.items()}

    logger.info(f"Loading organizations from {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info(f"Found {len(df)} rows in CSV")

    organizations: List[Organization] = []
    seen_names = set()

    name_col = reverse_map.get("name", "organization_name")

    for _, row in df.iterrows():
        name = _safe_str(row.get(name_col))
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        org = Organization(
            name=name,
            description=_safe_str(row.get(reverse_map.get("description", "description"))),
            website=_safe_str(row.get(reverse_map.get("website", "website"))),
            city=_safe_str(row.get(reverse_map.get("city", "city"))),
            state=_safe_str(row.get(reverse_map.get("state", "state"))),
            regions=_parse_comma_list(row.get(reverse_map.get("regions", "regions"))),
            interests=_parse_comma_list(row.get(reverse_map.get("interests", "interests"))),
            preferences=_parse_comma_list(row.get(reverse_map.get("preferences", "preferences"))),
            organization_size=_parse_size(
                row.get(reverse_map.get("organization_size", "num_employees"))
            ),
            activities=_safe_str(row.get(reverse_map.get("activities", "activities"))),
            contact_email=_safe_str(
                row.get(reverse_map.get("contact_email", "email"))
            ),
            phone=_safe_str(row.get(reverse_map.get("phone", "phone"))),
            key_people=_safe_str(row.get(reverse_map.get("key_people", "key_people"))),
            linkedin=_safe_str(row.get(reverse_map.get("linkedin", "linkedin"))),
            twitter=_safe_str(row.get(reverse_map.get("twitter", "twitter"))),
            facebook=_safe_str(row.get(reverse_map.get("facebook", "facebook"))),
            metadata_text=_safe_str(row.get(reverse_map.get("metadata_text", "metadata"))),
            year_established=_parse_year(
                row.get(reverse_map.get("year_established", "year_established"))
            ),
            org_type=_safe_str(row.get(reverse_map.get("org_type", "org_type"))),
            external_id=_safe_str(row.get(reverse_map.get("external_id", "external_id"))),
        )
        organizations.append(org)

    logger.info(f"Loaded {len(organizations)} unique organizations")
    return organizations


def load_members_from_csv(csv_path: str | Path) -> List[dict]:
    """Load member/contact info from a CSV.

    Returns dicts with org_name, first_name, last_name, email for later linking.
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)

    members = []
    for _, row in df.iterrows():
        org_name = _safe_str(row.get("organization_name"))
        email = _safe_str(row.get("email"))
        first_name = _safe_str(row.get("first_name"))

        if not org_name or not email or not first_name:
            continue

        members.append({
            "org_name": org_name,
            "first_name": first_name,
            "last_name": _safe_str(row.get("last_name")),
            "email": email,
            "is_primary": True,
        })

    logger.info(f"Loaded {len(members)} member contacts")
    return members
