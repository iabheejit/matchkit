"""URL utilities for MatchKit."""
import re

from config.settings import settings


def name_to_slug(name: str) -> str:
    """Convert a name to a URL-safe slug.

    Example: "Acme Corporation" → "acme-corporation"
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)  # Remove special chars
    slug = re.sub(r"[\s_]+", "-", slug)   # Spaces/underscores → hyphens
    slug = re.sub(r"-+", "-", slug)       # Collapse multiple hyphens
    return slug.strip("-")


def get_profile_url(org_name: str) -> str:
    """Get the profile URL for an organization.

    Uses profile_base_url and profile_url_pattern from settings.
    Returns "#" if profile_base_url is not configured.
    """
    if not settings.profile_base_url:
        return "#"
    slug = name_to_slug(org_name)
    pattern = settings.profile_url_pattern.format(slug=slug)
    base = settings.profile_base_url.rstrip("/")
    return f"{base}{pattern}"
