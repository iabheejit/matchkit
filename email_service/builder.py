"""Email builder using Jinja2 templates.

Templates receive branding variables from settings, making the
email output fully white-label-able without editing HTML/TXT files.
"""
import logging
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from datetime import datetime

from config.settings import settings

logger = logging.getLogger(__name__)


class EmailBuilder:
    """Build digest emails from Jinja2 templates."""

    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = str(Path(__file__).parent / "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html"]),
        )

    def build_digest(
        self,
        recipient_org: Dict[str, Any],
        matches: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Build HTML and text versions of the match digest.

        Args:
            recipient_org: Dict with {"first_name": str, "org_name": str}.
            matches: List of match dicts, each with:
                - org: {"name", "description", "interests", "regions", "website"}
                - score: float (0-1)
                - interest_score: float (0-1)
                - geo_score: float (0-1)
                - rationale: str | None
                - profile_url: str

        Returns:
            Dict with "html", "text", and "subject" keys.
        """
        app_name = settings.app_name
        context = {
            "recipient": recipient_org,
            "matches": matches,
            "week_date": datetime.now().strftime("%B %d, %Y"),
            "match_count": len(matches),
            # Branding
            "app_name": app_name,
            "app_tagline": settings.app_tagline,
            "support_email": settings.support_email,
        }

        try:
            html_template = self.env.get_template("weekly_digest.html")
            text_template = self.env.get_template("weekly_digest.txt")
        except Exception as e:
            logger.error(f"Failed to load email templates: {e}")
            raise

        subject = f"Your Weekly {app_name} Digest - {context['week_date']}"

        return {
            "html": html_template.render(**context),
            "text": text_template.render(**context),
            "subject": subject,
        }


# Singleton instance
email_builder = EmailBuilder()
